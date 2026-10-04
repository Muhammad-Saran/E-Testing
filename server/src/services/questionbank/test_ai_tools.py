from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from src.services.accounts.models import User
from .bloom import suggest_level
from .models import Question


class BloomTests(SimpleTestCase):
    def test_levels_from_action_verbs(self):
        cases = {
            'Define a binary tree.': 'remember',
            'Who created Python?': 'remember',
            'Explain how a hash table handles collisions.': 'understand',
            'Calculate the time complexity of merge sort.': 'apply',
            'Compare TCP and UDP.': 'analyze',
            'Justify the choice of a B-tree index for this table.': 'evaluate',
            'Design a schema for a library system.': 'create',
            # the highest level mentioned wins
            'Describe and evaluate two scheduling algorithms.': 'evaluate',
        }
        for text, level in cases.items():
            self.assertEqual(suggest_level(text)[0], level, text)


@override_settings(AI_ENGINE='rule', SIMILAR_THRESHOLD=0.8, DUPLICATE_THRESHOLD=0.85)
class SimilarityApiTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(email='t@example.com', password='x', role='instructor')
        self.client.force_authenticate(self.teacher)
        make = lambda text: Question.objects.create(created_by=self.teacher, text=text, question_type='short_answer',
                                                    correct_answer_text='x')
        self.q1 = make('What is the time complexity of binary search on a sorted array?')
        self.q2 = make('What is the time complexity of a binary search on a sorted array?')
        self.q3 = make('Explain the purpose of database normalization.')
        other = User.objects.create_user(email='o@example.com', password='x', role='instructor')
        Question.objects.create(created_by=other, text='What is the time complexity of binary search?',
                                question_type='short_answer', correct_answer_text='x')

    def test_similar_questions_while_writing(self):
        res = self.client.post('/api/questions/similar/',
                               {'text': 'What is the time complexity of binary search in a sorted array?'}, format='json')
        ids = [m['id'] for m in res.data['matches']]
        self.assertEqual(res.data['engine'], 'lexical')
        self.assertIn(self.q1.id, ids)
        self.assertNotIn(self.q3.id, ids)
        self.assertEqual(len(ids), 2)  # never another instructor's questions
        res = self.client.post('/api/questions/similar/', {'text': self.q1.text, 'exclude': self.q1.id}, format='json')
        self.assertNotIn(self.q1.id, [m['id'] for m in res.data['matches']])

    def test_duplicate_pairs_in_the_bank(self):
        pairs = self.client.get('/api/questions/duplicates/').data['pairs']
        self.assertEqual(len(pairs), 1)
        self.assertEqual({pairs[0]['a']['id'], pairs[0]['b']['id']}, {self.q1.id, self.q2.id})

    def test_suggest_difficulty_endpoint(self):
        res = self.client.post('/api/questions/suggest_difficulty/', {'text': 'Compare stacks and queues'}, format='json')
        self.assertEqual(res.data, {'difficulty': 'analyze', 'cue': 'compare'})

    def test_required_keywords_are_normalised(self):
        res = self.client.post('/api/questions/', {
            'text': 'How does a stack work?', 'question_type': 'short_answer', 'difficulty': 'understand',
            'marks': 2, 'correct_answer_text': 'Last in first out', 'required_keywords': ' last in first out|LIFO ,, top ',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['required_keywords'], 'last in first out | LIFO, top')
