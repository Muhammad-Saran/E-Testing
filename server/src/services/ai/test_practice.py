from django.test import override_settings
from rest_framework.test import APITestCase

from src.services.accounts.models import User
from src.services.courses.models import Course, Enrollment
from src.services.questionbank.models import Question
from .tests import SOURCE

RULE = override_settings(AI_ENGINE='rule', AI_ASYNC=False, DUPLICATE_THRESHOLD=0.85)


@RULE
class PracticeTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(email='s@example.com', password='x', role='student')
        self.teacher = User.objects.create_user(email='t@example.com', password='x', role='instructor')
        self.course = Course.objects.create(code='CSC101', title='Intro', instructor=self.teacher)
        self.other_course = Course.objects.create(code='CSC999', title='Other', instructor=self.teacher)
        Enrollment.objects.create(course=self.course, student=self.student)
        self.client.force_authenticate(self.student)

    def test_practice_flow_hides_answers_until_checked(self):
        res = self.client.post('/api/ai/practice/', {'source_text': SOURCE, 'count': 4, 'question_type': 'mixed'},
                               format='json')
        self.assertEqual(res.status_code, 202, res.data)
        job = res.data
        self.assertEqual(job['status'], 'done')
        self.assertEqual(len(job['questions']), 4)
        flat = str(job['questions'])
        self.assertNotIn('is_correct', flat)
        self.assertNotIn('correct_answer', flat)
        self.assertNotIn('candidates', job)

        answers = []
        for q in job['questions']:
            if q['question_type'] == 'short_answer':
                answers.append({'index': q['index'], 'answer_text': 'no idea'})
            else:
                answers.append({'index': q['index'], 'option_index': 0})
        result = self.client.post(f'/api/ai/practice/{job["id"]}/check/', {'answers': answers}, format='json').data
        self.assertEqual(result['total'], 4)
        self.assertEqual(len(result['questions']), 4)
        self.assertTrue(all(q['correct_answer'] for q in result['questions']))
        again = self.client.get(f'/api/ai/practice/{job["id"]}/').data
        self.assertEqual(again['practice_result']['score'], result['score'])

    def test_students_only_use_material_from_their_courses(self):
        res = self.client.post('/api/ai/practice/', {'source_text': SOURCE, 'course': self.other_course.id},
                               format='json')
        self.assertEqual(res.status_code, 400)

    def test_instructors_cannot_use_practice_and_students_cannot_use_the_generator(self):
        self.assertEqual(self.client.post('/api/ai/jobs/', {'source_text': SOURCE}, format='json').status_code, 403)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get('/api/ai/practice/').status_code, 403)


@RULE
class GeneratorExtrasTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(email='t@example.com', password='x', role='instructor')
        self.client.force_authenticate(self.teacher)

    def test_candidates_get_bloom_levels_and_duplicate_flags(self):
        first = self.client.post('/api/ai/jobs/', {'source_text': SOURCE, 'count': 3, 'question_type': 'short_answer'},
                                 format='json').data
        self.assertTrue(all(c['difficulty'] in ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')
                            for c in first['candidates']))
        # Save the first candidate, then generate again: it is now a duplicate.
        self.client.post(f'/api/ai/jobs/{first["id"]}/commit/', {'questions': first['candidates'][:1]}, format='json')
        second = self.client.post('/api/ai/jobs/', {'source_text': SOURCE, 'count': 3, 'question_type': 'short_answer'},
                                  format='json').data
        saved = Question.objects.get()
        dup = [c for c in second['candidates'] if c.get('duplicate_of')]
        self.assertEqual(len(dup), 1)
        self.assertEqual(dup[0]['duplicate_of']['id'], saved.id)

    def test_quality_option_is_stored(self):
        job = self.client.post('/api/ai/jobs/', {'source_text': SOURCE, 'count': 2, 'quality': 'better'},
                               format='json').data
        self.assertEqual(job['quality'], 'better')
        status = self.client.get('/api/ai/jobs/status/').data
        self.assertIn('better', status['question_generation']['models'])
