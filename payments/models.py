from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid


class PaymentManager(models.Manager):
    """
    Custom manager for payments
    """
    def get_successful_payments(self, customer=None, professional=None):
        """Get successful payments with optional filtering"""
        queryset = self.filter(status='completed')
        
        if customer:
            queryset = queryset.filter(customer=customer)
        
        if professional:
            queryset = queryset.filter(booking__professional=professional)
        
        return queryset.select_related('booking', 'customer')
    
    def get_pending_payments(self, customer=None):
        """Get pending payments"""
        queryset = self.filter(status='pending')
        
        if customer:
            queryset = queryset.filter(customer=customer)
        
        return queryset.select_related('booking', 'customer')


class Payment(models.Model):
    """
    Enhanced payment model with server-side calculation support
    """
    PAYMENT_TYPE_CHOICES = [
        ('full', 'Full Payment (100%)'),
        ('partial', 'Partial Payment (50%)'),
        ('remaining', 'Remaining Payment (50%)'),
        ('refund', 'Refund'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]
    
    CURRENCY_CHOICES = [
        ('gbp', 'British Pound'),
        ('aed', 'UAE Dirham'),
        ('usd', 'US Dollar'),
        ('eur', 'Euro'),
    ]
    
    # Basic fields
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
    
    # Payment details (server-calculated)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Server-calculated payment amount"
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='gbp'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='stripe'
    )
    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        default='partial'
    )
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS,
        default='pending',
        db_index=True
    )
    
    # Description and details
    description = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    
    # Stripe-specific fields (don't store customer_id on user model)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    stripe_charge_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_customer_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Stripe customer ID for this transaction only (not stored on user model)"
    )
    payment_method_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Refund tracking
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    refund_reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata for storing server-calculated values and verification
    metadata = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Server-calculated values and verification data"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    objects = PaymentManager()
    
    class Meta:
        indexes = [
            models.Index(fields=['booking', 'payment_type']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['stripe_payment_intent_id']),
            models.Index(fields=['created_at', 'currency']),
            models.Index(fields=['payment_type', 'status']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment {self.payment_id} - {self.get_payment_type_display()} - {self.amount} {self.currency.upper()}"
    
    @property
    def is_successful(self):
        """Check if payment was successful"""
        return self.status == 'completed'
    
    @property
    def is_partial_payment(self):
        """Check if this is a partial payment (50%)"""
        return self.payment_type == 'partial'
    
    @property
    def is_full_payment(self):
        """Check if this is a full payment (100%)"""
        return self.payment_type == 'full'
    
    @property
    def is_remaining_payment(self):
        """Check if this is a remaining payment (50%)"""
        return self.payment_type == 'remaining'
    
    @property
    def is_refunded(self):
        """Check if payment was refunded"""
        return self.status in ['refunded', 'partially_refunded']
    
    @property
    def can_be_refunded(self):
        """Check if payment can be refunded"""
        return self.is_successful and self.stripe_charge_id and self.payment_type != 'refund'
    
    def get_refund_amount(self):
        """Get available refund amount"""
        if not self.can_be_refunded:
            return Decimal('0.00')
        
        return self.amount - self.refund_amount
    
    def verify_server_calculation(self):
        """Verify payment amount matches server calculation"""
        if not self.metadata.get('server_calculated_amount'):
            return False
        
        server_amount = Decimal(self.metadata['server_calculated_amount'])
        return abs(self.amount - server_amount) < Decimal('0.01')
    
    def save(self, *args, **kwargs):
        # Ensure metadata contains server calculation flag
        if not self.metadata.get('server_calculated'):
            self.metadata['server_calculated'] = True
            self.metadata['calculated_at'] = timezone.now().isoformat()
        
        super().save(*args, **kwargs)



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


class PaymentRefund(models.Model):
    """
    Track payment refunds
    """
    refund_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    original_payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='refunds'
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    reason = models.TextField(blank=True)
    
    # Stripe details
    stripe_refund_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('succeeded', 'Succeeded'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['original_payment', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Refund {self.refund_id} - {self.amount} for {self.original_payment.payment_id}"