import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from src.services.accounts.models import User
from src.services.courses.models import Course, CourseMaterial
from src.services.notifications.models import Notification, NotificationType
from src.services.questionbank.models import Question
from src.services.questionbank.serializers import QuestionSerializer
from .engine import answer_similarity
from .generation import generate_questions, split_sentences

SOURCE = (
    'Python is a high-level programming language. It was created by Guido van Rossum and first released in 1991. '
    'A stack is a linear data structure that follows the Last In First Out principle. '
    'A queue is a linear data structure that follows the First In First Out principle. '
    'The TCP protocol provides reliable, ordered delivery of a stream of bytes between applications. '
    'HTTP is the foundation of data communication for the World Wide Web. '
    'Django is a Python web framework that encourages rapid development and clean design. '
    'SQLite is a C library that implements a small, fast, self-contained SQL database engine. '
    'React is a JavaScript library for building user interfaces, maintained by Meta. '
    'Binary search runs in logarithmic time on a sorted array of 1000 elements.'
)

# Tests use the rule-based engine so they run fast and without model downloads.
RULE = override_settings(AI_ENGINE='rule', AI_ASYNC=False)


@RULE
class GenerationTests(SimpleTestCase):
    def test_sentences_are_split_and_filtered(self):
        sentences = split_sentences('Too short. ' + SOURCE)
        self.assertNotIn('Too short.', sentences)
        self.assertEqual(len(sentences), 10)

    def test_headings_are_dropped_but_wrapped_lines_kept(self):
        text = ('Lecture 3: Stacks and Queues\n\nA stack is a linear data structure that follows LIFO order.\n'
                'Queues are used in breadth first\nSearch and in the scheduling of jobs.\n'
                '2.1 Binary Trees\nA binary tree node has at most two children in total.')
        self.assertEqual(split_sentences(text), [
            'A stack is a linear data structure that follows LIFO order.',
            'Queues are used in breadth first Search and in the scheduling of jobs.',
            'A binary tree node has at most two children in total.',
        ])

    def test_generates_valid_questions_of_each_type(self):
        for qtype in ('mcq', 'true_false', 'short_answer', 'mixed'):
            questions, engine_name = generate_questions(SOURCE, qtype, 5, seed=1)
            self.assertEqual(engine_name, 'rule')
            self.assertGreaterEqual(len(questions), 3, qtype)
            for q in questions:
                if qtype != 'mixed':
                    self.assertEqual(q['question_type'], qtype)
                if q['question_type'] == 'mcq':
                    self.assertEqual(sum(o['is_correct'] for o in q['options']), 1)
                    self.assertGreaterEqual(len(q['options']), 3)
                # Every candidate must be acceptable to the question bank as-is.
                payload = {k: q[k] for k in ('text', 'question_type', 'difficulty', 'marks',
                                             'correct_answer_text', 'options')}
                serializer = QuestionSerializer(data=payload)
                self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_generation_is_reproducible_with_a_seed(self):
        self.assertEqual(generate_questions(SOURCE, 'mixed', 5, seed=7), generate_questions(SOURCE, 'mixed', 5, seed=7))


@RULE
class SimilarityTests(SimpleTestCase):
    def test_short_factual_answers(self):
        self.assertEqual(answer_similarity('Islamabad', ' islamabad ')[0], 1.0)
        self.assertGreater(answer_similarity('Islamabad', 'Islamabd')[0], 0.9)   # typo
        self.assertLess(answer_similarity('Islamabad', 'Karachi')[0], 0.5)
        self.assertEqual(answer_similarity('1991', '1992')[0], 0.0)              # numbers exact
        self.assertEqual(answer_similarity('Islamabad', '')[0], 0.0)
        self.assertEqual(answer_similarity('A queue', 'queue')[0], 1.0)            # articles ignored

    def test_descriptive_answers_fall_back_to_lexical(self):
        ref = 'Normalization reduces data redundancy and improves data integrity'
        good, method = answer_similarity(ref, 'it reduces redundancy and improves integrity of data')
        bad, _ = answer_similarity(ref, 'photosynthesis happens in green plants')
        self.assertEqual(method, 'lexical')
        self.assertGreater(good, bad)


@RULE
class GenerationApiTests(APITestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.teacher = User.objects.create_user(email='t@example.com', password='x', role='instructor')
        self.other = User.objects.create_user(email='o@example.com', password='x', role='instructor')
        self.student = User.objects.create_user(email='s@example.com', password='x', role='student')
        self.course = Course.objects.create(code='CSC101', title='Intro', instructor=self.teacher)
        self.client.force_authenticate(self.teacher)

    def tearDown(self):
        shutil.rmtree(self.media, ignore_errors=True)

    def create_job(self, **extra):
        data = {'source_text': SOURCE, 'question_type': 'mixed', 'count': 4, 'course': self.course.id, **extra}
        return self.client.post('/api/ai/jobs/', data, format='json')

    def test_generate_review_and_commit_to_bank(self):
        res = self.create_job()
        self.assertEqual(res.status_code, 202)
        self.assertEqual(res.data['status'], 'done')
        self.assertEqual(res.data['engine'], 'rule')
        candidates = res.data['candidates']
        self.assertEqual(len(candidates), 4)
        self.assertTrue(Notification.objects.filter(
            user=self.teacher, type=NotificationType.AI_GENERATION_COMPLETE).exists())

        # The instructor edits the first candidate and keeps two of them.
        chosen = [dict(candidates[0], text='Edited: ' + candidates[0]['text'], marks=2), candidates[1]]
        res = self.client.post(f'/api/ai/jobs/{res.data["id"]}/commit/', {'questions': chosen}, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['created'], 2)
        saved = Question.objects.filter(created_by=self.teacher)
        self.assertEqual(saved.count(), 2)
        self.assertTrue(all(q.is_ai_generated and q.course_id == self.course.id for q in saved))
        self.assertTrue(saved.filter(text__startswith='Edited:', marks=2).exists())

    def test_invalid_candidate_is_reported_not_saved(self):
        job = self.create_job().data
        bad = dict(job['candidates'][0], question_type='mcq', options=[{'text': 'only one', 'is_correct': True}])
        res = self.client.post(f'/api/ai/jobs/{job["id"]}/commit/', {'questions': [bad]}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['failed'], 1)
        self.assertFalse(Question.objects.exists())

    def test_requires_enough_text(self):
        self.assertEqual(self.create_job(source_text='Too short.').status_code, 400)

    def test_generate_from_uploaded_material(self):
        with self.settings(MEDIA_ROOT=self.media):
            material = CourseMaterial.objects.create(
                course=self.course, title='Notes', uploaded_by=self.teacher,
                file=SimpleUploadedFile('notes.txt', SOURCE.encode()),
            )
            res = self.client.post('/api/ai/jobs/', {'material': material.id, 'count': 3}, format='json')
        self.assertEqual(res.status_code, 202, res.data)
        self.assertEqual(len(res.data['candidates']), 3)
        self.assertEqual(res.data['course'], self.course.id)

    def test_access_is_limited_to_the_owner(self):
        job = self.create_job().data
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/ai/jobs/{job["id"]}/').status_code, 404)
        self.assertEqual(self.create_job().status_code, 400)  # not their course
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get('/api/ai/jobs/').status_code, 403)

    def test_engine_status(self):
        res = self.client.get('/api/ai/jobs/status/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['question_generation']['available'])
