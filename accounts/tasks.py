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
        logger.info(f"Starting OTP email task for {email} with purpose {purpose}")
        
        # Validate inputs
        if not email or not otp or not purpose:
            logger.error(f"Missing required parameters: email={email}, otp={otp}, purpose={purpose}")
            return False
        
        if purpose == 'email_verification':
            subject = 'Verify Your Email - The beauty Spa by Shea'
            template = 'emails/email_verification.html'
        else:
            subject = 'Password Reset - The beauty Spa by Shea'
            template = 'emails/password_reset.html'
        
        logger.info(f"Rendering template {template} for {email}")
        
        # Check if template exists and can be rendered
        try:
            html_message = render_to_string(template, {
                'otp': otp,
                'email': email,
                'purpose': purpose
            })
            logger.info(f"Template rendered successfully")
        except Exception as template_error:
            logger.error(f"Failed to render template {template}: {str(template_error)}")
            # Continue with plain text as fallback
            html_message = None
        
        # Plain text fallback
        plain_message = f'Your OTP is: {otp}. This code will expire in 10 minutes.'
        
        # Validate email settings
        if not settings.DEFAULT_FROM_EMAIL:
            logger.error("DEFAULT_FROM_EMAIL is not configured")
            return False
        
        logger.info(f"Sending email to {email} with subject: {subject}")
        
        # Send email with error handling
        try:
            result = send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False
            )
            logger.info(f"Email sent successfully with result: {result}")
            return True
            
        except Exception as mail_error:
            logger.error(f"Failed to send email via SMTP: {str(mail_error)}")
            raise mail_error
        
    except Exception as exc:
        logger.error(f"Failed to send OTP email to {email}: {str(exc)}")
        if self.request.retries < self.max_retries:
            # Exponential backoff: 60s, 120s, 240s
            countdown = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying email send in {countdown} seconds, attempt {self.request.retries + 1}")
            raise self.retry(countdown=countdown, exc=exc)
        
        # Send notification to admins about email failure
        logger.critical(f"Failed to send OTP email after all retries: {email}")
        return False


@shared_task
def send_otp_email_sync(email, otp, purpose):
    """
    Send OTP email synchronously (fallback function)
    """
    try:
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        
        logger.info(f"Sending OTP email synchronously to {email}")
        
        if purpose == 'email_verification':
            subject = 'Verify Your Email - The beauty Spa by Shea'
            template = 'emails/email_verification.html'
        else:
            subject = 'Password Reset - The beauty Spa by Shea'
            template = 'emails/password_reset.html'
        
        try:
            html_message = render_to_string(template, {
                'otp': otp,
                'email': email,
                'purpose': purpose
            })
        except Exception:
            html_message = None
        
        plain_message = f'Your OTP is: {otp}. This code will expire in 10 minutes.'
        
        result = send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Synchronous OTP email sent successfully: {result}")
        return True
        
    except Exception as exc:
        logger.error(f"Failed to send OTP email synchronously: {str(exc)}")
        return False


@shared_task
def send_welcome_email(user_id):
    """
    Send welcome email to new users
    """
    try:
        from .models import User
        user = User.objects.get(id=user_id)
        
        subject = 'Welcome to The beauty Spa by Shea!'
        html_message = render_to_string('emails/welcome.html', {
            'user': user,
            'region': user.current_region
        })
        
        plain_message = f'Welcome {user.get_full_name()}! Your  account is now active.'
        
        send_mail(
            subject=subject,
            message=plain_message,
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