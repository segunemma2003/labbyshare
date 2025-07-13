@shared_task(bind=True, max_retries=3)
def send_push_notification(self, user_id, title, body, data=None):
    """
    Send push notification via Firebase
    """
    try:
        from firebase_admin import messaging
        from accounts.models import User
        
        user = User.objects.get(id=user_id)
        
        if not user.firebase_uid:
            logger.warning(f"User {user_id} has no Firebase UID")
            return False
        
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            token=user.firebase_uid,
            data=data or {}
        )
        
        response = messaging.send(message)
        logger.info(f"Push notification sent to {user.email}: {response}")
        return True
        
    except Exception as exc:
        logger.error(f"Failed to send push notification: {str(exc)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        return False