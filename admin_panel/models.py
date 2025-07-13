from django.db import models
from django.utils import timezone
import uuid


class AdminActivity(models.Model):
    """
    Track admin activities for audit purposes
    """
    ACTIVITY_TYPES = [
        ('user_action', 'User Action'),
        ('professional_verification', 'Professional Verification'),
        ('booking_management', 'Booking Management'),
        ('payment_management', 'Payment Management'),
        ('content_moderation', 'Content Moderation'),
        ('system_configuration', 'System Configuration'),
    ]
    
    admin_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='admin_activities'
    )
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    target_model = models.CharField(max_length=50, blank=True)  # Model name
    target_id = models.CharField(max_length=100, blank=True)   # Model ID
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Metadata
    previous_data = models.JSONField(default=dict, blank=True)
    new_data = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['admin_user', 'created_at']),
            models.Index(fields=['activity_type', 'created_at']),
            models.Index(fields=['target_model', 'target_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.admin_user.get_full_name()} - {self.activity_type} - {self.created_at}"


class SystemAlert(models.Model):
    """
    System alerts for administrators
    """
    ALERT_TYPES = [
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Information'),
        ('critical', 'Critical'),
    ]
    
    ALERT_CATEGORIES = [
        ('payment', 'Payment Issues'),
        ('user', 'User Issues'),
        ('professional', 'Professional Issues'),
        ('booking', 'Booking Issues'),
        ('system', 'System Issues'),
        ('security', 'Security Issues'),
    ]
    
    alert_id = models.UUIDField(default=uuid.uuid4, unique=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    category = models.CharField(max_length=20, choices=ALERT_CATEGORIES)
    
    # Related objects
    related_user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    related_booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    related_payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Status
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_alerts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['alert_type', 'is_resolved']),
            models.Index(fields=['category', 'created_at']),
            models.Index(fields=['is_resolved', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.alert_type}"


class SupportTicket(models.Model):
    """
    Customer support tickets
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting_customer', 'Waiting for Customer'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    CATEGORY_CHOICES = [
        ('booking', 'Booking Issues'),
        ('payment', 'Payment Issues'),
        ('technical', 'Technical Issues'),
        ('account', 'Account Issues'),
        ('professional', 'Professional Issues'),
        ('other', 'Other'),
    ]
    
    ticket_id = models.UUIDField(default=uuid.uuid4, unique=True)
    customer = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='support_tickets'
    )
    
    # Ticket details
    subject = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Assignment
    assigned_to = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets'
    )
    
    # Related objects
    related_booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['priority', 'status']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Ticket {self.ticket_id} - {self.subject}"


class TicketMessage(models.Model):
    """
    Messages within support tickets
    """
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE
    )
    
    message = models.TextField()
    is_internal = models.BooleanField(default=False)  # Internal admin notes
    attachments = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
        ]
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message for {self.ticket.ticket_id}"