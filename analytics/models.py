from django.db import models
from django.utils import timezone


class AnalyticsEvent(models.Model):
    """
    Track user events for analytics
    """
    EVENT_TYPES = [
        ('page_view', 'Page View'),
        ('search', 'Search'),
        ('booking_started', 'Booking Started'),
        ('booking_completed', 'Booking Completed'),
        ('payment_initiated', 'Payment Initiated'),
        ('payment_completed', 'Payment Completed'),
        ('user_registration', 'User Registration'),
        ('professional_registration', 'Professional Registration'),
    ]
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    session_id = models.CharField(max_length=100, blank=True)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES, db_index=True)
    
    # Event data
    page_url = models.URLField(blank=True)
    referrer = models.URLField(blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True)
    
    # Contextual data
    region = models.ForeignKey(
        'regions.Region',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    service = models.ForeignKey(
        'services.Service',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Additional data
    properties = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['user', 'event_type']),
            models.Index(fields=['region', 'created_at']),
            models.Index(fields=['session_id', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.created_at}"