from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_otp_email(self, email, otp, purpose):
    """
    Send OTP email for verification or password reset
    """
    try:
        if purpose == 'verification':
            subject = 'Verify Your Email - LabMyShare'
            template = 'emails/email_verification.html'
        else:
            subject = 'Password Reset - LabMyShare'
            template = 'emails/password_reset.html'
        
        html_message = render_to_string(template, {
            'otp': otp,
            'email': email,
            'purpose': purpose
        })
        
        send_mail(
            subject=subject,
            message=f'Your OTP is: {otp}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"OTP email sent successfully to {email}")
        return True
        
    except Exception as exc:
        logger.error(f"Failed to send OTP email to {email}: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        return False


@shared_task
def cleanup_expired_otps():
    """
    Clean up expired OTP verification records
    """
    from .models import OTPVerification
    
    expired_count = OTPVerification.objects.filter(
        expires_at__lt=timezone.now()
    ).delete()[0]
    
    logger.info(f"Cleaned up {expired_count} expired OTP records")
    return expired_count


@shared_task
def send_welcome_email(user_id):
    """
    Send welcome email to new users
    """
    try:
        from .models import User
        user = User.objects.get(id=user_id)
        
        subject = 'Welcome to LabMyShare!'
        html_message = render_to_string('emails/welcome.html', {
            'user': user,
            'region': user.current_region
        })
        
        send_mail(
            subject=subject,
            message=f'Welcome {user.get_full_name()}!',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        return True
        
    except Exception as exc:
        logger.error(f"Failed to send welcome email: {str(exc)}")
        return False