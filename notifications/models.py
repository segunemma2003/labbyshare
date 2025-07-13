from django.db import models
from django.utils import timezone
import uuid


class NotificationManager(models.Manager):
    """
    Custom manager for notifications
    """
    def get_user_notifications(self, user, unread_only=False):
        """Get notifications for a user"""
        queryset = self.filter(user=user).order_by('-created_at')
        
        if unread_only:
            queryset = queryset.filter(is_read=False)
        
        return queryset
    
    def mark_all_read(self, user):
        """Mark all notifications as read for a user"""
        return self.filter(user=user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )


class Notification(models.Model):
    """
    In-app notifications for users
    """
    NOTIFICATION_TYPES = [
        ('booking_created', 'Booking Created'),
        ('booking_confirmed', 'Booking Confirmed'),
        ('booking_cancelled', 'Booking Cancelled'),
        ('booking_reminder', 'Booking Reminder'),
        ('booking_completed', 'Booking Completed'),
        ('payment_succeeded', 'Payment Succeeded'),
        ('payment_failed', 'Payment Failed'),
        ('review_received', 'Review Received'),
        ('professional_verified', 'Professional Verified'),
        ('professional_rejected', 'Professional Rejected'),
        ('system_announcement', 'System Announcement'),
        ('promotion', 'Promotion'),
    ]
    
    notification_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Content
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, db_index=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    action_url = models.URLField(blank=True)
    
    # Related objects
    related_booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    related_payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    # Status
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Push notification tracking
    push_sent = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    
    # Metadata
    data = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    objects = NotificationManager()
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
            models.Index(fields=['notification_type', 'created_at']),
            models.Index(fields=['user', 'notification_type']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.get_full_name()}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class NotificationPreference(models.Model):
    """
    User notification preferences
    """
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Push notification preferences
    booking_updates_push = models.BooleanField(default=True)
    payment_updates_push = models.BooleanField(default=True)
    reminders_push = models.BooleanField(default=True)
    promotions_push = models.BooleanField(default=False)
    
    # Email notification preferences
    booking_updates_email = models.BooleanField(default=True)
    payment_updates_email = models.BooleanField(default=True)
    reminders_email = models.BooleanField(default=False)
    promotions_email = models.BooleanField(default=False)
    
    # SMS preferences
    booking_updates_sms = models.BooleanField(default=False)
    reminders_sms = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferences for {self.user.get_full_name()}"


class PushNotificationDevice(models.Model):
    """
    User devices for push notifications
    """
    PLATFORM_CHOICES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web'),
    ]
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='push_devices'
    )
    
    device_token = models.CharField(max_length=500, unique=True)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    app_version = models.CharField(max_length=20, blank=True)
    device_info = models.JSONField(default=dict, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['device_token']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.platform}"
