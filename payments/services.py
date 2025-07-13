import stripe
from django.conf import settings
from decimal import Decimal
from .models import Payment, SavedPaymentMethod, PaymentWebhookEvent
import logging

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripePaymentService:
    """
    Service class for Stripe payment operations
    """
    
    @staticmethod
    def create_customer(user):
        """Create or get Stripe customer"""
        try:
            # Check if customer already exists
            if hasattr(user, 'stripe_customer_id') and user.stripe_customer_id:
                return stripe.Customer.retrieve(user.stripe_customer_id)
            
            # Create new customer
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name(),
                metadata={'user_id': user.id}
            )
            
            # Save customer ID to user
            user.stripe_customer_id = customer.id
            user.save(update_fields=['stripe_customer_id'])
            
            return customer
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation error: {str(e)}")
            raise Exception(f"Failed to create customer: {str(e)}")
    
    @staticmethod
    def create_payment_intent(booking, payment_type, amount=None, customer_id=None, payment_method_id=None):
        """Create Stripe payment intent"""
        try:
            # Calculate amount
            if not amount:
                if payment_type == 'deposit':
                    amount = booking.deposit_amount
                elif payment_type == 'remaining':
                    amount = booking.total_amount - booking.deposit_amount
                else:  # full payment
                    amount = booking.total_amount
            
            # Convert to cents
            amount_cents = int(amount * 100)
            
            # Get currency from region
            currency = booking.region.currency.lower()
            
            # Create payment intent
            intent_params = {
                'amount': amount_cents,
                'currency': currency,
                'customer': customer_id,
                'metadata': {
                    'booking_id': str(booking.booking_id),
                    'payment_type': payment_type,
                    'user_id': booking.customer.id
                },
                'description': f"{payment_type.title()} for {booking.service.name}",
            }
            
            if payment_method_id:
                intent_params['payment_method'] = payment_method_id
                intent_params['confirmation_method'] = 'manual'
                intent_params['confirm'] = True
            
            payment_intent = stripe.PaymentIntent.create(**intent_params)
            
            # Create payment record
            payment = Payment.objects.create(
                booking=booking,
                customer=booking.customer,
                amount=amount,
                currency=currency.upper(),
                payment_type=payment_type,
                stripe_payment_intent_id=payment_intent.id,
                stripe_customer_id=customer_id,
                payment_method_id=payment_method_id,
                description=intent_params['description'],
                status='pending'
            )
            
            return payment_intent, payment
            
        except stripe.error.StripeError as e:
            logger.error(f"Payment intent creation error: {str(e)}")
            raise Exception(f"Payment failed: {str(e)}")
    
    @staticmethod
    def confirm_payment_intent(payment_intent_id, payment_method_id=None):
        """Confirm payment intent"""
        try:
            confirm_params = {'payment_intent': payment_intent_id}
            
            if payment_method_id:
                confirm_params['payment_method'] = payment_method_id
            
            return stripe.PaymentIntent.confirm(**confirm_params)
            
        except stripe.error.StripeError as e:
            logger.error(f"Payment confirmation error: {str(e)}")
            raise Exception(f"Payment confirmation failed: {str(e)}")
    
    @staticmethod
    def save_payment_method(customer_id, payment_method_id, user):
        """Save payment method for future use"""
        try:
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id,
            )
            
            # Get payment method details
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
            card = payment_method.card
            
            # Save to database
            saved_method = SavedPaymentMethod.objects.create(
                customer=user,
                stripe_payment_method_id=payment_method_id,
                stripe_customer_id=customer_id,
                card_brand=card.brand,
                card_last_four=card.last4,
                card_exp_month=card.exp_month,
                card_exp_year=card.exp_year,
                card_country=card.country or '',
                is_default=not user.saved_payment_methods.exists()
            )
            
            return saved_method
            
        except stripe.error.StripeError as e:
            logger.error(f"Save payment method error: {str(e)}")
            raise Exception(f"Failed to save payment method: {str(e)}")
    
    @staticmethod
    def create_refund(payment, amount=None, reason=""):
        """Create refund for payment"""
        try:
            if not payment.is_refundable:
                raise Exception("Payment is not refundable")
            
            # Calculate refund amount
            refund_amount = amount or payment.get_refundable_amount()
            refund_amount_cents = int(refund_amount * 100)
            
            # Create refund
            refund = stripe.Refund.create(
                payment_intent=payment.stripe_payment_intent_id,
                amount=refund_amount_cents,
                reason='requested_by_customer',
                metadata={
                    'original_payment_id': str(payment.payment_id),
                    'refund_reason': reason
                }
            )
            
            # Update payment record
            payment.refund_amount += refund_amount
            payment.refund_reason = reason
            
            if payment.refund_amount >= payment.amount:
                payment.status = 'refunded'
            else:
                payment.status = 'partially_refunded'
            
            payment.save()
            
            # Create refund payment record
            refund_payment = Payment.objects.create(
                booking=payment.booking,
                customer=payment.customer,
                amount=-refund_amount,  # Negative amount for refund
                currency=payment.currency,
                payment_type='refund',
                stripe_payment_intent_id=refund.payment_intent,
                status='succeeded',
                description=f"Refund for {payment.description}",
                metadata={'original_payment': str(payment.payment_id)}
            )
            
            return refund, refund_payment
            
        except stripe.error.StripeError as e:
            logger.error(f"Refund creation error: {str(e)}")
            raise Exception(f"Refund failed: {str(e)}")
    
    @staticmethod
    def handle_webhook_event(event_data):
        """Handle Stripe webhook events"""
        try:
            event_id = event_data['id']
            event_type = event_data['type']
            
            # Check if we've already processed this event
            webhook_event, created = PaymentWebhookEvent.objects.get_or_create(
                stripe_event_id=event_id,
                defaults={
                    'event_type': event_type,
                    'raw_data': event_data
                }
            )
            
            if not created and webhook_event.processed:
                return True  # Already processed
            
            # Process different event types
            if event_type == 'payment_intent.succeeded':
                StripePaymentService._handle_payment_succeeded(event_data)
            elif event_type == 'payment_intent.payment_failed':
                StripePaymentService._handle_payment_failed(event_data)
            elif event_type == 'charge.dispute.created':
                StripePaymentService._handle_dispute_created(event_data)
            
            # Mark as processed
            webhook_event.processed = True
            webhook_event.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")
            webhook_event.processing_error = str(e)
            webhook_event.save()
            return False
    
    @staticmethod
    def _handle_payment_succeeded(event_data):
        """Handle successful payment"""
        payment_intent = event_data['data']['object']
        payment_intent_id = payment_intent['id']
        
        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)
            payment.status = 'succeeded'
            payment.processed_at = timezone.now()
            payment.save()
            
            # Update booking payment status
            booking = payment.booking
            if payment.payment_type == 'deposit':
                booking.deposit_paid = True
                booking.payment_status = 'deposit_paid'
            elif payment.payment_type in ['remaining', 'full']:
                booking.payment_status = 'fully_paid'
            
            booking.save()
            
            # Send confirmation notifications
            from notifications.tasks import send_payment_confirmation
            send_payment_confirmation.delay(payment.id)
            
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for intent: {payment_intent_id}")
    
    @staticmethod
    def _handle_payment_failed(event_data):
        """Handle failed payment"""
        payment_intent = event_data['data']['object']
        payment_intent_id = payment_intent['id']
        
        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)
            payment.status = 'failed'
            payment.failure_reason = payment_intent.get('last_payment_error', {}).get('message', '')
            payment.save()
            
            # Notify customer of failure
            from notifications.tasks import send_payment_failure_notification
            send_payment_failure_notification.delay(payment.id)
            
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for intent: {payment_intent_id}")
    
    @staticmethod
    def _handle_dispute_created(event_data):
        """Handle payment dispute"""
        charge = event_data['data']['object']
        charge_id = charge['id']
        
        # Find payment and notify admin
        try:
            payment = Payment.objects.get(stripe_charge_id=charge_id)
            
            # Notify admin team
            from notifications.tasks import send_admin_notification
            send_admin_notification.delay(
                'payment_dispute',
                f"Payment dispute created for booking {payment.booking.booking_id}",
                {'payment_id': str(payment.payment_id)}
            )
            
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for charge: {charge_id}")