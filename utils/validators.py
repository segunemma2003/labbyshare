"""
Custom validators
"""
from django.core.exceptions import ValidationError
from django.utils import timezone
import re


def validate_phone_number(value):
    """Validate phone number format"""
    pattern = r'^\+?1?\d{9,15}$'
    if not re.match(pattern, value):
        raise ValidationError('Invalid phone number format')


def validate_future_date(value):
    """Validate that date is in the future"""
    if value <= timezone.now().date():
        raise ValidationError('Date must be in the future')


def validate_business_hours(start_time, end_time):
    """Validate business hours"""
    if start_time >= end_time:
        raise ValidationError('End time must be after start time')


def validate_rating(value):
    """Validate rating is between 1 and 5"""
    if not 1 <= value <= 5:
        raise ValidationError('Rating must be between 1 and 5')
