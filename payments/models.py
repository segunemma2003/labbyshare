from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid


class PaymentManager(models.Manager):
    """
    Custom manager for payments
    """
    def get_successful_payments(self, customer=None, professional=None):
        """Get successful payments with optional filtering"""
        queryset = self.filter(status='succeeded')
        
        if customer:
            queryset = queryset.filter(customer=customer)
        
        if professional:
            queryset = queryset.filter(booking__professional=professional)
        
        return queryset.select_related('booking', 'customer')


class Payment(models.Model):
    """
    Payment records with Stripe integration
    """
    PAYMENT_TYPES = [
        ('deposit', 'Deposit'),
        ('remaining', 'Remaining Balance'),
        ('full', 'Full Payment'),
        ('refund', 'Refund')
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded')
    ]
    
    # Identifiers
    payment_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    booking = models.ForeignKey(
        'bookings.Booking', 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    customer = models.ForeignKey(
        'accounts.User', 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    
    # Payment details
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='USD')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    description = models.CharField(max_length=255, blank=True)
    
    # Stripe details
    stripe_payment_intent_id = models.CharField(max_length=200, unique=True, null=True)
    stripe_charge_id = models.CharField(max_length=200, blank=True)
    stripe_customer_id = models.CharField(max_length=200, blank=True)
    payment_method_id = models.CharField(max_length=200, blank=True)
    
    # Status and metadata
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending', db_index=True)
    failure_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Refund details
    refund_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00
    )
    refund_reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    objects = PaymentManager()
    
    class Meta:
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['booking', 'payment_type']),
            models.Index(fields=['stripe_payment_intent_id']),
            models.Index(fields=['status', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment {self.payment_id} - {self.amount} {self.currency}"
    
    @property
    def is_refundable(self):
        """Check if payment can be refunded"""
        return (
            self.status == 'succeeded' and 
            self.refund_amount < self.amount and
            self.payment_type != 'refund'
        )
    
    def get_refundable_amount(self):
        """Get amount that can still be refunded"""
        return self.amount - self.refund_amount


class SavedPaymentMethod(models.Model):
    """
    Customer's saved payment methods from Stripe
    """
    customer = models.ForeignKey(
        'accounts.User', 
        on_delete=models.CASCADE, 
        related_name='saved_payment_methods'
    )
    
    # Stripe details
    stripe_payment_method_id = models.CharField(max_length=200, unique=True)
    stripe_customer_id = models.CharField(max_length=200)
    
    # Card details (for display)
    card_brand = models.CharField(max_length=20)  # visa, mastercard, etc.
    card_last_four = models.CharField(max_length=4)
    card_exp_month = models.IntegerField()
    card_exp_year = models.IntegerField()
    card_country = models.CharField(max_length=2, blank=True)
    
    # Settings
    is_default = models.BooleanField(default=False)
    nickname = models.CharField(max_length=50, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['customer', 'is_default']),
            models.Index(fields=['stripe_customer_id']),
        ]
    
    def __str__(self):
        return f"{self.card_brand.title()} ending in {self.card_last_four}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default payment method per customer
        if self.is_default:
            SavedPaymentMethod.objects.filter(
                customer=self.customer, 
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        
        super().save(*args, **kwargs)


class PaymentWebhookEvent(models.Model):
    """
    Track Stripe webhook events
    """
    stripe_event_id = models.CharField(max_length=200, unique=True)
    event_type = models.CharField(max_length=100)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    
    # Related payment (if applicable)
    payment = models.ForeignKey(
        Payment, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    raw_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['stripe_event_id']),
            models.Index(fields=['event_type', 'processed']),
        ]
    
    def __str__(self):
        return f"Webhook {self.stripe_event_id} - {self.event_type}"
