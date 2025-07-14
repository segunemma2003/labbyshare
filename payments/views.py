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
import stripe
import json
import logging

from .models import Payment, SavedPaymentMethod
from .serializers import (
    PaymentSerializer, PaymentMethodSerializer, PaymentIntentSerializer,
    RefundRequestSerializer
)
from .services import StripePaymentService
from bookings.models import Booking

logger = logging.getLogger(__name__)


class PaymentListView(generics.ListAPIView):
    """
    List user payments
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'payment_type']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return Payment.objects.none()
            
        return Payment.objects.filter(
            customer=self.request.user
        ).select_related('booking')


class PaymentDetailView(generics.RetrieveAPIView):
    """
    Get payment details
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'payment_id'
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser
        if getattr(self, 'swagger_fake_view', False):
            return Payment.objects.none()
            
        return Payment.objects.filter(customer=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Create payment intent",
    request_body=PaymentIntentSerializer,
    responses={200: openapi.Response('Payment intent created')}
)
def create_payment_intent(request):
    """
    Create Stripe payment intent
    """
    serializer = PaymentIntentSerializer(data=request.data, context={'request': request})
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        booking = serializer.validated_data['booking_id']
        payment_type = serializer.validated_data['payment_type']
        payment_method_id = serializer.validated_data.get('payment_method_id')
        save_payment_method = serializer.validated_data.get('save_payment_method', False)
        use_saved_method = serializer.validated_data.get('use_saved_method', False)
        
        # Create or get Stripe customer
        customer = StripePaymentService.create_customer(request.user)
        
        # Create payment intent
        payment_intent, payment = StripePaymentService.create_payment_intent(
            booking=booking,
            payment_type=payment_type,
            customer_id=customer.id,
            payment_method_id=payment_method_id
        )
        
        # Save payment method if requested
        if save_payment_method and payment_method_id:
            StripePaymentService.save_payment_method(
                customer.id, 
                payment_method_id, 
                request.user
            )
        
        return Response({
            'client_secret': payment_intent.client_secret,
            'payment_id': str(payment.payment_id),
            'requires_action': payment_intent.status == 'requires_action'
        })
        
    except Exception as e:
        logger.error(f"Payment intent creation failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Confirm payment",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'payment_intent_id': openapi.Schema(type=openapi.TYPE_STRING),
            'payment_method_id': openapi.Schema(type=openapi.TYPE_STRING),
        },
        required=['payment_intent_id']
    ),
    responses={200: 'Payment confirmed'}
)
def confirm_payment(request):
    """
    Confirm payment intent
    """
    payment_intent_id = request.data.get('payment_intent_id')
    payment_method_id = request.data.get('payment_method_id')
    
    if not payment_intent_id:
        return Response(
            {'error': 'payment_intent_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        payment_intent = StripePaymentService.confirm_payment_intent(
            payment_intent_id,
            payment_method_id
        )
        
        return Response({
            'status': payment_intent.status,
            'requires_action': payment_intent.status == 'requires_action'
        })
        
    except Exception as e:
        logger.error(f"Payment confirmation failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Request refund",
    request_body=RefundRequestSerializer,
    responses={200: 'Refund processed'}
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
        
        refund, refund_payment = StripePaymentService.create_refund(
            payment,
            amount,
            reason
        )
        
        return Response({
            'message': 'Refund processed successfully',
            'refund_id': refund.id,
            'refund_amount': float(refund_payment.amount)
        })
        
    except Exception as e:
        logger.error(f"Refund failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


class SavedPaymentMethodsView(generics.ListCreateAPIView):
    """
    List and create saved payment methods
    """
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]
    
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
    
    def get_queryset(self):
        # Handle schema generation with AnonymousUser - THIS WAS THE MAIN ISSUE
        if getattr(self, 'swagger_fake_view', False):
            return SavedPaymentMethod.objects.none()
            
        return SavedPaymentMethod.objects.filter(customer=self.request.user)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@swagger_auto_schema(
    operation_description="Get payment summary for user",
    responses={200: openapi.Response('Payment summary')}
)
def payment_summary(request):
    """
    Get payment summary for user
    """
    payments = Payment.objects.filter(customer=request.user)
    
    summary = {
        'total_payments': payments.count(),
        'successful_payments': payments.filter(status='succeeded').count(),
        'total_amount_paid': float(
            payments.filter(status='succeeded').aggregate(
                total=models.Sum('amount')
            )['total'] or 0
        ),
        'pending_payments': payments.filter(status='pending').count(),
        'failed_payments': payments.filter(status='failed').count(),
    }
    
    return Response(summary)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhook events
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid payload in Stripe webhook")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook")
        return HttpResponse(status=400)
    
    # Handle the event
    try:
        success = StripePaymentService.handle_webhook_event(event)
        if success:
            return HttpResponse(status=200)
        else:
            return HttpResponse(status=500)
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return HttpResponse(status=500)