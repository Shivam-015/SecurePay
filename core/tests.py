from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    def test_healthcheck_confirms_database_connection(self):
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_healthcheck_rejects_non_get_requests(self):
        response = self.client.post(reverse('health'))
        self.assertEqual(response.status_code, 405)
