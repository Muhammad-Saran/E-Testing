"""Question pools, option shuffling, exam security, short-answer review and analytics."""
from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from src.services.accounts.models import User
from src.services.courses.models import Course, Enrollment
from src.services.notifications.models import Notification
from src.services.questionbank.models import Question, QuestionOption
from .models import Exam, ExamAnswer, ExamAttempt, ExamQuestion, ExamStatus, ProctorEvent
from .services import attempt_questions, shuffled_options


@override_settings(AI_ENGINE='rule')
class FeatureTestBase(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(email='t@example.com', password='x', role='instructor')
        self.students = [User.objects.create_user(email=f's{i}@example.com', password='x', role='student')
                         for i in range(6)]
        self.course = Course.objects.create(code='CSC201', title='Data Structures', instructor=self.teacher)
        for s in self.students:
            Enrollment.objects.create(course=self.course, student=s)
        now = timezone.now()
        self.exam = Exam.objects.create(
            course=self.course, created_by=self.teacher, title='Quiz',
            available_from=now - timedelta(minutes=5), available_until=now + timedelta(hours=1), duration_minutes=10,
        )

    def mcq(self, text, n_options=4, marks=1):
        q = Question.objects.create(created_by=self.teacher, text=text, question_type='mcq', marks=marks)
        options = [QuestionOption.objects.create(question=q, text=f'{text} option {i}', is_correct=i == 0, order=i)
                   for i in range(n_options)]
        eq = ExamQuestion.objects.create(exam=self.exam, question=q, marks=marks, order=self.exam.pool_size)
        return eq, options

    def short(self, text, answer, keywords='', marks=4):
        q = Question.objects.create(created_by=self.teacher, text=text, question_type='short_answer',
                                    correct_answer_text=answer, required_keywords=keywords, marks=marks)
        return ExamQuestion.objects.create(exam=self.exam, question=q, marks=marks, order=self.exam.pool_size)

    def as_user(self, user):
        self.client.force_authenticate(user)
        self.client.credentials()

    def publish(self):
        self.as_user(self.teacher)
        return self.client.post(f'/api/exams/{self.exam.id}/publish/')

    def start(self, student, header=True):
        self.client.force_authenticate(student)
        res = self.client.post(f'/api/exams/{self.exam.id}/start/')
        if header and res.status_code == 200:
            self.client.credentials(HTTP_X_EXAM_SESSION=res.data['session_key'])
        return res


class QuestionPoolTests(FeatureTestBase):
    def test_each_student_gets_a_subset_of_the_pool(self):
        eqs = [self.mcq(f'Q{i}')[0] for i in range(8)]
        self.exam.questions_per_student = 3
        self.exam.save()
        self.assertEqual(self.publish().status_code, 200)
        self.assertEqual(self.exam.total_marks, 3)

        sets = set()
        for student in self.students:
            data = self.start(student).data
            self.assertEqual(len(data['questions']), 3)
            self.assertEqual(data['exam']['total_marks'], 3)
            sets.add(frozenset(q['id'] for q in data['questions']))
        self.assertGreater(len(sets), 1, 'students should not all get the same questions')

        # Grading only covers the questions this student received.
        student = self.students[0]
        res = self.start(student)
        mine = [q['id'] for q in res.data['questions']]
        res = self.client.post(f'/api/exams/{self.exam.id}/submit/', {'answers': []}, format='json')
        self.assertEqual(sorted(q['exam_question_id'] for q in res.data['questions']), sorted(mine))
        self.assertEqual(res.data['total_marks'], 3)
        self.assertEqual(ExamAnswer.objects.filter(attempt__student=student).count(), 3)
        self.assertTrue(set(mine) <= {eq.id for eq in eqs})

    def test_answers_to_questions_outside_the_subset_are_ignored(self):
        eqs = [self.mcq(f'Q{i}') for i in range(5)]
        self.exam.questions_per_student = 2
        self.exam.save()
        self.publish()
        res = self.start(self.students[0])
        mine = {q['id'] for q in res.data['questions']}
        outsider_eq, options = next((eq, o) for eq, o in eqs if eq.id not in mine)
        self.client.post(f'/api/exams/{self.exam.id}/save/', {'answers': [
            {'exam_question_id': outsider_eq.id, 'selected_option_id': options[0].id}]}, format='json')
        self.assertFalse(ExamAnswer.objects.filter(exam_question=outsider_eq).exists())

    def test_publish_requires_equal_marks_and_a_big_enough_pool(self):
        self.mcq('A', marks=1)
        self.mcq('B', marks=2)
        self.mcq('C', marks=1)
        self.exam.questions_per_student = 5
        self.exam.save()
        self.assertEqual(self.publish().status_code, 400)  # pool too small
        self.exam.questions_per_student = 2
        self.exam.save()
        res = self.publish()
        self.assertEqual(res.status_code, 400)
        self.assertIn('same marks', res.data['detail'])


class OptionShuffleTests(FeatureTestBase):
    def test_options_are_shuffled_per_student_without_answers(self):
        eq, options = self.mcq('Which structure is LIFO?', n_options=5)
        self.publish()
        orders = set()
        for student in self.students:
            data = self.start(student).data
            q = data['questions'][0]
            self.assertNotIn('is_correct', q['options'][0])
            self.assertEqual({o['id'] for o in q['options']}, {o.id for o in options})
            attempt = ExamAttempt.objects.get(student=student)
            self.assertEqual([o['id'] for o in q['options']], [o.id for o in shuffled_options(attempt, eq)])
            orders.add(tuple(o['id'] for o in q['options']))
        self.assertGreater(len(orders), 1)

    def test_shuffle_can_be_turned_off(self):
        eq, options = self.mcq('Q', n_options=5)
        self.exam.shuffle_options = False
        self.exam.save()
        self.publish()
        q = self.start(self.students[0]).data['questions'][0]
        self.assertEqual([o['id'] for o in q['options']], [o.id for o in options])


class ExamSecurityTests(FeatureTestBase):
    def test_second_device_takes_over_and_the_first_is_locked_out(self):
        self.mcq('Q1')
        self.publish()
        student = self.students[0]
        first = self.start(student).data['session_key']
        # A second browser (no session header) opens the same exam.
        self.client.credentials()
        second = self.client.post(f'/api/exams/{self.exam.id}/start/').data['session_key']
        self.assertNotEqual(first, second)
        self.assertTrue(ProctorEvent.objects.filter(event_type='new_session').exists())

        self.client.credentials(HTTP_X_EXAM_SESSION=first)
        res = self.client.post(f'/api/exams/{self.exam.id}/save/', {'answers': []}, format='json')
        self.assertEqual(res.status_code, 409)
        self.assertTrue(res.data['session_replaced'])
        self.client.credentials(HTTP_X_EXAM_SESSION=second)
        self.assertEqual(self.client.post(f'/api/exams/{self.exam.id}/save/', {'answers': []},
                                          format='json').status_code, 200)

    def test_reload_in_the_same_tab_is_not_a_violation(self):
        self.mcq('Q1')
        self.publish()
        self.start(self.students[0])
        self.start(self.students[0])  # same header -> same session, resumed
        self.assertFalse(ProctorEvent.objects.exists())

    def test_reaching_the_violation_limit_submits_the_exam(self):
        self.mcq('Q1')
        self.exam.max_violations = 2
        self.exam.require_fullscreen = True
        self.exam.save()
        self.publish()
        data = self.start(self.students[0]).data
        self.assertTrue(data['exam']['require_fullscreen'])
        url = f'/api/exams/{self.exam.id}/proctor-event/'
        self.assertEqual(self.client.post(url, {'event_type': 'copy_paste'}, format='json').data['violations'], 0)
        self.assertFalse(self.client.post(url, {'event_type': 'tab_switch'}, format='json').data.get('terminated'))
        res = self.client.post(url, {'event_type': 'fullscreen_exit'}, format='json')
        self.assertTrue(res.data['terminated'])
        attempt = ExamAttempt.objects.get(student=self.students[0])
        self.assertTrue(attempt.is_submitted)
        self.assertEqual(attempt.submit_reason, 'violations')
        self.assertEqual(self.client.post(url, {'event_type': 'tab_switch'}, format='json').status_code, 409)

    def test_closing_records_the_reason(self):
        self.mcq('Q1')
        self.publish()
        self.start(self.students[0])
        self.as_user(self.teacher)
        self.client.post(f'/api/exams/{self.exam.id}/close/')
        self.assertEqual(ExamAttempt.objects.get().submit_reason, 'closed')


class ShortAnswerReviewTests(FeatureTestBase):
    def submit_short(self, student, text):
        self.start(student)
        eq = attempt_questions(ExamAttempt.objects.get(student=student))[0]
        return self.client.post(f'/api/exams/{self.exam.id}/submit/', {'answers': [
            {'exam_question_id': eq.id, 'answer_text': text}]}, format='json')

    def test_missing_required_keywords_cap_the_marks_and_flag_for_review(self):
        self.short('How does a stack remove items?', 'A stack removes the most recently added item first, last in first out',
                   keywords='last in first out|lifo')
        self.publish()
        res = self.submit_short(self.students[0], 'A stack removes items in first in first out order')
        q = res.data['questions'][0]
        self.assertFalse(q['is_correct'])
        self.assertEqual(q['awarded_marks'], 0)  # its only key term is missing
        res = self.submit_short(self.students[1], 'The last item pushed is popped first - LIFO')
        self.assertEqual(ExamAnswer.objects.get(attempt__student=self.students[1]).grading_method, 'lexical')

    def test_instructor_reviews_and_changes_marks(self):
        eq = self.short('Define normalization', 'Normalization reduces data redundancy and improves data integrity',
                        keywords='redundancy, integrity')
        self.publish()
        self.submit_short(self.students[0], 'Normalization reduces data redundancy and improves data consistency')
        answer = ExamAnswer.objects.get(exam_question=eq)
        self.assertTrue(answer.needs_review)
        self.assertLessEqual(answer.awarded_marks, 2)

        self.as_user(self.teacher)
        listing = self.client.get(f'/api/exams/{self.exam.id}/reviews/')
        self.assertEqual(len(listing.data), 1)
        self.assertEqual(listing.data[0]['missing_keywords'], ['integrity'])

        url = f'/api/exams/{self.exam.id}/review/'
        self.assertEqual(self.client.post(url, {'answer_id': answer.id, 'awarded_marks': 9}, format='json').status_code, 400)
        mail.outbox.clear()
        res = self.client.post(url, {'answer_id': answer.id, 'awarded_marks': 3, 'note': 'Close enough'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['attempt_score'], 3)
        answer.refresh_from_db()
        self.assertFalse(answer.needs_review)
        self.assertEqual(answer.awarded_marks, 3)
        self.assertIsNotNone(answer.reviewed_at)
        self.assertEqual(ExamAttempt.objects.get(student=self.students[0]).score, 3)
        self.assertTrue(Notification.objects.filter(user=self.students[0], title__startswith='Mark reviewed').exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.get(f'/api/exams/{self.exam.id}/reviews/').data, [])
        self.assertEqual(len(self.client.get(f'/api/exams/{self.exam.id}/reviews/', {'all': 1}).data), 1)

        other = User.objects.create_user(email='t2@example.com', password='x', role='instructor')
        self.as_user(other)
        self.assertEqual(self.client.post(url, {'answer_id': answer.id, 'awarded_marks': 0}, format='json').status_code, 404)


class AnalyticsTests(FeatureTestBase):
    def test_item_analysis_and_course_trend(self):
        eq1, opts1 = self.mcq('Easy question')
        eq2, opts2 = self.mcq('Hard question')
        self.exam.shuffle_questions = False
        self.exam.save()
        self.publish()
        # Students 0-2 answer both right, 3-5 only the easy one.
        for i, student in enumerate(self.students):
            self.start(student)
            pick = opts2[0] if i < 3 else opts2[1]
            self.client.post(f'/api/exams/{self.exam.id}/submit/', {'answers': [
                {'exam_question_id': eq1.id, 'selected_option_id': opts1[0].id},
                {'exam_question_id': eq2.id, 'selected_option_id': pick.id}]}, format='json')

        self.as_user(self.teacher)
        data = self.client.get(f'/api/exams/{self.exam.id}/analytics/').data
        easy, hard = data['questions']
        self.assertEqual(easy['accuracy'], 100.0)
        self.assertEqual(easy['discrimination'], 0)
        self.assertEqual(hard['accuracy'], 50.0)
        self.assertEqual(hard['discrimination'], 1.0)
        self.assertEqual(hard['discrimination_label'], 'Excellent')
        counts = {o['text']: o['count'] for o in hard['options']}
        self.assertEqual(counts['Hard question option 0'], 3)
        self.assertEqual(counts['Hard question option 1'], 3)
        self.assertEqual(data['summary']['pass_rate'], 100.0)
        self.assertEqual(data['summary']['median_percentage'], 75.0)

        trend = self.client.get('/api/exams/course_analytics/', {'course': self.course.id}).data
        self.assertEqual(trend['summary']['exams'], 1)
        self.assertEqual(trend['timeline'][0]['submitted'], 6)
        self.assertEqual(trend['top_students'][0]['average_percentage'], 100.0)
        self.assertEqual(trend['at_risk'], [])
