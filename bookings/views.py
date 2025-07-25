from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q, Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils import timezone
from decimal import Decimal
import logging
from django.conf import settings
from django.db import transaction
from payments.services import StripePaymentService
from .models import Booking, Review, BookingReschedule, BookingMessage
from .serializers import (
    BookingListSerializer, BookingDetailSerializer, BookingCreateSerializer,
    BookingUpdateSerializer, ReviewSerializer, ReviewCreateSerializer,
    BookingRescheduleSerializer, BookingMessageSerializer
)
from .filters import BookingFilter
import traceback
from rest_framework import serializers

logger = logging.getLogger(__name__)


class BookingListView(generics.ListAPIView):
    """
    List user's bookings
    """
    serializer_class = BookingListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = BookingFilter
    ordering_fields = ['scheduled_date', 'created_at', 'total_amount']
    ordering = ['-scheduled_date', '-scheduled_time']
    
    @swagger_auto_schema(
        operation_description="Get user's bookings",
        manual_parameters=[
            openapi.Parameter(
                'status', openapi.IN_QUERY,
                description="Filter by booking status",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'upcoming', openapi.IN_QUERY,
                description="Show only upcoming bookings",
                type=openapi.TYPE_BOOLEAN
            ),
        ],
        responses={200: BookingListSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        user = self.request.user
        region = getattr(self.request, 'region', None)
        
        if user.user_type == 'professional':
            # Professional sees their bookings
            try:
                professional = user.professional_profile
                return Booking.objects.get_professional_bookings(professional, region)
            except:
                return Booking.objects.none()
        else:
            # Customer sees their bookings
            return Booking.objects.get_customer_bookings(user, region)


class BookingCreateView(generics.CreateAPIView):
    """
    Create new booking with server-side payment calculation
    """
    serializer_class = BookingCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Create new booking with server-side payment calculation",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['professional', 'service', 'scheduled_date', 'scheduled_time'],
            properties={
                'professional': openapi.Schema(type=openapi.TYPE_INTEGER, description='Professional ID'),
                'service': openapi.Schema(type=openapi.TYPE_INTEGER, description='Service ID'),
                'scheduled_date': openapi.Schema(type=openapi.TYPE_STRING, format='date', description='Booking date (YYYY-MM-DD)'),
                'scheduled_time': openapi.Schema(type=openapi.TYPE_STRING, format='time', description='Booking time (HH:MM)'),
                'payment_type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['full', 'partial'],
                    default='partial',
                    description='Payment type: "full" for full payment, "partial" for 50% now + 50% later'
                ),
                'selected_addons': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'addon_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'quantity': openapi.Schema(type=openapi.TYPE_INTEGER, default=1)
                        }
                    ),
                    description='Selected addons with quantities'
                ),
                'booking_for_self': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=True),
                'address_line1': openapi.Schema(type=openapi.TYPE_STRING),
                'city': openapi.Schema(type=openapi.TYPE_STRING),
                'customer_notes': openapi.Schema(type=openapi.TYPE_STRING),
            }
        ),
        responses={
            201: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'booking_id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid'),
                    'total_amount': openapi.Schema(type=openapi.TYPE_NUMBER, format='decimal'),
                    'payment_amount': openapi.Schema(type=openapi.TYPE_NUMBER, format='decimal'),
                    'stripe_payment_intent_id': openapi.Schema(type=openapi.TYPE_STRING),
                    'stripe_client_secret': openapi.Schema(type=openapi.TYPE_STRING),
                    'payment_type': openapi.Schema(type=openapi.TYPE_STRING),
                    'server_calculated': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=True),
                    'breakdown': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'base_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'addon_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'tax_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'discount_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'total_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'deposit_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'deposit_percentage': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'remaining_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                        }
                    )
                }
            ),
            400: 'Bad Request - Validation errors'
        }
    )
    def post(self, request, *args, **kwargs):
        """
        Create booking with comprehensive error logging
        """
        # Log the incoming request
        logger.info(f"Booking creation request from user {request.user.id}")
        logger.debug(f"Request data: {request.data}")
        
        try:
            with transaction.atomic():
                # Create the booking with server-side calculations
                response = super().post(request, *args, **kwargs)
                
                # If booking was created successfully, process payment
                if response.status_code == 201:
                    booking_data = response.data
                    
                    # Use the booking object stored in perform_create with temporary attributes
                    booking = getattr(request, '_booking_with_attrs', None)
                    if not booking:
                        # Fallback to database fetch if not available
                        booking = Booking.objects.get(booking_id=booking_data.get('booking_id'))
                    
                    logger.info(f"Booking {booking.booking_id} created successfully")
                    
                    # Get server-calculated payment details
                    payment_amount = getattr(booking, '_payment_amount', booking.deposit_amount)
                    payment_type = getattr(booking, '_payment_type', 'partial')
                    
                    logger.info(f"Creating Stripe payment intent for booking {booking.booking_id}")
                    logger.debug(f"Payment amount: {payment_amount}, Payment type: {payment_type}")
                    
                    try:
                        # Create Stripe customer for this transaction
                        customer = StripePaymentService.create_customer(request.user)
                        logger.info(f"Created Stripe customer {customer.id}")
                        
                        # Create payment intent with server-calculated amounts
                        payment_intent, payment = StripePaymentService.create_payment_intent(
                            booking=booking,
                            amount=payment_amount,
                            payment_type=payment_type,
                            customer_id=customer.id
                        )
                        
                        logger.info(f"Created payment intent {payment_intent.id} for booking {booking.booking_id}")
                        
                        # Calculate remaining amount
                        remaining_amount = booking.total_amount - payment_amount
                        
                        # Add payment information to response
                        response.data.update({
                            'stripe_payment_intent_id': payment_intent.id,
                            'stripe_client_secret': payment_intent.client_secret,
                            'payment_amount': str(payment_amount),
                            'payment_type': payment_type,
                            'server_calculated': True,
                            'breakdown': {
                                'base_amount': str(booking.base_amount),
                                'addon_amount': str(booking.addon_amount),
                                'tax_amount': str(booking.tax_amount),
                                'discount_amount': str(booking.discount_amount),
                                'total_amount': str(booking.total_amount),
                                'deposit_amount': str(booking.deposit_amount),
                                'deposit_percentage': str(booking.deposit_percentage),
                                'remaining_amount': str(remaining_amount),
                            }
                        })
                        
                        logger.info(f"Successfully created booking {booking.booking_id} with payment intent")
                        
                    except Exception as stripe_error:
                        logger.error(f"Stripe payment creation failed for booking {booking.booking_id}")
                        logger.error(f"Stripe error: {str(stripe_error)}")
                        logger.error(f"Stripe error traceback: {traceback.format_exc()}")
                        
                        # Delete the booking since payment setup failed
                        booking.delete()
                        
                        return Response(
                            {
                                'error': 'Failed to setup payment for booking.',
                                'details': str(stripe_error) if settings.DEBUG else 'Payment setup failed'
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                return response
                
        except Exception as e:
            logger.error(f"Booking creation failed for user {request.user.id}")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            logger.error(f"Request data that caused error: {request.data}")
            
            # Log additional context
            try:
                serializer = self.get_serializer(data=request.data)
                if not serializer.is_valid():
                    logger.error(f"Serializer validation errors: {serializer.errors}")
            except Exception as serializer_error:
                logger.error(f"Could not validate serializer: {str(serializer_error)}")
            
            return Response(
                {
                    'error': 'Failed to create booking with payment. Please try again.',
                    'details': str(e) if settings.DEBUG else 'Internal server error',
                    'error_type': type(e).__name__ if settings.DEBUG else None
                },
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['region'] = getattr(self.request, 'region', None)
        return context

    def perform_create(self, serializer):
        booking = serializer.save()
        
        # Store the booking object with temporary attributes in the request
        # so we can access it later in the post method
        self.request._booking_with_attrs = booking
        
        # Send notifications
        try:
            from notifications.tasks import send_booking_notification, send_admin_booking_email
            send_booking_notification.delay(
                booking.id, 
                'booking_created',
                [booking.customer.id, booking.professional.user.id]
            )
            # Send admin email
            send_admin_booking_email.delay(booking.id)
        except Exception as e:
            logger.error(f"Failed to send booking notification or admin email: {str(e)}")




class BookingDetailView(generics.RetrieveAPIView):
    """
    Get booking details
    """
    serializer_class = BookingDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'booking_id'
    
    @swagger_auto_schema(
        operation_description="Get booking details",
        responses={200: BookingDetailSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        user = self.request.user
        
        # Users can only see their own bookings
        if user.user_type == 'professional':
            try:
                professional = user.professional_profile
                return Booking.objects.filter(professional=professional)
            except:
                return Booking.objects.none()
        else:
            return Booking.objects.filter(customer=user)


class BookingUpdateView(generics.UpdateAPIView):
    """
    Update booking details (limited fields)
    """
    serializer_class = BookingUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'booking_id'
    
    @swagger_auto_schema(
        operation_description="Update booking details",
        request_body=BookingUpdateSerializer,
        responses={200: BookingDetailSerializer()}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
    
    def get_queryset(self):
        # Only customers can update their bookings
        return Booking.objects.filter(
            customer=self.request.user,
            status__in=['pending', 'confirmed']
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Cancel booking",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'reason': openapi.Schema(type=openapi.TYPE_STRING, description='Cancellation reason')
        }
    ),
    responses={200: 'Booking cancelled successfully'}
)
def cancel_booking(request, booking_id):
    """
    Cancel a booking (no refunds provided)
    """
    booking = get_object_or_404(
        Booking,
        booking_id=booking_id,
        customer=request.user
    )
    
    if not booking.can_be_cancelled:
        return Response(
            {'error': 'Booking cannot be cancelled'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    reason = request.data.get('reason', '')
    
    # Update booking status (no refunds for cancellations)
    booking.status = 'cancelled'
    booking.cancelled_by = request.user
    booking.cancelled_at = timezone.now()
    booking.cancellation_reason = reason
    
    # Note: Payment status remains unchanged - no refunds
    # booking.payment_status stays as is (deposit_paid, fully_paid, etc.)
    
    booking.save()
    
    # Create status history
    from .models import BookingStatusHistory
    BookingStatusHistory.objects.create(
        booking=booking,
        previous_status='confirmed',
        new_status='cancelled',
        changed_by=request.user,
        reason=reason
    )
    
    # Send notifications
    try:
        from notifications.tasks import send_booking_notification
        send_booking_notification.delay(
            booking.id,
            'booking_cancelled',
            [booking.professional.user.id]
        )
        
        # Notify admin about cancellation
        from notifications.tasks import create_notification
        create_notification.delay(
            user_id=1,  # Assuming admin user ID is 1, adjust as needed
            notification_type='booking_cancelled',
            title='Booking Cancelled',
            message=f'Booking {booking.booking_id} has been cancelled by customer. Reason: {reason}. No refund will be provided.',
            related_booking_id=booking.id
        )
    except Exception as e:
        logger.error(f"Failed to send cancellation notification: {str(e)}")
    
    return Response({
        'message': 'Booking cancelled successfully. No refund will be provided.',
        'payment_status': booking.payment_status,
        'note': 'Payment remains with the service provider as per cancellation policy'
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Confirm booking (professionals only)",
    responses={200: 'Booking confirmed successfully'}
)
def confirm_booking(request, booking_id):
    """
    Confirm a booking (professional only)
    """
    try:
        professional = request.user.professional_profile
    except:
        return Response(
            {'error': 'Only professionals can confirm bookings'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    booking = get_object_or_404(
        Booking,
        booking_id=booking_id,
        professional=professional,
        status='pending'
    )
    
    # Update booking status
    booking.status = 'confirmed'
    booking.confirmed_at = timezone.now()
    booking.save()
    
    # Send notifications
    try:
        from notifications.tasks import send_booking_notification
        send_booking_notification.delay(
            booking.id,
            'booking_confirmed',
            [booking.customer.id]
        )
    except Exception as e:
        logger.error(f"Failed to send confirmation notification: {str(e)}")
    
    return Response({'message': 'Booking confirmed successfully'})


class BookingRescheduleView(generics.CreateAPIView):
    """
    Request booking reschedule
    """
    serializer_class = BookingRescheduleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Request booking reschedule",
        request_body=BookingRescheduleSerializer,
        responses={201: BookingRescheduleSerializer()}
    )
    def post(self, request, *args, **kwargs):
        try:
            logger.info(f"Reschedule request started for user {request.user.id}")
            logger.info(f"Request data: {request.data}")
            logger.info(f"URL kwargs: {self.kwargs}")
            
            return super().post(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Reschedule request failed: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error traceback: {traceback.format_exc()}")
            return Response(
                {
                    'error': 'Failed to create reschedule request',
                    'details': str(e) if settings.DEBUG else 'Internal server error',
                    'error_type': type(e).__name__ if settings.DEBUG else None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_serializer_context(self):
        try:
            context = super().get_serializer_context()
            booking_id = self.kwargs['booking_id']

            # Defensive check for authentication
            if not hasattr(self.request, 'user') or not self.request.user.is_authenticated:
                raise serializers.ValidationError("Authentication credentials were not provided or are invalid.")

            try:
                booking = Booking.objects.get(
                    booking_id=booking_id,
                    customer=self.request.user,
                    status__in=['confirmed', 'pending']
                )
            except Booking.DoesNotExist:
                raise serializers.ValidationError("Booking not found or you don't have permission to reschedule it")

            context['booking'] = booking
            return context

        except Exception as e:
            logger.error(f"Error in get_serializer_context: {str(e)}")
            raise serializers.ValidationError(f"Error setting up reschedule request: {str(e)}")


class ReviewCreateView(generics.CreateAPIView):
    """
    Create review for completed booking
    """
    serializer_class = ReviewCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Create review for completed booking",
        request_body=ReviewCreateSerializer,
        responses={201: ReviewSerializer()}
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        booking_id = self.kwargs['booking_id']
        booking = get_object_or_404(
            Booking,
            booking_id=booking_id,
            customer=request.user
        )
        context['booking'] = booking
        return context


class BookingMessageView(generics.ListCreateAPIView):
    """
    Booking messages between customer and professional
    """
    serializer_class = BookingMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        booking_id = self.kwargs['booking_id']
        
        # Verify user has access to this booking
        user = self.request.user
        booking_filter = Q(booking__booking_id=booking_id)
        
        if user.user_type == 'professional':
            try:
                professional = user.professional_profile
                booking_filter &= Q(booking__professional=professional)
            except:
                return BookingMessage.objects.none()
        else:
            booking_filter &= Q(booking__customer=user)
        
        return BookingMessage.objects.filter(booking_filter).order_by('created_at')
    
    def perform_create(self, serializer):
        booking_id = self.kwargs['booking_id']
        booking = get_object_or_404(Booking, booking_id=booking_id)
        
        # Verify user has access
        user = self.request.user
        if user != booking.customer and (
            not hasattr(user, 'professional_profile') or 
            user.professional_profile != booking.professional
        ):
            raise PermissionError("No access to this booking")
        
        serializer.save(booking=booking, sender=user)
        
        

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Process remaining payment for partially paid booking",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['booking_id'],
        properties={
            'booking_id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid'),
        }
    ),
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'stripe_payment_intent_id': openapi.Schema(type=openapi.TYPE_STRING),
                'stripe_client_secret': openapi.Schema(type=openapi.TYPE_STRING),
                'payment_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                'payment_type': openapi.Schema(type=openapi.TYPE_STRING, default='remaining'),
                'server_calculated': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=True),
            }
        )
    }
)
def process_remaining_payment(request):
    """
    Process remaining payment for a booking that had partial payment completed
    """
    try:
        booking_id = request.data.get('booking_id')
        
        if not booking_id:
            return Response(
                {'error': 'booking_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify user owns the booking
        booking = get_object_or_404(
            Booking,
            booking_id=booking_id,
            customer=request.user
        )
        
        # Process remaining payment with server-side calculation
        payment_intent, payment = StripePaymentService.process_remaining_payment(str(booking_id))
        
        response_data = {
            'stripe_payment_intent_id': payment_intent.id,
            'stripe_client_secret': payment_intent.client_secret,
            'payment_amount': str(payment.amount),
            'payment_type': 'remaining',
            'server_calculated': True,
            'booking_breakdown': {
                'total_amount': str(booking.total_amount),
                'initial_payment': str(booking.deposit_amount),
                'remaining_amount': str(payment.amount),
            }
        }
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Remaining payment processing failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def debug_reschedule(request, booking_id):
    """
    Debug endpoint to test reschedule functionality
    """
    try:
        logger.info(f"Debug reschedule request for booking {booking_id}")
        logger.info(f"User: {request.user.id}")
        
        # Check if booking exists
        try:
            booking = Booking.objects.get(booking_id=booking_id)
            logger.info(f"Booking found: {booking.booking_id}, status: {booking.status}")
        except Booking.DoesNotExist:
            logger.error(f"Booking {booking_id} not found")
            return Response({'error': 'Booking not found'}, status=404)
        
        # Check if user has permission
        if booking.customer != request.user:
            logger.error(f"User {request.user.id} does not own booking {booking_id}")
            return Response({'error': 'Permission denied'}, status=403)
        
        # Check if booking can be rescheduled
        if booking.status not in ['confirmed', 'pending']:
            logger.error(f"Booking {booking_id} cannot be rescheduled (status: {booking.status})")
            return Response({'error': 'Booking cannot be rescheduled'}, status=400)
        
        # Test serializer creation
        try:
            from .serializers import BookingRescheduleSerializer
            serializer = BookingRescheduleSerializer(data={'reason': 'Test reason'})
            if serializer.is_valid():
                logger.info("Serializer is valid")
            else:
                logger.error(f"Serializer errors: {serializer.errors}")
                return Response({'error': 'Serializer validation failed', 'details': serializer.errors}, status=400)
        except Exception as e:
            logger.error(f"Serializer test failed: {str(e)}")
            return Response({'error': 'Serializer test failed', 'details': str(e)}, status=500)
        
        return Response({
            'message': 'Debug test passed',
            'booking_id': str(booking.booking_id),
            'booking_status': booking.status,
            'user_id': request.user.id,
            'can_reschedule': True
        })
        
    except Exception as e:
        logger.error(f"Debug reschedule failed: {str(e)}")
        logger.error(f"Error traceback: {traceback.format_exc()}")
        return Response({
            'error': 'Debug test failed',
            'details': str(e),
            'error_type': type(e).__name__
        }, status=500)
