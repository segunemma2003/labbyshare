from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
import uuid


class User(AbstractUser):
    """
    Optimized User model with proper indexing for millions of users
    """
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
    
    # Core identification
    uid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, db_index=True)  # Indexed for search
    last_name = models.CharField(max_length=150, db_index=True)   # Indexed for search
    
    # User type and permissions
    user_type = models.CharField(
        max_length=20, 
        choices=USER_TYPE_CHOICES, 
        default='customer', 
        db_index=True
    )
    
    # Contact information
    phone_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$')],
        blank=True, 
        null=True,
        db_index=True
    )
    
    # Profile information
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    
    # Region relationship - critical for multi-location support
    current_region = models.ForeignKey(
        'regions.Region', 
        on_delete=models.SET_NULL, 
        null=True,
        db_index=True,
        related_name='current_users'
    )
    
    # OAuth fields for social authentication
    google_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    apple_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    firebase_uid = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    
    # Profile completion tracking
    profile_completed = models.BooleanField(default=False, db_index=True)
    
    # Enhanced timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_region = models.ForeignKey(
        'regions.Region', 
        related_name='last_login_users', 
        on_delete=models.SET_NULL, 
        null=True
    )
    
    # Account status
    is_verified = models.BooleanField(default=False, db_index=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    class Meta:
        # Composite indexes for high-performance queries
        indexes = [
            models.Index(fields=['email', 'current_region']),
            models.Index(fields=['user_type', 'is_active']),
            models.Index(fields=['google_id'], condition=models.Q(google_id__isnull=False), name='idx_user_google_id_not_null'), 
            models.Index(fields=['apple_id'], condition=models.Q(apple_id__isnull=False), name='idx_user_apple_id_not_null'),
            models.Index(fields=['firebase_uid'], condition=models.Q(firebase_uid__isnull=False), name='idx_user_firebase_uid_not_null'),
            models.Index(fields=['created_at', 'current_region']),
            models.Index(fields=['first_name', 'last_name']),  # For name searches
            models.Index(fields=['is_verified', 'user_type']),
        ]
        
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
        
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class OTPVerification(models.Model):
    """
    OTP verification for password reset and email verification
    """
    PURPOSE_CHOICES = [
        ('password_reset', 'Password Reset'),
        ('email_verification', 'Email Verification')
    ]
    
    email = models.EmailField(db_index=True)
    otp = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)  # Indexed for cleanup queries
    used = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['email', 'purpose', 'used']),
            models.Index(fields=['expires_at', 'used']),  # For cleanup
        ]
        
    def is_expired(self):
        return timezone.now() > self.expires_at
        
    def __str__(self):
        return f"OTP for {self.email} - {self.purpose}"