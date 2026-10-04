from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from src.services.accounts.models import User
from .models import Question


class QuestionBankTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(email='t@example.com', password='x', role='instructor')
        self.client.force_authenticate(self.teacher)

    def test_mcq_needs_exactly_one_correct_option(self):
        payload = {'text': 'Pick', 'question_type': 'mcq', 'options': [
            {'text': 'a', 'is_correct': True}, {'text': 'b', 'is_correct': True}]}
        self.assertEqual(self.client.post('/api/questions/', payload, format='json').status_code, 400)
        payload['options'][1]['is_correct'] = False
        self.assertEqual(self.client.post('/api/questions/', payload, format='json').status_code, 201)

    def test_true_false_answer_expands_into_options(self):
        res = self.client.post('/api/questions/', {
            'text': 'Sky is blue', 'question_type': 'true_false', 'correct_answer_text': 'true'}, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual([(o['text'], o['is_correct']) for o in res.data['options']],
                         [('True', True), ('False', False)])

    def test_edit_bumps_version(self):
        q = self.client.post('/api/questions/', {
            'text': 'Q', 'question_type': 'short_answer', 'correct_answer_text': 'A'}, format='json').data
        res = self.client.patch(f'/api/questions/{q["id"]}/', {'text': 'Q2'}, format='json')
        self.assertEqual(res.data['version'], 2)

    def test_csv_import_supports_all_types(self):
        csv_text = (
            'text,question_type,difficulty,subject,marks,correct_answer_text,options\n'
            'Largest planet?,mcq,remember,Science,2,Jupiter,Mars|Jupiter|Venus\n'
            'Water boils at 100C,true_false,remember,Science,1,true,\n'
            'Define OOP,short_answer,understand,CS,3,object oriented programming,\n'
            ',mcq,remember,,1,,\n'
        )
        upload = SimpleUploadedFile('q.csv', csv_text.encode(), content_type='text/csv')
        res = self.client.post('/api/questions/import_csv/', {'file': upload}, format='multipart')
        self.assertEqual(res.data['created'], 3)
        self.assertEqual(res.data['failed'], 1)
        mcq = Question.objects.get(text='Largest planet?')
        self.assertEqual(mcq.options.get(is_correct=True).text, 'Jupiter')

    def test_students_cannot_use_the_bank(self):
        student = User.objects.create_user(email='s@example.com', password='x', role='student')
        self.client.force_authenticate(student)
        self.assertEqual(self.client.get('/api/questions/').status_code, 403)
