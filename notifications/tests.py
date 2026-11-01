from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from contracts.models import Contract, Milestone
from marketplace.models import Category, Gig

from .models import Notification, ReminderDelivery
from .tasks import send_milestone_deadline_reminders


class DeadlineReminderTaskTests(TestCase):
    def setUp(self):
        client = User.objects.create_user(
            email='client@example.test', password='Strong-password-123!',
            display_name='Client', role=User.Role.CLIENT,
        )
        self.freelancer = User.objects.create_user(
            email='freelancer@example.test', password='Strong-password-123!',
            display_name='Freelancer', role=User.Role.FREELANCER,
        )
        category, _ = Category.objects.get_or_create(slug='design', defaults={'name': 'Design'})
        gig = Gig.objects.create(
            freelancer=self.freelancer, category=category, title='Reminder gig',
            description='Description', starting_price='25.00', delivery_days=2,
        )
        contract = Contract.objects.create(
            client=client, freelancer=self.freelancer, gig=gig,
            title='Reminder contract', scope='Scope', total_amount='25.00',
            status=Contract.Status.IN_PROGRESS,
        )
        self.milestone = Milestone.objects.create(
            contract=contract, sequence=1, title='Reminder milestone', amount='25.00',
            due_date=timezone.localdate() + timedelta(days=1), status=Milestone.Status.FUNDED,
        )

    def test_due_tomorrow_notification_is_idempotent(self):
        self.assertEqual(send_milestone_deadline_reminders(), 1)
        self.assertEqual(send_milestone_deadline_reminders(), 0)
        self.assertEqual(ReminderDelivery.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.freelancer, kind='milestone_deadline').count(), 1)
