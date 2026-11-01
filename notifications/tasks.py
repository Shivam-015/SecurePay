from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from contracts.models import Milestone

from .models import Notification, ReminderDelivery


@shared_task(ignore_result=True)
def send_milestone_deadline_reminders():
    today = timezone.localdate()
    targets = (
        ('due_tomorrow', today + timedelta(days=1), 'Your milestone is due tomorrow.'),
        ('overdue', None, 'Your milestone deadline has passed. Please update the client.'),
    )
    created = 0
    milestones = Milestone.objects.select_related('contract', 'contract__freelancer', 'contract__client').filter(
        status__in=(Milestone.Status.FUNDED, Milestone.Status.REVISION_REQUESTED),
    )
    for milestone in milestones:
        for reminder_type, target_date, message_text in targets:
            if reminder_type == 'due_tomorrow' and milestone.due_date != target_date:
                continue
            if reminder_type == 'overdue' and milestone.due_date >= today:
                continue
            delivery_date = target_date or today
            try:
                with transaction.atomic():
                    ReminderDelivery.objects.create(
                        milestone=milestone,
                        recipient=milestone.contract.freelancer,
                        reminder_type=reminder_type,
                        target_date=delivery_date,
                    )
                    Notification.objects.create(
                        recipient=milestone.contract.freelancer,
                        actor=None,
                        contract=milestone.contract,
                        kind='milestone_deadline',
                        title='Milestone deadline reminder',
                        message=f'{message_text} “{milestone.title}” is due {milestone.due_date.strftime("%b %d").lstrip("0")}.',
                    )
            except IntegrityError:
                continue
            created += 1
            if getattr(settings, 'DEADLINE_EMAILS', False) and milestone.contract.freelancer.email:
                send_mail(
                    subject=f'SecurePay milestone reminder: {milestone.title}',
                    message=f'{message_text}\nContract: {milestone.contract.title}\nDue date: {milestone.due_date:%Y-%m-%d}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[milestone.contract.freelancer.email],
                    fail_silently=True,
                )
    return created
