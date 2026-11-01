import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = Celery('securepay')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
app.conf.beat_schedule = {
    'securepay-milestone-reminders-daily': {
        'task': 'notifications.tasks.send_milestone_deadline_reminders',
        'schedule': crontab(hour=9, minute=0),
    },
}
