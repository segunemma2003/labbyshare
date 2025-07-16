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
from payment.services import StripePaymentService

from .models import Booking, Review, BookingReschedule, BookingMessage
from .serializers import (
    BookingListSerializer, BookingDetailSerializer, BookingCreateSerializer,
    BookingUpdateSerializer, ReviewSerializer, ReviewCreateSerializer,
    BookingRescheduleSerializer, BookingMessageSerializer
)
from .filters import BookingFilter

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
        Create booking with server-side payment calculation in atomic transaction
        """
        try:
            with transaction.atomic():
                # Create the booking with server-side calculations
                response = super().post(request, *args, **kwargs)
                
                # If booking was created successfully, process payment
                if response.status_code == 201:
                    booking_data = response.data
                    booking = Booking.objects.get(booking_id=booking_data.get('booking_id'))
                    
                    # Get server-calculated payment details
                    payment_amount = getattr(booking, '_payment_amount', booking.deposit_amount)
                    payment_type = getattr(booking, '_payment_type', 'partial')
                    
                    # Create Stripe customer for this transaction (no storage on user model)
                    customer = StripePaymentService.create_customer(request.user)
                    
                    # Create payment intent with server-calculated amounts
                    payment_intent, payment = StripePaymentService.create_payment_intent(
                        booking=booking,
                        amount=payment_amount,
                        payment_type=payment_type,
                        customer_id=customer.id
                    )
                    
                    # Calculate remaining amount
                    remaining_amount = booking.total_amount - payment_amount
                    
                    # Add payment information to response
                    response.data.update({
                        'stripe_payment_intent_id': payment_intent.id,
                        'stripe_client_secret': payment_intent.client_secret,
                        'payment_amount': str(payment_amount),
                        'payment_type': payment_type,
                        'server_calculated': True,  # Indicate server-side calculation
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
                    
                    logger.info(f"Created booking {booking.booking_id} with server-calculated payment: {payment_amount} {payment_intent.currency}")
                    
                return response
                
        except Exception as e:
            logger.error(f"Failed to create booking with payment: {str(e)}")
            return Response(
                {
                    'error': 'Failed to create booking with payment. Please try again.',
                    'details': str(e) if settings.DEBUG else 'Internal server error'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['region'] = getattr(self.request, 'region', None)
        return context

    def perform_create(self, serializer):
        booking = serializer.save()
        
        # Send notifications
        try:
            from notifications.tasks import send_booking_notification
            send_booking_notification.delay(
                booking.id, 
                'booking_created',
                [booking.customer.id, booking.professional.user.id]
            )
        except Exception as e:
            logger.error(f"Failed to send booking notification: {str(e)}")




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
    Cancel a booking
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
    
    # Update booking status
    booking.status = 'cancelled'
    booking.cancelled_by = request.user
    booking.cancelled_at = timezone.now()
    booking.cancellation_reason = reason
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
    except Exception as e:
        logger.error(f"Failed to send cancellation notification: {str(e)}")
    
    return Response({'message': 'Booking cancelled successfully'})


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
        return super().post(request, *args, **kwargs)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        booking_id = self.kwargs['booking_id']
        booking = get_object_or_404(
            Booking,
            booking_id=booking_id,
            customer=request.user,
            status__in=['confirmed', 'pending']
        )
        context['booking'] = booking
        return context


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