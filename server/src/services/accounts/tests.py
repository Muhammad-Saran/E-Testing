import re

from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import AuthEvent, AuthEventType, User

PASSWORD = 'Str0ng-pass-123'


@override_settings(INSTITUTION_EMAIL_DOMAIN='')
class AuthTests(APITestCase):
    def register(self, email='stu@example.com', role='student'):
        return self.client.post('/api/auth/register/', {
            'email': email, 'first_name': 'Test', 'last_name': 'User', 'role': role,
            'password': PASSWORD, 'password_confirm': PASSWORD,
        }, format='json')

    def login(self, email='stu@example.com', password=PASSWORD):
        return self.client.post('/api/auth/login/', {'email': email, 'password': password}, format='json')

    def test_register_and_login_issue_tokens(self):
        self.assertEqual(self.register().status_code, 201)
        res = self.login()
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.data)
        self.assertEqual(res.data['user']['role'], 'student')
        self.assertTrue(User.objects.get(email='stu@example.com').password.startswith('bcrypt'))

    @override_settings(INSTITUTION_EMAIL_DOMAIN='cuiatd.edu.pk')
    def test_registration_restricted_to_institution_domain(self):
        self.assertEqual(self.register(email='x@gmail.com').status_code, 400)
        self.assertEqual(self.register(email='x@cuiatd.edu.pk').status_code, 201)

    def test_student_cannot_promote_themselves(self):
        token = self.register().data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = self.client.patch('/api/auth/me/', {'role': 'instructor', 'first_name': 'New'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['role'], 'student')
        self.assertEqual(res.data['first_name'], 'New')

    def test_logout_blacklists_refresh_token(self):
        data = self.register().data
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {data["access"]}')
        self.assertEqual(self.client.post('/api/auth/logout/', {'refresh': data['refresh']}, format='json').status_code, 200)
        self.client.credentials()
        res = self.client.post('/api/auth/refresh/', {'refresh': data['refresh']}, format='json')
        self.assertEqual(res.status_code, 401)

    def test_password_reset_link_is_single_use(self):
        self.register()
        res = self.client.post('/api/auth/password-reset/', {'email': 'stu@example.com'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        uid, token = re.search(r'uid=([^&\s]+)&token=(\S+)', mail.outbox[0].body).groups()

        payload = {'uid': uid, 'token': token, 'password': 'An0ther-pass-456', 'password_confirm': 'An0ther-pass-456'}
        self.assertEqual(self.client.post('/api/auth/password-reset/confirm/', payload, format='json').status_code, 200)
        self.assertEqual(self.login(password='An0ther-pass-456').status_code, 200)
        # The same link cannot be used a second time.
        self.assertEqual(self.client.post('/api/auth/password-reset/confirm/', payload, format='json').status_code, 400)

    def test_password_reset_does_not_reveal_unknown_emails(self):
        res = self.client.post('/api/auth/password-reset/', {'email': 'nobody@example.com'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_auth_events_are_audited(self):
        self.register()
        self.login()
        self.login(password='wrong-password')
        events = set(AuthEvent.objects.values_list('event', flat=True))
        self.assertEqual(events, {AuthEventType.REGISTER, AuthEventType.LOGIN, AuthEventType.LOGIN_FAILED})
