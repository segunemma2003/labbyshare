from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.conf import settings
from django.db import models
from decimal import Decimal
import stripe
import json
import logging

from .models import Payment, SavedPaymentMethod, PaymentRefund
from .serializers import (
    PaymentSerializer, PaymentMethodSerializer, PaymentIntentCreateSerializer,
    PaymentIntentResponseSerializer, PaymentConfirmSerializer,
    RefundRequestSerializer, RefundResponseSerializer, RemainingPaymentSerializer,
    PaymentSummarySerializer, BookingPaymentStatusSerializer
)
from .services import StripePaymentService
from bookings.models import Booking

logger = logging.getLogger(__name__)


class PaymentListView(generics.ListAPIView):
    """
    List user payments with filtering and pagination
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'payment_type', 'currency']
    ordering_fields = ['created_at', 'amount', 'processed_at']
    ordering = ['-created_at']
    
    @swagger_auto_schema(
        operation_description="List user payments with filtering options",
        manual_parameters=[
            openapi.Parameter('status', openapi.IN_QUERY, description="Filter by payment status", type=openapi.TYPE_STRING),
            openapi.Parameter('payment_type', openapi.IN_QUERY, description="Filter by payment type", type=openapi.TYPE_STRING),
            openapi.Parameter('currency', openapi.IN_QUERY, description="Filter by currency", type=openapi.TYPE_STRING),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return Payment.objects.none()
            
        return Payment.objects.filter(
            customer=self.request.user
        ).select_related('booking', 'booking__service', 'booking__professional')


class PaymentDetailView(generics.RetrieveAPIView):
    """
    Get detailed payment information
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'payment_id'
    
    @swagger_auto_schema(
        operation_description="Get detailed payment information",
        responses={200: PaymentSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return Payment.objects.none()
            
        return Payment.objects.filter(
            customer=self.request.user
        ).select_related('booking', 'booking__service')


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Create payment intent for booking",
    request_body=PaymentIntentCreateSerializer,
    responses={
        200: PaymentIntentResponseSerializer(),
        400: 'Bad Request - Validation errors'
    }
)
def create_payment_intent(request):
    """
    Create Stripe payment intent for booking payment
    """
    serializer = PaymentIntentCreateSerializer(data=request.data, context={'request': request})
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        booking = serializer.validated_data['booking_id']
        payment_type = serializer.validated_data['payment_type']
        payment_method_id = serializer.validated_data.get('payment_method_id')
        save_payment_method = serializer.validated_data.get('save_payment_method', False)
        
        # Calculate payment amount based on type
        if payment_type == 'full':
            amount = booking.total_amount
        elif payment_type == 'deposit':
            amount = booking.deposit_amount
        elif payment_type == 'remaining':
            amount = booking.total_amount - booking.deposit_amount
        else:
            return Response(
                {'error': 'Invalid payment type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or get Stripe customer
        customer = StripePaymentService.create_customer(request.user)
        
        # Create payment intent
        payment_intent, payment = StripePaymentService.create_payment_intent(
            booking=booking,
            amount=amount,
            payment_type=payment_type,
            customer_id=customer.id,
            payment_method_id=payment_method_id
        )
        
        # Save payment method if requested
        if save_payment_method and payment_method_id:
            try:
                StripePaymentService.save_payment_method(
                    customer.id, 
                    payment_method_id, 
                    request.user
                )
            except Exception as e:
                logger.error(f"Failed to save payment method: {str(e)}")
                # Don't fail the payment creation
        
        response_data = {
            'client_secret': payment_intent.client_secret,
            'payment_id': str(payment.payment_id),
            'amount': str(amount),
            'currency': payment_intent.currency,
            'payment_type': payment_type,
            'requires_action': payment_intent.status == 'requires_action',
            'booking_breakdown': {
                'base_amount': str(booking.base_amount),
                'addon_amount': str(booking.addon_amount),
                'tax_amount': str(booking.tax_amount),
                'discount_amount': str(booking.discount_amount),
                'total_amount': str(booking.total_amount),
                'deposit_amount': str(booking.deposit_amount),
                'amount_being_charged': str(amount),
            }
        }
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Payment intent creation failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Confirm payment intent",
    request_body=PaymentConfirmSerializer,
    responses={
        200: openapi.Response(
            description="Payment confirmed",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(type=openapi.TYPE_STRING),
                    'requires_action': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'payment_id': openapi.Schema(type=openapi.TYPE_STRING),
                    'booking_id': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )
        ),
        400: 'Bad Request - Payment confirmation failed'
    }
)
def confirm_payment(request):
    """
    Confirm payment intent (for manual confirmation flow)
    """
    serializer = PaymentConfirmSerializer(data=request.data, context={'request': request})
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        payment = serializer.validated_data['payment_intent_id']
        payment_method_id = serializer.validated_data.get('payment_method_id')
        
        # Confirm payment intent
        payment_intent = StripePaymentService.confirm_payment_intent(
            payment.stripe_payment_intent_id,
            payment_method_id
        )
        
        response_data = {
            'status': payment_intent.status,
            'requires_action': payment_intent.status == 'requires_action',
            'payment_id': str(payment.payment_id),
            'booking_id': str(payment.booking.booking_id),
        }
        
        # If payment succeeded immediately, update the payment
        if payment_intent.status == 'succeeded':
            StripePaymentService.handle_payment_success(payment.stripe_payment_intent_id)
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Payment confirmation failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Process remaining payment for booking",
    request_body=RemainingPaymentSerializer,
    responses={
        200: PaymentIntentResponseSerializer(),
        400: 'Bad Request - Cannot process remaining payment'
    }
)
def process_remaining_payment(request):
    """
    Process remaining payment for a booking that had deposit paid
    """
    serializer = RemainingPaymentSerializer(data=request.data, context={'request': request})
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        booking = serializer.validated_data['booking_id']
        payment_method_id = serializer.validated_data.get('payment_method_id')
        
        # Create or get Stripe customer
        customer = StripePaymentService.create_customer(request.user)
        
        # Process remaining payment
        payment_intent, payment = StripePaymentService.process_remaining_payment(
            str(booking.booking_id),
            customer.id
        )
        
        response_data = {
            'client_secret': payment_intent.client_secret,
            'payment_id': str(payment.payment_id),
            'amount': str(payment.amount),
            'currency': payment_intent.currency,
            'payment_type': 'remaining',
            'requires_action': payment_intent.status == 'requires_action',
            'booking_breakdown': {
                'total_amount': str(booking.total_amount),
                'deposit_amount': str(booking.deposit_amount),
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


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Request payment refund",
    request_body=RefundRequestSerializer,
    responses={
        200: RefundResponseSerializer(),
        400: 'Bad Request - Refund failed'
    }
)
def request_refund(request):
    """
    Request payment refund
    """
    serializer = RefundRequestSerializer(data=request.data, context={'request': request})
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        payment = serializer.validated_data['payment_id']
        amount = serializer.validated_data.get('amount')
        reason = serializer.validated_data['reason']
        
        # Process refund
        refund_result = StripePaymentService.create_refund(
            payment.id,
            amount,
            reason
        )
        
        if refund_result['success']:
            return Response({
                'success': True,
                'refund_id': refund_result['refund_id'],
                'amount': str(refund_result['amount']),
                'status': refund_result['status'],
                'message': 'Refund processed successfully'
            })
        else:
            return Response(
                {'error': refund_result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )
        
    except Exception as e:
        logger.error(f"Refund request failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Get payment summary for user",
    responses={200: PaymentSummarySerializer()}
)
def payment_summary(request):
    """
    Get comprehensive payment summary for user
    """
    try:
        payments = Payment.objects.filter(customer=request.user)
        
        # Calculate totals
        total_payments = payments.count()
        successful_payments = payments.filter(status__in=['completed', 'succeeded']).count()
        failed_payments = payments.filter(status='failed').count()
        pending_payments = payments.filter(status='pending').count()
        
        # Calculate amounts
        successful_amount = payments.filter(
            status__in=['completed', 'succeeded']
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        refunded_amount = payments.filter(
            status__in=['refunded', 'partially_refunded']
        ).aggregate(total=models.Sum('refund_amount'))['total'] or Decimal('0.00')
        
        # Currency breakdown
        currency_breakdown = {}
        for payment in payments.filter(status__in=['completed', 'succeeded']):
            currency = payment.currency.upper()
            if currency not in currency_breakdown:
                currency_breakdown[currency] = {'amount': Decimal('0.00'), 'count': 0}
            currency_breakdown[currency]['amount'] += payment.amount
            currency_breakdown[currency]['count'] += 1
        
        # Convert Decimal to string for JSON serialization
        for currency in currency_breakdown:
            currency_breakdown[currency]['amount'] = str(currency_breakdown[currency]['amount'])
        
        summary = {
            'total_payments': total_payments,
            'successful_payments': successful_payments,
            'failed_payments': failed_payments,
            'pending_payments': pending_payments,
            'total_amount_paid': successful_amount,
            'total_refunded': refunded_amount,
            'currency_breakdown': currency_breakdown
        }
        
        return Response(summary)
        
    except Exception as e:
        logger.error(f"Payment summary failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Get payment status for booking",
    responses={200: BookingPaymentStatusSerializer()}
)
def booking_payment_status(request, booking_id):
    """
    Get detailed payment status for a specific booking
    """
    try:
        booking = get_object_or_404(
            Booking,
            booking_id=booking_id,
            customer=request.user
        )
        
        # Get all payments for this booking
        payments = Payment.objects.filter(booking=booking).order_by('-created_at')
        
        # Calculate amounts
        amount_paid = payments.filter(
            status__in=['completed', 'succeeded']
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        remaining_amount = booking.total_amount - amount_paid
        
        # Determine next payment due
        next_payment_due = None
        next_payment_type = None
        
        if booking.payment_status == 'pending':
            if booking.deposit_required:
                next_payment_due = booking.deposit_amount
                next_payment_type = 'deposit'
            else:
                next_payment_due = booking.total_amount
                next_payment_type = 'full'
        elif booking.payment_status == 'deposit_paid':
            next_payment_due = remaining_amount
            next_payment_type = 'remaining'
        
        # Payment breakdown
        breakdown = {
            'base_amount': str(booking.base_amount),
            'addon_amount': str(booking.addon_amount),
            'tax_amount': str(booking.tax_amount),
            'discount_amount': str(booking.discount_amount),
            'total_amount': str(booking.total_amount),
            'deposit_amount': str(booking.deposit_amount),
        }
        
        response_data = {
            'booking_id': str(booking.booking_id),
            'payment_status': booking.payment_status,
            'total_amount': booking.total_amount,
            'deposit_amount': booking.deposit_amount,
            'amount_paid': amount_paid,
            'remaining_amount': remaining_amount,
            'payment_history': PaymentSerializer(payments, many=True).data,
            'breakdown': breakdown,
        }
        
        if next_payment_due:
            response_data['next_payment_due'] = next_payment_due
            response_data['next_payment_type'] = next_payment_type
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"Booking payment status failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class SavedPaymentMethodsView(generics.ListCreateAPIView):
    """
    List and create saved payment methods
    """
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="List saved payment methods",
        responses={200: PaymentMethodSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return SavedPaymentMethod.objects.none()
            
        return SavedPaymentMethod.objects.filter(
            customer=self.request.user
        ).order_by('-is_default', '-created_at')


class PaymentMethodDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update, or delete saved payment method
    """
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get, update, or delete payment method",
        responses={200: PaymentMethodSerializer()}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return SavedPaymentMethod.objects.none()
            
        return SavedPaymentMethod.objects.filter(customer=self.request.user)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhook events
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        
        # Process the event
        result = StripePaymentService.handle_webhook_event(event)
        
        if result['success']:
            return HttpResponse(status=200)
        else:
            logger.error(f"Webhook processing failed: {result.get('error', 'Unknown error')}")
            return HttpResponse(status=500)
            
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {str(e)}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {str(e)}")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return HttpResponse(status=500)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Complete payment for booking",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['booking_id', 'payment_type'],
        properties={
            'booking_id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid', description='Booking ID'),
            'payment_type': openapi.Schema(
                type=openapi.TYPE_STRING, 
                enum=['full', 'deposit', 'remaining'],
                description='Type of payment to complete'
            ),
            'payment_method_id': openapi.Schema(type=openapi.TYPE_STRING, description='Stripe payment method ID (optional)'),
        }
    ),
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'payment_intent_id': openapi.Schema(type=openapi.TYPE_STRING),
                'client_secret': openapi.Schema(type=openapi.TYPE_STRING),
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                'currency': openapi.Schema(type=openapi.TYPE_STRING),
                'payment_status': openapi.Schema(type=openapi.TYPE_STRING),
                'booking_payment_status': openapi.Schema(type=openapi.TYPE_STRING),
                'message': openapi.Schema(type=openapi.TYPE_STRING),
            }
        ),
        400: 'Bad Request - Validation errors',
        404: 'Booking not found'
    }
)
def complete_payment(request):
    """
    Complete payment for a booking - generates payment intent and handles completion
    """
    try:
        booking_id = request.data.get('booking_id')
        payment_type = request.data.get('payment_type')
        payment_method_id = request.data.get('payment_method_id')
        
        if not booking_id or not payment_type:
            return Response(
                {'error': 'booking_id and payment_type are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify user owns the booking
        booking = get_object_or_404(
            Booking,
            booking_id=booking_id,
            customer=request.user
        )
        
        # Calculate payment amount based on type
        if payment_type == 'full':
            amount = booking.total_amount
        elif payment_type == 'deposit':
            amount = booking.deposit_amount
        elif payment_type == 'remaining':
            if booking.payment_status != 'deposit_paid':
                return Response(
                    {'error': 'Booking must have deposit paid to process remaining payment'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            amount = booking.total_amount - booking.deposit_amount
        else:
            return Response(
                {'error': 'Invalid payment_type. Must be full, deposit, or remaining'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if payment is already completed
        if payment_type == 'full' and booking.payment_status == 'fully_paid':
            return Response(
                {'error': 'Booking is already fully paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        elif payment_type == 'deposit' and booking.payment_status in ['deposit_paid', 'fully_paid']:
            return Response(
                {'error': 'Deposit is already paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        elif payment_type == 'remaining' and booking.payment_status == 'fully_paid':
            return Response(
                {'error': 'Booking is already fully paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or get Stripe customer
        customer = StripePaymentService.create_customer(request.user)
        
        # Create payment intent
        payment_intent, payment = StripePaymentService.create_payment_intent(
            booking=booking,
            amount=amount,
            payment_type=payment_type,
            customer_id=customer.id,
            payment_method_id=payment_method_id
        )
        
        # If payment method is provided, try to confirm immediately
        if payment_method_id:
            try:
                confirmed_intent = StripePaymentService.confirm_payment_intent(
                    payment_intent.id,
                    payment_method_id
                )
                
                # If payment succeeded immediately, update status
                if confirmed_intent.status == 'succeeded':
                    result = StripePaymentService.handle_payment_success(payment_intent.id)
                    if result['success']:
                        return Response({
                            'success': True,
                            'payment_intent_id': payment_intent.id,
                            'client_secret': payment_intent.client_secret,
                            'amount': str(amount),
                            'currency': payment_intent.currency,
                            'payment_status': 'completed',
                            'booking_payment_status': booking.payment_status,
                            'message': 'Payment completed successfully'
                        })
                
                # If requires action, return client secret
                return Response({
                    'success': True,
                    'payment_intent_id': payment_intent.id,
                    'client_secret': payment_intent.client_secret,
                    'amount': str(amount),
                    'currency': payment_intent.currency,
                    'payment_status': confirmed_intent.status,
                    'booking_payment_status': booking.payment_status,
                    'message': 'Payment requires additional action'
                })
                
            except Exception as e:
                logger.error(f"Payment confirmation failed: {str(e)}")
                return Response({
                    'success': True,
                    'payment_intent_id': payment_intent.id,
                    'client_secret': payment_intent.client_secret,
                    'amount': str(amount),
                    'currency': payment_intent.currency,
                    'payment_status': 'requires_confirmation',
                    'booking_payment_status': booking.payment_status,
                    'message': 'Payment intent created, requires confirmation'
                })
        
        # Return payment intent for client-side confirmation
        return Response({
            'success': True,
            'payment_intent_id': payment_intent.id,
            'client_secret': payment_intent.client_secret,
            'amount': str(amount),
            'currency': payment_intent.currency,
            'payment_status': 'pending',
            'booking_payment_status': booking.payment_status,
            'message': 'Payment intent created successfully'
        })
        
    except Booking.DoesNotExist:
        return Response(
            {'error': 'Booking not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Payment completion failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )