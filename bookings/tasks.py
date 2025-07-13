from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def schedule_booking_reminders(booking_id):
    """
    Schedule reminder notifications for bookings
    """
    try:
        from .models import Booking
        booking = Booking.objects.get(id=booking_id)
        
        booking_datetime = timezone.datetime.combine(
            booking.scheduled_date, 
            booking.scheduled_time
        )
        
        # Make timezone aware
        if timezone.is_naive(booking_datetime):
            booking_datetime = timezone.make_aware(booking_datetime)
        
        # Schedule 24h reminder
        reminder_24h = booking_datetime - timedelta(hours=24)
        if reminder_24h > timezone.now():
            send_booking_reminder.apply_async(
                args=[booking_id, '24h'],
                eta=reminder_24h
            )
        
        # Schedule 3h reminder
        reminder_3h = booking_datetime - timedelta(hours=3)
        if reminder_3h > timezone.now():
            send_booking_reminder.apply_async(
                args=[booking_id, '3h'],
                eta=reminder_3h
            )
        
        # Schedule 1h reminder
        reminder_1h = booking_datetime - timedelta(hours=1)
        if reminder_1h > timezone.now():
            send_booking_reminder.apply_async(
                args=[booking_id, '1h'],
                eta=reminder_1h
            )
        
        logger.info(f"Scheduled reminders for booking {booking.booking_id}")
        return True
    
    except Exception as exc:
        logger.error(f"Failed to schedule reminders for booking {booking_id}: {str(exc)}")
        return False


@shared_task
def send_booking_reminder(booking_id, reminder_type):
    """
    Send booking reminder notification
    """
    try:
        from .models import Booking
        booking = Booking.objects.get(id=booking_id)
        
        if booking.status != 'confirmed':
            logger.info(f"Booking {booking.booking_id} not confirmed, skipping reminder")
            return False
        
        # Update reminder sent status
        if reminder_type == '24h':
            booking.reminder_24h_sent = True
        elif reminder_type == '3h':
            booking.reminder_3h_sent = True
        elif reminder_type == '1h':
            booking.reminder_1h_sent = True
        
        booking.save(update_fields=[f'reminder_{reminder_type}_sent'])
        
        # Send push notification via Firebase
        from notifications.tasks import send_push_notification
        send_push_notification.delay(
            user_id=booking.customer.id,
            title=f'Upcoming Appointment - {reminder_type} reminder',
            body=f'Your {booking.service.name} appointment is in {reminder_type}.',
            data={
                'booking_id': str(booking.booking_id),
                'type': 'booking_reminder'
            }
        )
        
        logger.info(f"Sent {reminder_type} reminder for booking {booking.booking_id}")
        return True
    
    except Exception as exc:
        logger.error(f"Failed to send reminder: {str(exc)}")
        return False
