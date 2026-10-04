from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase

from src.services.notifications.models import Notification
from .models import AuthEvent, AuthEventType, User

PASSWORD = 'Str0ng-pass-123'


@override_settings(LOGIN_MAX_FAILURES=3, LOGIN_LOCKOUT_MINUTES=15)
class LockoutTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='stu@example.com', password=PASSWORD, role='student')

    def login(self, password):
        return self.client.post('/api/auth/login/', {'email': 'stu@example.com', 'password': password}, format='json')

    def test_account_locks_after_repeated_failures(self):
        for _ in range(3):
            self.assertEqual(self.login('wrong').status_code, 401)
        # Even the right password is refused while locked.
        res = self.login(PASSWORD)
        self.assertEqual(res.status_code, 429)
        self.assertTrue(res.data['locked'])
        self.assertGreaterEqual(res.data['retry_after_minutes'], 1)
        self.assertTrue(AuthEvent.objects.filter(event=AuthEventType.LOCKED).exists())
        self.assertTrue(Notification.objects.filter(user=self.user, title__icontains='locked').exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_successful_login_resets_the_count(self):
        self.login('wrong')
        self.login('wrong')
        self.assertEqual(self.login(PASSWORD).status_code, 200)
        self.login('wrong')
        self.login('wrong')
        self.assertEqual(self.login(PASSWORD).status_code, 200)

    def test_unknown_emails_are_also_limited(self):
        for _ in range(3):
            self.client.post('/api/auth/login/', {'email': 'ghost@example.com', 'password': 'x'}, format='json')
        res = self.client.post('/api/auth/login/', {'email': 'ghost@example.com', 'password': 'x'}, format='json')
        self.assertEqual(res.status_code, 429)


class ChangePasswordTests(APITestCase):
    def test_change_password_needs_the_current_one(self):
        user = User.objects.create_user(email='stu@example.com', password=PASSWORD, role='student')
        self.client.force_authenticate(user)
        url = '/api/auth/change-password/'
        bad = self.client.post(url, {'current_password': 'nope', 'new_password': 'An0ther-pass-456',
                                     'new_password_confirm': 'An0ther-pass-456'}, format='json')
        self.assertEqual(bad.status_code, 400)
        weak = self.client.post(url, {'current_password': PASSWORD, 'new_password': '123',
                                      'new_password_confirm': '123'}, format='json')
        self.assertEqual(weak.status_code, 400)
        ok = self.client.post(url, {'current_password': PASSWORD, 'new_password': 'An0ther-pass-456',
                                    'new_password_confirm': 'An0ther-pass-456'}, format='json')
        self.assertEqual(ok.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password('An0ther-pass-456'))
        self.assertEqual(len(mail.outbox), 1)
