from rest_framework.test import APITestCase

from accounts.models import User
from marketplace.models import Category, Gig


class ApiAuthenticationAndVisibilityTests(APITestCase):
    def setUp(self):
        self.freelancer = User.objects.create_user(
            email='freelancer@example.test', password='Strong-password-123!',
            display_name='Freelancer', role=User.Role.FREELANCER,
        )
        category, _ = Category.objects.get_or_create(slug='design', defaults={'name': 'Design'})
        self.gig = Gig.objects.create(
            freelancer=self.freelancer, category=category, title='Logo design',
            description='A demo service', starting_price='50.00', delivery_days=5,
        )

    def test_gigs_are_public_and_protected_profile_requires_jwt(self):
        response = self.client.get('/api/v1/gigs/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['slug'], self.gig.slug)

        denied = self.client.get('/api/v1/me/')
        self.assertEqual(denied.status_code, 401)

        token_response = self.client.post('/api/v1/auth/token/', {
            'email': self.freelancer.email,
            'password': 'Strong-password-123!',
        }, format='json')
        self.assertEqual(token_response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")
        profile = self.client.get('/api/v1/me/')
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data['email'], self.freelancer.email)

    def test_registration_creates_regular_user_and_hashes_password(self):
        response = self.client.post('/api/v1/auth/register/', {
            'email': 'new-client@example.test',
            'display_name': 'New Client',
            'role': User.Role.CLIENT,
            'password': 'Valid-password-456!',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='new-client@example.test')
        self.assertTrue(user.check_password('Valid-password-456!'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_active)
        from django.core import mail
        import re
        token_match = re.search(r'/verify-email/([^/\s]+)/', mail.outbox[-1].body)
        self.assertIsNotNone(token_match)
        token = token_match.group(1)
        verified = self.client.post('/api/v1/auth/verify-email/', {'token': token}, format='json')
        self.assertEqual(verified.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_contract_detail_is_scoped_to_participants(self):
        client_user = User.objects.create_user(
            email='client@example.test', password='Strong-password-123!',
            display_name='Client', role=User.Role.CLIENT,
        )
        from contracts.models import Contract
        contract = Contract.objects.create(
            client=client_user, freelancer=self.freelancer, gig=self.gig,
            title='Private contract', scope='Private details', total_amount='50.00',
        )
        outsider = User.objects.create_user(
            email='outsider@example.test', password='Strong-password-123!',
            display_name='Outsider', role=User.Role.CLIENT,
        )
        self.client.force_authenticate(outsider)
        response = self.client.get(f'/api/v1/contracts/{contract.pk}/')
        self.assertEqual(response.status_code, 404)

    def test_contract_evidence_is_scoped_to_participants(self):
        from contracts.models import Contract
        owner = User.objects.create_user(
            email='owner@example.test', password='Strong-password-123!',
            display_name='Owner', role=User.Role.CLIENT,
        )
        contract = Contract.objects.create(
            client=owner, freelancer=self.freelancer, gig=self.gig,
            title='Private agreement', scope='Private scope', total_amount='50.00',
        )
        outsider = User.objects.create_user(
            email='evidence-outsider@example.test', password='Strong-password-123!',
            display_name='Outsider', role=User.Role.CLIENT,
        )
        self.client.force_authenticate(outsider)
        response = self.client.get(f'/api/v1/contracts/{contract.pk}/evidence/')
        self.assertEqual(response.status_code, 404)

        self.client.force_authenticate(owner)
        response = self.client.get(f'/api/v1/contracts/{contract.pk}/evidence/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['integrity']['status'], 'no_events')
        self.assertNotIn('email', response.data['agreement'])

    def test_nonexistent_dispute_message_returns_not_found(self):
        self.client.force_authenticate(self.freelancer)
        response = self.client.post('/api/v1/disputes/999999/messages/', {'body': 'Hello'}, format='json')
        self.assertEqual(response.status_code, 404)

