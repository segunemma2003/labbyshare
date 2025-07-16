import stripe
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple
import logging
import os

from .models import Payment, SavedPaymentMethod, PaymentWebhookEvent, PaymentRefund

logger = logging.getLogger(__name__)

# Debug: Print a masked version of the Stripe secret key
key = os.environ.get('STRIPE_SECRET_KEY') or getattr(settings, 'STRIPE_SECRET_KEY', None)
if key:
    print(f"STRIPE_SECRET_KEY loaded: {key[:6]}...{key[-4:]}")
else:
    print("STRIPE_SECRET_KEY is NOT set!")

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripePaymentService:
    """
    Enhanced Stripe payment service with full/deposit payment support
    """
    
    @staticmethod
    def create_customer(user) -> stripe.Customer:
        """
        Create Stripe customer (don't store ID on user model)
        """
        try:
            # Always create a new customer for each transaction
            # This ensures no sensitive data is stored on user model
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name(),
                phone=getattr(user, 'phone', None),
                metadata={
                    'user_id': str(user.id),
                    'user_type': getattr(user, 'user_type', 'customer'),
                    'region': getattr(user, 'region', 'UK')
                }
            )
            
            logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
            return customer
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer for user {user.id}: {str(e)}")
            raise e
    
    @staticmethod
    def create_payment_intent(
        booking,
        amount: Decimal,
        payment_type: str,
        customer_id: str = None,
        payment_method_id: str = None
    ) -> Tuple[stripe.PaymentIntent, Payment]:
        """
        Create a Stripe payment intent for booking payment
        
        Args:
            booking: The booking instance
            amount: Amount to charge (calculated server-side)
            payment_type: 'full' or 'partial'
            customer_id: Stripe customer ID
            payment_method_id: Stripe payment method ID (optional)
            
        Returns:
            Tuple of (PaymentIntent, Payment record)
        """
        try:
            # Calculate amount in cents (Stripe uses cents)
            amount_cents = int(amount * 100)
            
            # Get currency for region
            currency = StripePaymentService._get_currency_for_region(booking.region)
            
            # Create payment intent metadata with server-calculated values
            intent_metadata = {
                'booking_id': str(booking.booking_id),
                'customer_id': str(booking.customer.id),
                'professional_id': str(booking.professional.id),
                'service_id': str(booking.service.id),
                'region_id': str(booking.region.id),
                'payment_type': payment_type,
                
                # Server-calculated amounts (for verification)
                'base_amount': str(booking.base_amount),
                'addon_amount': str(booking.addon_amount),
                'tax_amount': str(booking.tax_amount),
                'discount_amount': str(booking.discount_amount),
                'total_amount': str(booking.total_amount),
                'deposit_amount': str(booking.deposit_amount),
                'deposit_percentage': str(booking.deposit_percentage),
                'amount_being_charged': str(amount),
                
                # Verification hash (to prevent tampering)
                'verification_hash': StripePaymentService._generate_verification_hash(booking, amount)
            }
            
            # Create payment intent data
            intent_data = {
                'amount': amount_cents,
                'currency': currency,
                'automatic_payment_methods': {
                    'enabled': True,
                },
                'metadata': intent_metadata
            }
            
            # Add customer if provided
            if customer_id:
                intent_data['customer'] = customer_id
            
            # Add payment method if provided
            if payment_method_id:
                intent_data['payment_method'] = payment_method_id
                intent_data['confirmation_method'] = 'manual'
                intent_data['confirm'] = True
            
            # Set description based on payment type
            service_name = booking.service.name
            if payment_type == 'full':
                intent_data['description'] = f"Full payment for {service_name} - {booking.scheduled_date}"
            else:
                intent_data['description'] = f"Partial payment (50%) for {service_name} - {booking.scheduled_date}"
            
            # Create the payment intent
            payment_intent = stripe.PaymentIntent.create(**intent_data)
            
            # Create payment record in database
            payment = Payment.objects.create(
                booking=booking,
                customer=booking.customer,
                amount=amount,
                currency=currency,
                payment_method='stripe',
                payment_type=payment_type,
                stripe_payment_intent_id=payment_intent.id,
                stripe_customer_id=customer_id,
                payment_method_id=payment_method_id,
                status='pending',
                description=intent_data['description'],
                metadata={
                    'stripe_client_secret': payment_intent.client_secret,
                    'payment_type': payment_type,
                    'server_calculated_amount': str(amount),
                    'verification_hash': intent_metadata['verification_hash']
                }
            )
            
            logger.info(f"Created payment intent {payment_intent.id} for booking {booking.booking_id} - Amount: {amount} {currency}")
            return payment_intent, payment
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            raise e
        
    @staticmethod
    def _generate_verification_hash(booking, amount):
        """Generate verification hash to prevent payment tampering"""
        import hashlib
        data = f"{booking.booking_id}:{amount}:{booking.total_amount}:{booking.deposit_amount}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    @staticmethod
    def confirm_payment_intent(payment_intent_id: str, payment_method_id: str = None) -> stripe.PaymentIntent:
        """
        Confirm a payment intent
        
        Args:
            payment_intent_id: Stripe payment intent ID
            payment_method_id: Stripe payment method ID (optional)
            
        Returns:
            PaymentIntent object
        """
        try:
            confirm_params = {}
            
            if payment_method_id:
                confirm_params['payment_method'] = payment_method_id
            
            payment_intent = stripe.PaymentIntent.confirm(
                payment_intent_id,
                **confirm_params
            )
            
            return payment_intent
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment intent: {str(e)}")
            raise e
    
    @staticmethod
    def handle_payment_success(payment_intent_id: str) -> Dict:
        """
        Handle successful payment and update booking status
        """
        try:
            # Retrieve the payment intent
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            # Find the payment record
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)
            booking = payment.booking
            
            # Verify payment amount matches server calculation
            server_amount = Decimal(payment_intent.metadata.get('amount_being_charged', '0'))
            stripe_amount = Decimal(payment_intent.amount) / 100
            
            if abs(server_amount - stripe_amount) > Decimal('0.01'):
                logger.error(f"Payment amount mismatch for {payment_intent_id}: server={server_amount}, stripe={stripe_amount}")
                raise ValueError("Payment amount verification failed")
            
            # Update payment status
            payment.status = 'completed'
            payment.stripe_charge_id = payment_intent.latest_charge
            payment.processed_at = timezone.now()
            payment.save()
            
            # Update booking payment status based on payment type
            if payment.payment_type == 'full':
                booking.payment_status = 'fully_paid'
            else:  # partial payment
                booking.payment_status = 'deposit_paid'
            
            booking.save()
            
            # Send confirmation notifications
            try:
                from notifications.tasks import send_booking_notification
                send_booking_notification.delay(
                    booking.id,
                    'payment_confirmed',
                    [booking.customer.id, booking.professional.user.id]
                )
            except Exception as e:
                logger.error(f"Failed to send payment confirmation notification: {str(e)}")
            
            logger.info(f"Payment confirmed for booking {booking.booking_id} - Type: {payment.payment_type}")
            return {
                'success': True,
                'payment_id': str(payment.payment_id),
                'booking_id': str(booking.booking_id),
                'payment_type': payment.payment_type,
                'amount': str(payment.amount),
                'booking_status': booking.status,
                'payment_status': booking.payment_status
            }
            
        except Payment.DoesNotExist:
            logger.error(f"Payment record not found for intent {payment_intent_id}")
            return {'success': False, 'error': 'Payment record not found'}
        except Exception as e:
            logger.error(f"Error handling payment success: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def handle_payment_failure(payment_intent_id: str) -> Dict:
        """
        Handle failed payment
        
        Args:
            payment_intent_id: Stripe payment intent ID
            
        Returns:
            Dict with failure details
        """
        try:
            # Retrieve the payment intent
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            # Find the payment record
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)
            booking = payment.booking
            
            # Update payment status
            payment.status = 'failed'
            payment.failure_reason = payment_intent.last_payment_error.message if payment_intent.last_payment_error else 'Payment failed'
            payment.processed_at = timezone.now()
            payment.save()
            
            # Update booking payment status
            booking.payment_status = 'failed'
            booking.save()
            
            # Send failure notification
            try:
                from notifications.tasks import send_booking_notification
                send_booking_notification.delay(
                    booking.id,
                    'payment_failed',
                    [booking.customer.id]
                )
            except Exception as e:
                logger.error(f"Failed to send payment failure notification: {str(e)}")
            
            logger.warning(f"Payment failed for booking {booking.booking_id}: {payment.failure_reason}")
            return {
                'success': False,
                'error': payment.failure_reason,
                'payment_id': payment.id,
                'booking_id': str(booking.booking_id)
            }
            
        except Payment.DoesNotExist:
            logger.error(f"Payment record not found for intent {payment_intent_id}")
            return {'success': False, 'error': 'Payment record not found'}
        except Exception as e:
            logger.error(f"Error handling payment failure: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def process_remaining_payment(booking_id: str) -> Tuple[stripe.PaymentIntent, Payment]:
        """
        Process remaining payment for a booking that had partial payment
        """
        try:
            from bookings.models import Booking
            booking = Booking.objects.get(booking_id=booking_id)
            
            # Check if booking has partial payment completed
            if booking.payment_status != 'deposit_paid':
                raise ValueError("Booking must have partial payment completed to process remaining payment")
            
            # Calculate remaining amount (SERVER-SIDE CALCULATION)
            remaining_amount = booking.total_amount - booking.deposit_amount
            
            if remaining_amount <= 0:
                raise ValueError("No remaining amount to pay")
            
            # Create new Stripe customer for this transaction
            customer = StripePaymentService.create_customer(booking.customer)
            
            # Create payment intent for remaining amount
            payment_intent, payment = StripePaymentService.create_payment_intent(
                booking=booking,
                amount=remaining_amount,
                payment_type='remaining',
                customer_id=customer.id
            )
            
            logger.info(f"Created remaining payment intent for booking {booking.booking_id} - Amount: {remaining_amount}")
            return payment_intent, payment
            
        except Exception as e:
            logger.error(f"Error processing remaining payment: {str(e)}")
            raise e
    
    @staticmethod
    def create_refund(payment_id: int, amount: Decimal = None, reason: str = None) -> Dict:
        """
        Create a refund for a payment
        
        Args:
            payment_id: Payment ID
            amount: Amount to refund (None for full refund)
            reason: Refund reason
            
        Returns:
            Dict with refund details
        """
        try:
            payment = Payment.objects.get(id=payment_id)
            
            if not payment.stripe_charge_id:
                raise ValueError("No charge ID available for refund")
            
            # Calculate refund amount
            refund_amount = amount or payment.get_refund_amount()
            
            if refund_amount <= 0:
                raise ValueError("No amount available for refund")
            
            # Create refund in Stripe
            refund_data = {
                'charge': payment.stripe_charge_id,
                'amount': int(refund_amount * 100),  # Convert to cents
                'metadata': {
                    'payment_id': payment_id,
                    'booking_id': str(payment.booking.booking_id),
                    'reason': reason or 'Customer request'
                }
            }
            
            refund = stripe.Refund.create(**refund_data)
            
            # Create refund record
            payment_refund = PaymentRefund.objects.create(
                original_payment=payment,
                amount=refund_amount,
                reason=reason or 'Customer request',
                stripe_refund_id=refund.id,
                status='succeeded' if refund.status == 'succeeded' else 'pending'
            )
            
            # Update payment status
            payment.refund_amount += refund_amount
            
            if payment.refund_amount >= payment.amount:
                payment.status = 'refunded'
                payment.booking.payment_status = 'refunded'
            else:
                payment.status = 'partially_refunded'
            
            payment.refunded_at = timezone.now()
            payment.save()
            payment.booking.save()
            
            logger.info(f"Created refund {refund.id} for payment {payment_id}")
            return {
                'success': True,
                'refund_id': refund.id,
                'amount': refund_amount,
                'status': refund.status,
                'payment_refund_id': payment_refund.id
            }
            
        except Payment.DoesNotExist:
            logger.error(f"Payment {payment_id} not found")
            return {'success': False, 'error': 'Payment not found'}
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating refund: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error creating refund: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def save_payment_method(customer_id: str, payment_method_id: str, user) -> SavedPaymentMethod:
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
            
            logger.info(f"Saved payment method {payment_method_id} for user {user.id}")
            return saved_method
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error saving payment method: {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Error saving payment method: {str(e)}")
            raise e
    
    @staticmethod
    def handle_webhook_event(event_data: Dict) -> Dict:
        """
        Handle Stripe webhook events
        
        Args:
            event_data: Webhook event data
            
        Returns:
            Dict with processing result
        """
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
                return {'success': True, 'message': 'Event already processed'}
            
            # Process different event types
            result = {'success': True, 'message': 'Event processed'}
            
            if event_type == 'payment_intent.succeeded':
                result = StripePaymentService.handle_payment_success(event_data['data']['object']['id'])
            elif event_type == 'payment_intent.payment_failed':
                result = StripePaymentService.handle_payment_failure(event_data['data']['object']['id'])
            elif event_type == 'charge.dispute.created':
                result = StripePaymentService._handle_dispute_created(event_data)
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                result = {'success': True, 'message': 'Event type not handled'}
            
            # Mark as processed
            webhook_event.processed = True
            webhook_event.save()
            
            return result
            
        except Exception as e:
            logger.error(f"Webhook processing error: {str(e)}")
            if 'webhook_event' in locals():
                webhook_event.processing_error = str(e)
                webhook_event.save()
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _handle_dispute_created(event_data: Dict) -> Dict:
        """Handle payment dispute"""
        try:
            charge = event_data['data']['object']
            charge_id = charge['id']
            
            # Find payment and notify admin
            payment = Payment.objects.get(stripe_charge_id=charge_id)
            
            # Notify admin team
            try:
                from notifications.tasks import send_booking_notification
                send_booking_notification.delay(
                    payment.booking.id,
                    'payment_dispute',
                    [payment.customer.id]  # Also notify customer
                )
            except Exception as e:
                logger.error(f"Failed to send dispute notification: {str(e)}")
            
            logger.warning(f"Payment dispute created for booking {payment.booking.booking_id}")
            return {'success': True, 'message': 'Dispute handled'}
            
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for charge: {charge_id}")
            return {'success': False, 'error': 'Payment not found'}
        except Exception as e:
            logger.error(f"Error handling dispute: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _get_currency_for_region(region) -> str:
        """Get currency code for region"""
        currency_map = {
            'UK': 'gbp',
            'UAE': 'aed',
        }
        return currency_map.get(region.code, 'gbp')  # Default to GBP