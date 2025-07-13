from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal
import uuid

class Region(models.Model):
    code = models.CharField(max_length=10, unique=True, db_index=True)  # UK, UAE
    name = models.CharField(max_length=100)
    currency = models.CharField(max_length=10, default='USD')
    timezone = models.CharField(max_length=50, default='UTC')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['code', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"

class User(AbstractUser):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('P', 'Prefer not to say')
    ]
    
    USER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('professional', 'Professional'),
        ('admin', 'Admin'),
        ('super_admin', 'Super Admin')
    ]
    
    uid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='customer', db_index=True)
    phone_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$')],
        blank=True, null=True
    )
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    current_region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, db_index=True)
    
    # OAuth fields
    google_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    apple_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    firebase_uid = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    
    # Profile completion
    profile_completed = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_region = models.ForeignKey(
        Region, 
        related_name='last_login_users', 
        on_delete=models.SET_NULL, 
        null=True
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    class Meta:
        indexes = [
            models.Index(fields=['email', 'current_region']),
            models.Index(fields=['google_id']),
            models.Index(fields=['apple_id']),
            models.Index(fields=['firebase_uid']),
            models.Index(fields=['created_at']),
        ]

class OTPVerification(models.Model):
    email = models.EmailField(db_index=True)
    otp = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=[
        ('password_reset', 'Password Reset'),
        ('email_verification', 'Email Verification')
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['email', 'purpose', 'used']),
            models.Index(fields=['expires_at']),
        ]

class Category(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='category_icons/', blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, db_index=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['name', 'region']
        indexes = [
            models.Index(fields=['region', 'is_active', 'sort_order']),
        ]
        verbose_name_plural = "Categories"
    
    def __str__(self):
        return f"{self.name} - {self.region.code}"

class Service(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='services')
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.IntegerField()  # Service duration
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['name', 'category']
        indexes = [
            models.Index(fields=['category', 'is_active', 'sort_order']),
            models.Index(fields=['base_price']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.category.name}"

class AddOn(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='addons')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['name', 'category']
        indexes = [
            models.Index(fields=['category', 'is_active']),
        ]

class Professional(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='professional_profile')
    bio = models.TextField(blank=True)
    experience_years = models.IntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.IntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    regions = models.ManyToManyField(Region, related_name='professionals')
    services = models.ManyToManyField(Service, related_name='professionals')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['is_active', 'rating']),
            models.Index(fields=['is_verified', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Professional"

class ProfessionalAvailability(models.Model):
    WEEKDAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ]
    
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='availability')
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['professional', 'weekday', 'start_time']
        indexes = [
            models.Index(fields=['professional', 'weekday', 'is_active']),
        ]

class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled')
    ]
    
    booking_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='bookings')
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    
    # Booking details
    booking_for_self = models.BooleanField(default=True)
    recipient_name = models.CharField(max_length=200, blank=True)  # If booking for someone else
    recipient_phone = models.CharField(max_length=20, blank=True)
    
    # Timing
    scheduled_date = models.DateField(db_index=True)
    scheduled_time = models.TimeField()
    duration_minutes = models.IntegerField()
    
    # Pricing
    base_amount = models.DecimalField(max_digits=10, decimal_places=2)
    addon_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status and payments
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    payment_status = models.CharField(max_length=20, default='pending')
    deposit_paid = models.BooleanField(default=False)
    
    # Metadata
    region = models.ForeignKey(Region, on_delete=models.CASCADE, db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Notifications
    reminder_24h_sent = models.BooleanField(default=False)
    reminder_3h_sent = models.BooleanField(default=False)
    reminder_1h_sent = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['professional', 'scheduled_date']),
            models.Index(fields=['region', 'scheduled_date']),
            models.Index(fields=['status', 'scheduled_date']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Booking {self.booking_id} - {self.service.name}"

class BookingAddOn(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='selected_addons')
    addon = models.ForeignKey(AddOn, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price_at_booking = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        unique_together = ['booking', 'addon']

class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name='reviews_received')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='reviews')
    
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])  # 1-5 stars
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['professional', 'rating']),
            models.Index(fields=['service', 'rating']),
            models.Index(fields=['created_at']),
        ]

class Payment(models.Model):
    PAYMENT_TYPES = [
        ('deposit', 'Deposit'),
        ('remaining', 'Remaining Balance'),
        ('full', 'Full Payment'),
        ('refund', 'Refund')
    ]
    
    payment_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    
    # Stripe details
    stripe_payment_intent_id = models.CharField(max_length=200, blank=True)
    stripe_charge_id = models.CharField(max_length=200, blank=True)
    payment_method_id = models.CharField(max_length=200, blank=True)
    
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['booking', 'payment_type']),
        ]

class SavedPaymentMethod(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_payment_methods')
    stripe_payment_method_id = models.CharField(max_length=200, unique=True)
    card_brand = models.CharField(max_length=20)
    last_four = models.CharField(max_length=4)
    exp_month = models.IntegerField()
    exp_year = models.IntegerField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['customer', 'is_default']),
        ]

class AdminChatMessage(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File')
    ]
    
    conversation_id = models.UUIDField(db_index=True)  # Group messages by conversation
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_messages', null=True, blank=True)
    
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    file_url = models.URLField(blank=True)
    
    is_from_admin = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['conversation_id', 'created_at']),
            models.Index(fields=['customer', 'is_read']),
        ]

# Settings and Configuration Models
class RegionalPricing(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='regional_pricing')
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['service', 'region']
        indexes = [
            models.Index(fields=['region', 'is_active']),
        ]

class AppSettings(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['key', 'region']),
        ]