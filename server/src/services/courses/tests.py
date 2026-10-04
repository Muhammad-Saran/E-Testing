import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from src.services.accounts.models import User
from .models import Course, Enrollment

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class CourseMaterialTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.teacher = User.objects.create_user(email='t@example.com', password='x', role='instructor')
        self.student = User.objects.create_user(email='s@example.com', password='x', role='student')
        self.outsider = User.objects.create_user(email='o@example.com', password='x', role='student')
        self.course = Course.objects.create(code='CSC101', title='Intro', instructor=self.teacher)
        Enrollment.objects.create(course=self.course, student=self.student)

    def upload(self, name='notes.pdf'):
        self.client.force_authenticate(self.teacher)
        return self.client.post('/api/courses/materials/', {
            'course': self.course.id, 'title': 'Lecture 1',
            'file': SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf'),
        }, format='multipart')

    def test_enrolled_student_can_download(self):
        material = self.upload().data
        self.client.force_authenticate(self.student)
        self.assertEqual(len(self.client.get('/api/courses/materials/').data), 1)
        res = self.client.get(f'/api/courses/materials/{material["id"]}/download/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(b''.join(res.streaming_content), b'%PDF-1.4 test')

    def test_unenrolled_student_cannot_see_material(self):
        material = self.upload().data
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get('/api/courses/materials/').data, [])
        self.assertEqual(self.client.get(f'/api/courses/materials/{material["id"]}/download/').status_code, 404)

    def test_disallowed_file_type_is_rejected(self):
        self.assertEqual(self.upload(name='virus.exe').status_code, 400)

    def test_students_cannot_view_roster(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(f'/api/courses/{self.course.id}/roster/').status_code, 403)
