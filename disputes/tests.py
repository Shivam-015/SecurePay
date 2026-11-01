from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from auditlog.services import verify_contract_chain
from contracts.models import Contract, Milestone
from invoices.models import Invoice
from marketplace.models import Category, Gig
from payments.models import DemoPayment

from .models import Dispute
from .services import open_dispute, resolve_dispute


class DemoDisputeWorkflowTests(TestCase):
    def setUp(self):
        self.client = User.objects.create_user(
            email='client@example.test', password='Strong-password-123!',
            display_name='Client', role=User.Role.CLIENT,
        )
        self.freelancer = User.objects.create_user(
            email='freelancer@example.test', password='Strong-password-123!',
            display_name='Freelancer', role=User.Role.FREELANCER,
        )
        self.staff = User.objects.create_user(
            email='staff@example.test', password='Strong-password-123!',
            display_name='Reviewer', is_staff=True,
        )
        category, _ = Category.objects.get_or_create(slug='design', defaults={'name': 'Design'})
        gig = Gig.objects.create(
            freelancer=self.freelancer, category=category, title='Demo gig',
            description='Description', starting_price='100.00', delivery_days=5,
        )
        self.contract = Contract.objects.create(
            client=self.client, freelancer=self.freelancer, gig=gig,
            title='Demo contract', scope='Scope', total_amount='100.00',
            status=Contract.Status.IN_PROGRESS,
        )
        self.milestone = Milestone.objects.create(
            contract=self.contract, sequence=1, title='Delivery', amount='100.00',
            due_date=timezone.localdate() + timedelta(days=2), status=Milestone.Status.SUBMITTED,
        )
        self.payment = DemoPayment.objects.create(
            milestone=self.milestone, initiated_by=self.client, amount='100.00',
            currency='INR', status=DemoPayment.Status.FUNDED,
        )

    def test_staff_release_closes_dispute_and_issues_demo_invoice(self):
        dispute = open_dispute(
            milestone_id=self.milestone.pk, actor=self.client,
            reason=Dispute.Reason.QUALITY, description='Please review this delivery.',
        )
        self.assertEqual(self.milestone.__class__.objects.get(pk=self.milestone.pk).status, Milestone.Status.DISPUTED)

        resolve_dispute(
            dispute_id=dispute.pk, actor=self.staff,
            outcome=Dispute.Outcome.RELEASE_DEMO, resolution_note='Staff reviewed the submitted work.',
        )
        self.payment.refresh_from_db()
        self.contract.refresh_from_db()
        dispute.refresh_from_db()
        self.assertEqual(self.payment.status, DemoPayment.Status.RELEASED)
        self.assertEqual(self.contract.status, Contract.Status.COMPLETED)
        self.assertEqual(dispute.status, Dispute.Status.RESOLVED)
        self.assertTrue(Invoice.objects.filter(demo_payment=self.payment, is_demo=True).exists())
        self.assertTrue(verify_contract_chain(self.contract.pk))

    def test_non_staff_cannot_resolve_dispute(self):
        dispute = open_dispute(
            milestone_id=self.milestone.pk, actor=self.client,
            reason=Dispute.Reason.QUALITY, description='Please review this delivery.',
        )
        with self.assertRaises(PermissionDenied):
            resolve_dispute(
                dispute_id=dispute.pk, actor=self.freelancer,
                outcome=Dispute.Outcome.RELEASE_DEMO, resolution_note='Attempted decision.',
            )
