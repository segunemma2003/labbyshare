import os
from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.settings')

app = Celery('labmyshare')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Periodic tasks
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-expired-otps': {
        'task': 'accounts.tasks.cleanup_expired_otps',
        'schedule': crontab(minute=0, hour=2),  # Run daily at 2 AM
    },
    'send-booking-reminders': {
        'task': 'bookings.tasks.send_booking_reminders',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'update-professional-ratings': {
        'task': 'professionals.tasks.update_ratings',
        'schedule': crontab(minute=0, hour=1),  # Daily at 1 AM
    },
    'check-and-update-booking-payments': {
        'task': 'bookings.tasks.check_and_update_booking_payments',
        'schedule': crontab(minute='*/5'),
    },
}

app.conf.timezone = 'UTC'

# Task configuration
app.conf.task_always_eager = os.environ.get('CELERY_ALWAYS_EAGER', 'False').lower() == 'true'
app.conf.task_eager_propagates = True
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')