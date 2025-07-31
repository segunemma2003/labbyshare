from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import os

def booking_picture_upload_path(instance, filename):
    """Generate upload path for booking pictures"""
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    return f'booking_pictures/{instance.booking.booking_id}/{instance.picture_type}/{filename}'


class BookingManager(models.Manager):
    """
    Custom manager for bookings with common queries
    """
    def get_customer_bookings(self, customer, region=None):
        """Get bookings for a customer in a specific region"""
        queryset = self.filter(customer=customer)
        if region:
            queryset = queryset.filter(region=region)
        return queryset.select_related(
            'professional__user', 'service', 'region'
        ).prefetch_related('selected_addons__addon')
    
    def get_professional_bookings(self, professional, region=None):
        """Get bookings for a professional in a specific region"""
        queryset = self.filter(professional=professional)
        if region:
            queryset = queryset.filter(region=region)
        return queryset.select_related(
            'customer', 'service', 'region'
        ).prefetch_related('selected_addons__addon')
    
    def get_upcoming_bookings(self, days=7):
        """Get upcoming bookings within specified days"""
        from datetime import timedelta
        end_date = timezone.now().date() + timedelta(days=days)
        return self.filter(
            scheduled_date__gte=timezone.now().date(),
            scheduled_date__lte=end_date,
            status__in=['confirmed', 'in_progress']
        )


class Booking(models.Model):
    """
    Main booking model handling service appointments
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
        ('no_show', 'No Show'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('deposit_paid', 'Deposit Paid'),
        ('fully_paid', 'Fully Paid'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
    ]
    
    # Unique identifier
    booking_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    
    # Core relationships
    customer = models.ForeignKey(
        'accounts.User', 
        on_delete=models.CASCADE, 
        related_name='bookings'
    )
    professional = models.ForeignKey(
        'professionals.Professional', 
        on_delete=models.CASCADE, 
        related_name='bookings'
    )
    service = models.ForeignKey('services.Service', on_delete=models.CASCADE)
    region = models.ForeignKey('regions.Region', on_delete=models.CASCADE, db_index=True)
    
    # Booking details
    booking_for_self = models.BooleanField(default=True)
    recipient_name = models.CharField(max_length=200, blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    recipient_email = models.EmailField(blank=True)
    
    # Scheduling
    scheduled_date = models.DateField(db_index=True)
    scheduled_time = models.TimeField(db_index=True)
    duration_minutes = models.IntegerField()
    
    # Address/Location
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    location_notes = models.TextField(blank=True)
    
    # Pricing breakdown
    base_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    addon_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    tax_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        null=True, blank=True  # Allow null temporarily during creation
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending', 
        db_index=True
    )
    payment_status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUS_CHOICES, 
        default='pending',
        db_index=True
    )
    
    # Deposit settings
    deposit_required = models.BooleanField(default=True)
    deposit_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=20.00,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    deposit_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Notes and special instructions
    customer_notes = models.TextField(blank=True)
    professional_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    # Reminder tracking
    reminder_24h_sent = models.BooleanField(default=False)
    reminder_3h_sent = models.BooleanField(default=False)
    reminder_1h_sent = models.BooleanField(default=False)
    
    # Cancellation details
    cancelled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_bookings'
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    objects = BookingManager()
    
    class Meta:
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['professional', 'scheduled_date']),
            models.Index(fields=['region', 'scheduled_date']),
            models.Index(fields=['status', 'scheduled_date']),
            models.Index(fields=['payment_status', 'status']),
            models.Index(fields=['scheduled_date', 'scheduled_time']),
            models.Index(fields=['created_at', 'region']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Booking {self.booking_id} - {self.service.name}"
    
    def save(self, *args, **kwargs):
        # Calculate total amount if not set
        if self.total_amount is None:
            self.total_amount = self.calculate_total()
        
        # Calculate deposit amount if not set and deposit is required
        if not self.deposit_amount and self.deposit_required and self.total_amount:
            self.deposit_amount = (self.total_amount * self.deposit_percentage) / 100
        
        super().save(*args, **kwargs)
    
    @property
    def is_upcoming(self):
        """Check if booking is upcoming"""
        booking_datetime = timezone.datetime.combine(self.scheduled_date, self.scheduled_time)
        if timezone.is_naive(booking_datetime):
            booking_datetime = timezone.make_aware(booking_datetime)
        return booking_datetime > timezone.now()
    
    @property
    def can_be_cancelled(self):
        """Check if booking can be cancelled"""
        if self.status in ['completed', 'cancelled', 'no_show']:
            return False
        
        # Check if it's within cancellation window (e.g., 24 hours)
        booking_datetime = timezone.datetime.combine(self.scheduled_date, self.scheduled_time)
        if timezone.is_naive(booking_datetime):
            booking_datetime = timezone.make_aware(booking_datetime)
        
        cancellation_deadline = booking_datetime - timezone.timedelta(hours=24)
        return timezone.now() < cancellation_deadline
    
    def calculate_total(self):
        """Calculate and return total amount"""
        total = (
            (self.base_amount or Decimal('0.00')) + 
            (self.addon_amount or Decimal('0.00')) + 
            (self.tax_amount or Decimal('0.00')) - 
            (self.discount_amount or Decimal('0.00'))
        )
        return total
    
    @property
    def remaining_payment_amount(self):
        """Get remaining payment amount (server-calculated)"""
        if self.payment_status == 'partial_paid':
            return self.total_amount - self.deposit_amount
        return Decimal('0.00')
    
    @property
    def next_payment_amount(self):
        """Get next payment amount required"""
        if self.payment_status == 'pending':
            if self.deposit_required:
                return self.deposit_amount
            else:
                return self.total_amount
        elif self.payment_status == 'partial_paid':
            return self.remaining_payment_amount
        return Decimal('0.00')


class BookingAddOn(models.Model):
    """
    Through model for booking add-ons
    """
    booking = models.ForeignKey(
        Booking, 
        on_delete=models.CASCADE, 
        related_name='selected_addons'
    )
    addon = models.ForeignKey('services.AddOn', on_delete=models.CASCADE)
    quantity = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    price_at_booking = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    class Meta:
        unique_together = ['booking', 'addon']
        indexes = [
            models.Index(fields=['booking']),
        ]
    
    def __str__(self):
        return f"{self.booking.booking_id} - {self.addon.name} x{self.quantity}"
    
    @property
    def total_price(self):
        return self.price_at_booking * self.quantity


class BookingStatusHistory(models.Model):
    """
    Track booking status changes
    """
    booking = models.ForeignKey(
        Booking, 
        on_delete=models.CASCADE, 
        related_name='status_history'
    )
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['booking', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.booking.booking_id}: {self.previous_status} → {self.new_status}"


class Review(models.Model):
    """
    Customer reviews for completed bookings
    """
    booking = models.OneToOneField(
        Booking, 
        on_delete=models.CASCADE, 
        related_name='review'
    )
    customer = models.ForeignKey(
        'accounts.User', 
        on_delete=models.CASCADE,
        related_name='reviews_given'
    )
    professional = models.ForeignKey(
        'professionals.Professional', 
        on_delete=models.CASCADE,
        related_name='reviews_received'
    )
    service = models.ForeignKey(
        'services.Service', 
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    
    # Review ratings
    overall_rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        db_index=True
    )
    service_rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        null=True, blank=True
    )
    professional_rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        null=True, blank=True
    )
    value_rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        null=True, blank=True
    )
    
    # Review content
    comment = models.TextField(blank=True)
    would_recommend = models.BooleanField(default=True)
    
    # Review status
    is_verified = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    
    # Professional response
    professional_response = models.TextField(blank=True)
    response_date = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['professional', 'overall_rating']),
            models.Index(fields=['service', 'overall_rating']),
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['is_published', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer.get_full_name()} → {self.professional.user.get_full_name()} ({self.overall_rating}★)"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update professional and service ratings
        if self.is_published:
            self.professional.update_rating()


class BookingReschedule(models.Model):
    """
    Track booking reschedule requests and history
    """
    booking = models.ForeignKey(
        Booking, 
        on_delete=models.CASCADE, 
        related_name='reschedule_requests'
    )
    requested_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='reschedule_requests'
    )
    
    # Original scheduling
    original_date = models.DateField()
    original_time = models.TimeField()
    
    # Requested new scheduling
    requested_date = models.DateField()
    requested_time = models.TimeField()
    
    # Request details
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('expired', 'Expired'),
        ],
        default='pending'
    )
    
    # Response details
    responded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reschedule_responses'
    )
    response_reason = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # Auto-expire if not responded
    
    class Meta:
        indexes = [
            models.Index(fields=['booking', 'status']),
            models.Index(fields=['requested_by', 'created_at']),
            models.Index(fields=['status', 'expires_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Reschedule request for {self.booking.booking_id}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at and self.status == 'pending'


class BookingMessage(models.Model):
    """
    Messages between customer and professional regarding a booking
    """
    booking = models.ForeignKey(
        Booking, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    sender = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='sent_booking_messages'
    )
    
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    # Message metadata
    is_system_message = models.BooleanField(default=False)
    message_type = models.CharField(
        max_length=20,
        choices=[
            ('text', 'Text'),
            ('status_update', 'Status Update'),
            ('reschedule', 'Reschedule'),
            ('cancellation', 'Cancellation'),
        ],
        default='text'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['booking', 'created_at']),
            models.Index(fields=['sender', 'is_read']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Message for {self.booking.booking_id} from {self.sender.get_full_name()}"


class BookingPicture(models.Model):
    """
    Pictures for bookings - before and after service completion
    """
    PICTURE_TYPE_CHOICES = [
        ('before', 'Before'),
        ('after', 'After'),
    ]
    
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='pictures'
    )
    picture_type = models.CharField(
        max_length=10,
        choices=PICTURE_TYPE_CHOICES,
        db_index=True
    )
    image = models.ImageField(
        upload_to=booking_picture_upload_path,
        help_text="Upload image file (JPEG, PNG, WebP)"
    )
    caption = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional caption for the picture"
    )
    
    # Metadata
    uploaded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='uploaded_booking_pictures'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Image metadata (optional, can be populated automatically)
    file_size = models.PositiveIntegerField(null=True, blank=True)  # in bytes
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['booking', 'picture_type']),
            models.Index(fields=['uploaded_by', 'uploaded_at']),
            models.Index(fields=['picture_type', 'uploaded_at']),
        ]
        ordering = ['picture_type', 'uploaded_at']
        
        # Ensure proper constraints for picture limits
        constraints = [
            models.UniqueConstraint(
                fields=['booking', 'picture_type', 'image'],
                name='unique_booking_picture'
            )
        ]
    
    def __str__(self):
        return f"{self.get_picture_type_display()} picture for {self.booking.booking_id}"
    
    def save(self, *args, **kwargs):
        # Populate image metadata if not set
        if self.image and not self.file_size:
            try:
                self.file_size = self.image.size
                # If PIL is available, get image dimensions
                from PIL import Image
                img = Image.open(self.image)
                self.width, self.height = img.size
            except (ImportError, Exception):
                pass
        
        super().save(*args, **kwargs)
    
    @property
    def file_size_mb(self):
        """Get file size in MB"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None