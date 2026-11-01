from django.test import TestCase
from django.urls import reverse
import hashlib
import json

from accounts.models import User
from auditlog.models import AuditEvent
from auditlog.services import agreement_fingerprint, record_event
from marketplace.models import Category, Gig

from .models import Contract, Milestone


class ContractEvidenceExportTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email='buyer@example.test', password='Strong-password-123!',
            display_name='Buyer', role=User.Role.CLIENT,
        )
        self.freelancer = User.objects.create_user(
            email='maker@example.test', password='Strong-password-123!',
            display_name='Maker', role=User.Role.FREELANCER,
        )
        category, _ = Category.objects.get_or_create(slug='design', defaults={'name': 'Design'})
        gig = Gig.objects.create(
            freelancer=self.freelancer, category=category, title='Design service',
            description='A service', starting_price='100.00', delivery_days=5,
        )
        self.contract = Contract.objects.create(
            client=self.client_user, freelancer=self.freelancer, gig=gig,
            title='Brand package', scope='Create a visual identity',
            total_amount='100.00',
        )
        Milestone.objects.create(
            contract=self.contract, sequence=1, title='First draft',
            amount='100.00', due_date='2030-01-01',
        )
        record_event(
            contract=self.contract, actor=self.client_user,
            event_type='contract_proposed', payload={
                'milestone_count': 1,
                'agreement_hash': agreement_fingerprint(self.contract),
            },
        )

    def test_participant_can_download_verified_evidence_without_private_email(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse('contracts:contract_evidence_export', args=(self.contract.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(response.json()['integrity']['status'], 'verified')
        self.assertEqual(response.json()['agreement']['milestones'][0]['title'], 'First draft')
        self.assertNotIn('email', response.json()['agreement'])
        evidence = response.json()
        agreement_json = json.dumps(evidence['agreement_fingerprint_input'], sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        self.assertEqual(hashlib.sha256(agreement_json.encode('utf-8')).hexdigest(), evidence['integrity']['agreement_fingerprint'])
        previous_hash = ''
        for sequence, event in enumerate(evidence['events'], start=1):
            self.assertEqual(event['sequence'], sequence)
            self.assertEqual(event['previous_hash'], previous_hash)
            event_fields = {key: event[key] for key in (
                'contract_id', 'sequence', 'event_type', 'actor_id', 'payload', 'occurred_at', 'previous_hash',
            )}
            event_json = json.dumps(event_fields, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            previous_hash = hashlib.sha256(event_json.encode('utf-8')).hexdigest()
            self.assertEqual(previous_hash, event['event_hash'])

    def test_nonparticipant_cannot_download_evidence(self):
        outsider = User.objects.create_user(
            email='outsider@example.test', password='Strong-password-123!',
            display_name='Outsider', role=User.Role.CLIENT,
        )
        self.client.force_login(outsider)
        response = self.client.get(reverse('contracts:contract_evidence_export', args=(self.contract.pk,)))
        self.assertEqual(response.status_code, 404)

    def test_evidence_reports_a_tampered_chain(self):
        AuditEvent.objects.filter(contract=self.contract).update(payload={'changed': True})
        self.client.force_login(self.client_user)
        response = self.client.get(reverse('contracts:contract_evidence_export', args=(self.contract.pk,)))
        self.assertEqual(response.json()['integrity']['status'], 'failed')

    def test_evidence_detects_changed_agreed_terms_even_if_event_chain_is_intact(self):
        self.contract.scope = 'Altered after proposal'
        self.contract.save(update_fields=('scope',))
        self.client.force_login(self.client_user)
        response = self.client.get(reverse('contracts:contract_evidence_export', args=(self.contract.pk,)))
        integrity = response.json()['integrity']
        self.assertTrue(integrity['event_chain_valid'])
        self.assertFalse(integrity['agreement_fingerprint_valid'])
        self.assertEqual(integrity['status'], 'failed')
