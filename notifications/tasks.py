from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from firebase_admin import messaging
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_push_notification(self, user_id, title, body, data=None, notification_type=None):
    """
    Send push notification via Firebase
    """
    try:
        from accounts.models import User
        from .models import PushNotificationDevice, Notification, NotificationPreference
        
        user = User.objects.get(id=user_id)
        
        # Check user preferences
        try:
            preferences = user.notification_preferences
            # Check if user wants this type of notification
            if notification_type and not getattr(preferences, f"{notification_type}_push", True):
                logger.info(f"Push notification skipped for user {user_id} due to preferences")
                return False
        except NotificationPreference.DoesNotExist:
            pass  # Default to sending if no preferences set
        
        # Get active devices for user
        devices = PushNotificationDevice.objects.filter(user=user, is_active=True)
        
        if not devices.exists():
            logger.warning(f"No active devices found for user {user_id}")
            return False
        
        # Send to all devices
        messages = []
        for device in devices:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                token=device.device_token,
                data=data or {}
            )
            messages.append(message)
        
        # Send batch
        response = messaging.send_all(messages)
        
        # Handle failed tokens
        if response.failure_count > 0:
            failed_tokens = []
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    failed_tokens.append(devices[idx].device_token)
                    logger.error(f"Failed to send to token: {resp.exception}")
            
            # Deactivate failed devices
            PushNotificationDevice.objects.filter(
                device_token__in=failed_tokens
            ).update(is_active=False)
        
        logger.info(f"Push notification sent to {user.email}: {response.success_count} succeeded, {response.failure_count} failed")
        return True
        
    except Exception as exc:
        logger.error(f"Failed to send push notification: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        return False


@shared_task(bind=True, max_retries=3)
def send_email_notification(self, user_id, subject, template, context, notification_type=None):
    """
    Send email notification
    """
    try:
        from accounts.models import User
        from .models import NotificationPreference
        
        user = User.objects.get(id=user_id)
        
        # Check user preferences
        try:
            preferences = user.notification_preferences
            if notification_type and not getattr(preferences, f"{notification_type}_email", True):
                logger.info(f"Email notification skipped for user {user_id} due to preferences")
                return False
        except NotificationPreference.DoesNotExist:
            pass
        
        # Render email template
        html_message = render_to_string(template, context)
        
        send_mail(
            subject=subject,
            message='',  # Plain text version
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Email notification sent to {user.email}")
        return True
        
    except Exception as exc:
        logger.error(f"Failed to send email notification: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        return False


@shared_task
def create_notification(user_id, notification_type, title, message, action_url='', data=None, related_booking_id=None, related_payment_id=None):
    """
    Create in-app notification
    """
    try:
        from accounts.models import User
        from .models import Notification
        
        user = User.objects.get(id=user_id)
        
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            action_url=action_url,
            data=data or {},
            related_booking_id=related_booking_id,
            related_payment_id=related_payment_id
        )
        
        logger.info(f"Notification created for {user.email}: {title}")
        return notification.id
        
    except Exception as exc:
        logger.error(f"Failed to create notification: {str(exc)}")
        return None


@shared_task
def send_booking_notification(booking_id, notification_type, user_ids=None):
    """
    Send booking-related notifications
    """
    try:
        from bookings.models import Booking
        booking = Booking.objects.get(id=booking_id)
        
        # Define notification content based on type
        notifications = {
            'booking_created': {
                'title': 'Booking Created',
                'message': f'Your booking for {booking.service.name} has been created.',
                'users': [booking.customer.id]
            },
            'booking_confirmed': {
                'title': 'Booking Confirmed',
                'message': f'Your booking for {booking.service.name} has been confirmed.',
                'users': [booking.customer.id]
            },
            'booking_cancelled': {
                'title': 'Booking Cancelled',
                'message': f'Your booking for {booking.service.name} has been cancelled.',
                'users': [booking.customer.id]
            },
            'professional_new_booking': {
                'title': 'New Booking Request',
                'message': f'You have a new booking request for {booking.service.name}.',
                'users': [booking.professional.user.id]
            }
        }
        
        notification_config = notifications.get(notification_type)
        if not notification_config:
            logger.error(f"Unknown notification type: {notification_type}")
            return
        
        target_users = user_ids or notification_config['users']
        
        for user_id in target_users:
            # Create in-app notification
            create_notification.delay(
                user_id=user_id,
                notification_type=notification_type,
                title=notification_config['title'],
                message=notification_config['message'],
                action_url=f'/bookings/{booking.booking_id}',
                related_booking_id=booking.id
            )
            
            # Send push notification
            send_push_notification.delay(
                user_id=user_id,
                title=notification_config['title'],
                body=notification_config['message'],
                data={
                    'booking_id': str(booking.booking_id),
                    'type': notification_type
                },
                notification_type='booking_updates'
            )
        
    except Exception as exc:
        logger.error(f"Failed to send booking notification: {str(exc)}")


@shared_task
def send_payment_confirmation(payment_id):
    """
    Send payment confirmation notification
    """
    try:
        from payments.models import Payment
        payment = Payment.objects.get(id=payment_id)
        
        # Create in-app notification
        create_notification.delay(
            user_id=payment.customer.id,
            notification_type='payment_succeeded',
            title='Payment Successful',
            message=f'Your payment of {payment.amount} {payment.currency} has been processed successfully.',
            action_url=f'/payments/{payment.payment_id}',
            related_payment_id=payment.id
        )
        
        # Send push notification
        send_push_notification.delay(
            user_id=payment.customer.id,
            title='Payment Successful',
            body=f'Your payment of {payment.amount} {payment.currency} has been processed.',
            data={
                'payment_id': str(payment.payment_id),
                'type': 'payment_succeeded'
            },
            notification_type='payment_updates'
        )
        
        # Send email confirmation
        send_email_notification.delay(
            user_id=payment.customer.id,
            subject='Payment Confirmation - LabMyShare',
            template='emails/payment_confirmation.html',
            context={
                'payment': payment,
                'booking': payment.booking,
                'customer': payment.customer
            },
            notification_type='payment_updates'
        )
        
    except Exception as exc:
        logger.error(f"Failed to send payment confirmation: {str(exc)}")


@shared_task
def send_professional_verification_notification(professional_id, action, notes=''):
    """
    Send professional verification result notification
    """
    try:
        from professionals.models import Professional
        professional = Professional.objects.get(id=professional_id)
        
        if action == 'approve':
            title = 'Professional Verification Approved'
            message = 'Congratulations! Your professional account has been verified. You can now start accepting bookings.'
            notification_type = 'professional_verified'
        else:
            title = 'Professional Verification Update'
            message = f'Your professional verification needs attention. {notes}'
            notification_type = 'professional_rejected'
        
        # Create in-app notification
        create_notification.delay(
            user_id=professional.user.id,
            notification_type=notification_type,
            title=title,
            message=message,
            action_url='/professional/profile'
        )
        
        # Send push notification
        send_push_notification.delay(
            user_id=professional.user.id,
            title=title,
            body=message,
            data={'type': notification_type}
        )
        
        # Send email
        send_email_notification.delay(
            user_id=professional.user.id,
            subject=f'{title} - LabMyShare',
            template='emails/professional_verification.html',
            context={
                'professional': professional,
                'action': action,
                'notes': notes
            }
        )
        
    except Exception as exc:
        logger.error(f"Failed to send professional verification notification: {str(exc)}")


@shared_task
def send_admin_notification(notification_type, message, data=None):
    """
    Send notification to admin users
    """
    try:
        from accounts.models import User
        
        admin_users = User.objects.filter(
            user_type__in=['admin', 'super_admin'],
            is_active=True
        )
        
        for admin in admin_users:
            create_notification.delay(
                user_id=admin.id,
                notification_type='system_announcement',
                title=f'Admin Alert: {notification_type}',
                message=message,
                data=data or {}
            )
        
    except Exception as exc:
        logger.error(f"Failed to send admin notification: {str(exc)}")

