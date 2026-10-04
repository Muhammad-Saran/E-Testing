from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from src.services.accounts.models import User
from .models import Course, Enrollment


def csv_file(text):
    return SimpleUploadedFile('class.csv', text.encode('utf-8'), content_type='text/csv')


@override_settings(INSTITUTION_EMAIL_DOMAIN='')
class BulkEnrollTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(email='t@example.com', password='x', role='instructor')
        self.course = Course.objects.create(code='CSC101', title='Intro', instructor=self.teacher)
        self.ali = User.objects.create_user(email='ali@example.com', password='x', role='student')
        self.sara = User.objects.create_user(email='sara@example.com', password='x', role='student',
                                             registration_number='FA22-BCS-001')
        self.url = f'/api/courses/{self.course.id}/enroll_csv/'
        self.client.force_authenticate(self.teacher)

    def test_enrolls_known_students_and_reports_the_rest(self):
        Enrollment.objects.create(course=self.course, student=self.ali)
        res = self.client.post(self.url, {'file': csv_file(
            'email,registration_number\nali@example.com,\n,FA22-BCS-001\nnew@example.com,\nt@example.com,\n'
        )}, format='multipart')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['enrolled'], 1)
        self.assertEqual(res.data['already'], 1)
        self.assertEqual(res.data['not_found'], ['new@example.com'])
        self.assertEqual(len(res.data['errors']), 1)  # the instructor account
        self.assertTrue(Enrollment.objects.filter(course=self.course, student=self.sara).exists())

    def test_create_missing_invites_new_students(self):
        res = self.client.post(self.url, {'create_missing': 'true', 'file': csv_file(
            'email,first_name,last_name,registration_number\nnew@example.com,Nadia,Khan,FA22-BCS-099\nbad-email,,,\n'
        )}, format='multipart')
        self.assertEqual(res.data['created'], 1)
        self.assertEqual(res.data['enrolled'], 1)
        user = User.objects.get(email='new@example.com')
        self.assertEqual((user.role, user.first_name, user.registration_number), ('student', 'Nadia', 'FA22-BCS-099'))
        self.assertFalse(user.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('reset-password?uid=', mail.outbox[0].body)
        self.assertEqual(len(res.data['errors']), 1)

    @override_settings(INSTITUTION_EMAIL_DOMAIN='cuiatd.edu.pk')
    def test_new_accounts_respect_the_institution_domain(self):
        res = self.client.post(self.url, {'create_missing': 'true', 'file': csv_file('email\nx@gmail.com\n')},
                               format='multipart')
        self.assertEqual(res.data['created'], 0)
        self.assertIn('cuiatd.edu.pk', res.data['errors'][0]['error'])

    def test_rejects_files_without_a_usable_header(self):
        res = self.client.post(self.url, {'file': csv_file('name\nAli\n')}, format='multipart')
        self.assertEqual(res.status_code, 400)

    def test_only_the_course_instructor(self):
        other = User.objects.create_user(email='o@example.com', password='x', role='instructor')
        self.client.force_authenticate(other)
        res = self.client.post(self.url, {'file': csv_file('email\nali@example.com\n')}, format='multipart')
        self.assertEqual(res.status_code, 404)
