from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import User
from .services import send_email_verification, verify_email_token


class AccountRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='person@example.test', password='Old-password-123!',
            display_name='Person',
        )

    def test_password_reset_sends_a_one_time_link_without_disclosing_unknown_accounts(self):
        response = self.client.post(reverse('accounts:password_reset'), {'email': self.user.email})
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/password-reset/', mail.outbox[0].body)

        response = self.client.post(reverse('accounts:password_reset'), {'email': 'unknown@example.test'})
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

    def test_authenticated_user_can_change_password(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('accounts:password_change'), {
            'old_password': 'Old-password-123!',
            'new_password1': 'New-password-456!Secure',
            'new_password2': 'New-password-456!Secure',
        })
        self.assertRedirects(response, reverse('accounts:password_change_done'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-password-456!Secure'))


class EmailVerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='pending@example.test', password='Strong-password-123!',
            display_name='Pending', is_active=False,
        )

    def test_verification_token_activates_once(self):
        request = self.client.get('/')
        send_email_verification(user=self.user, request=request.wsgi_request)
        import re
        match = re.search(r'/verify-email/([^/\s]+)/', mail.outbox[-1].body)
        self.assertIsNotNone(match)
        token = match.group(1)
        self.assertTrue(verify_email_token(token))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertFalse(verify_email_token(token))

    def test_invalid_verification_token_does_not_activate_account(self):
        self.assertFalse(verify_email_token('invalid-token'))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_signup_requires_email_confirmation_before_sign_in(self):
        response = self.client.post(reverse('accounts:signup'), {
            'display_name': 'New member',
            'email': 'new-member@example.test',
            'role': User.Role.CLIENT,
            'password1': 'Long-password-123!Secure',
            'password2': 'Long-password-123!Secure',
        })
        self.assertRedirects(response, reverse('accounts:verification_sent'))
        user = User.objects.get(email='new-member@example.test')
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        import re
        match = re.search(r'/verify-email/([^/\s]+)/', mail.outbox[-1].body)
        self.assertIsNotNone(match)
        response = self.client.post(reverse('accounts:verify_email', kwargs={'token': match.group(1)}))
        self.assertRedirects(response, reverse('accounts:login'))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
