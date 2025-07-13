import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'labmyshare.settings')

app = Celery('labmyshare')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periodic tasks
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-expired-otps': {
        'task': 'accounts.tasks.cleanup_expired_otps',
        'schedule': crontab(minute=0, hour=2),  # Run daily at 2 AM
    },
}
app.conf.timezone = 'UTC'