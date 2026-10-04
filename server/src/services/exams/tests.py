from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from src.services.accounts.models import User
from src.services.courses.models import Course, Enrollment
from src.services.questionbank.models import Question, QuestionOption
from .models import Exam, ExamAttempt, ExamQuestion, ExamStatus


@override_settings(AI_ENGINE='rule')
class ExamFlowTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(email='t@example.com', password='x', role='instructor')
        self.student = User.objects.create_user(email='s@example.com', password='x', role='student')
        self.other = User.objects.create_user(email='o@example.com', password='x', role='student')
        self.course = Course.objects.create(code='CSC101', title='Intro', instructor=self.teacher)
        Enrollment.objects.create(course=self.course, student=self.student)

        now = timezone.now()
        self.exam = Exam.objects.create(
            course=self.course, created_by=self.teacher, title='Quiz 1',
            available_from=now - timedelta(minutes=5), available_until=now + timedelta(hours=1),
            duration_minutes=10,
        )
        self.mcq = Question.objects.create(created_by=self.teacher, text='2+2?', question_type='mcq', marks=2)
        self.right = QuestionOption.objects.create(question=self.mcq, text='4', is_correct=True)
        self.wrong = QuestionOption.objects.create(question=self.mcq, text='5', is_correct=False)
        self.short = Question.objects.create(created_by=self.teacher, text='Capital of Pakistan?',
                                             question_type='short_answer', correct_answer_text='Islamabad')
        self.eq_mcq = ExamQuestion.objects.create(exam=self.exam, question=self.mcq, marks=2)
        self.eq_short = ExamQuestion.objects.create(exam=self.exam, question=self.short, marks=1)

    def as_user(self, user):
        self.client.force_authenticate(user)

    def start(self):
        """Start (or resume) the exam and send its session key with later requests."""
        res = self.client.post(f'/api/exams/{self.exam.id}/start/')
        if res.status_code == 200:
            self.client.credentials(HTTP_X_EXAM_SESSION=res.data['session_key'])
        return res

    def publish(self):
        self.as_user(self.teacher)
        return self.client.post(f'/api/exams/{self.exam.id}/publish/')

    def test_full_attempt_is_graded_with_feedback(self):
        self.assertEqual(self.publish().status_code, 200)
        self.as_user(self.student)
        start = self.start()
        self.assertEqual(start.status_code, 200)
        mcq = next(q for q in start.data['questions'] if q['id'] == self.eq_mcq.id)
        self.assertNotIn('is_correct', mcq['options'][0])

        res = self.client.post(f'/api/exams/{self.exam.id}/submit/', {'answers': [
            {'exam_question_id': self.eq_mcq.id, 'selected_option_id': self.right.id},
            {'exam_question_id': self.eq_short.id, 'answer_text': '  islamabad '},
        ]}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['score'], 3)
        self.assertEqual(res.data['percentage'], 100.0)
        self.assertEqual(res.data['class_average'], 3)
        self.assertEqual(len(res.data['questions']), 2)
        # The exam is still open, so correct answers are not revealed yet.
        self.assertFalse(res.data['answers_revealed'])
        self.assertIsNone(res.data['questions'][0]['correct_answer'])

        again = self.client.post(f'/api/exams/{self.exam.id}/submit/', {'answers': []}, format='json')
        self.assertEqual(again.status_code, 409)

    def test_saved_answers_are_graded_when_time_runs_out(self):
        self.publish()
        self.as_user(self.student)
        self.start()
        self.client.post(f'/api/exams/{self.exam.id}/save/', {'answers': [
            {'exam_question_id': self.eq_mcq.id, 'selected_option_id': self.right.id},
        ]}, format='json')

        # Move the attempt's start into the past so its 10 minutes are over.
        ExamAttempt.objects.filter(exam=self.exam).update(started_at=timezone.now() - timedelta(minutes=30))

        late = self.client.post(f'/api/exams/{self.exam.id}/submit/', {'answers': [
            {'exam_question_id': self.eq_short.id, 'answer_text': 'Islamabad'},
        ]}, format='json')
        # Late payload ignored — only the answer saved in time counts.
        self.assertEqual(late.status_code, 200)
        self.assertEqual(late.data['score'], 2)
        self.assertTrue(late.data['auto_submitted'])

    def test_expired_attempts_are_finalised_without_a_submit(self):
        self.publish()
        self.as_user(self.student)
        self.start()
        ExamAttempt.objects.filter(exam=self.exam).update(started_at=timezone.now() - timedelta(minutes=30))
        listing = self.client.get('/api/exams/available/')
        self.assertTrue(listing.data[0]['attempted'])
        self.assertTrue(ExamAttempt.objects.get(exam=self.exam).auto_submitted)

    def test_question_order_is_stable_for_a_student(self):
        self.publish()
        self.as_user(self.student)
        first = [q['id'] for q in self.start().data['questions']]
        second = [q['id'] for q in self.start().data['questions']]
        self.assertEqual(first, second)

    def test_tab_switches_are_logged_and_reported(self):
        self.publish()
        self.as_user(self.student)
        self.start()
        self.client.post(f'/api/exams/{self.exam.id}/proctor-event/', {'event_type': 'tab_switch'}, format='json')
        res = self.client.post(f'/api/exams/{self.exam.id}/proctor-event/', {'event_type': 'tab_switch'}, format='json')
        self.assertEqual(res.data['tab_switches'], 2)
        self.client.post(f'/api/exams/{self.exam.id}/submit/', {'answers': []}, format='json')

        self.as_user(self.teacher)
        analytics = self.client.get(f'/api/exams/{self.exam.id}/analytics/')
        self.assertEqual(analytics.data['results'][0]['tab_switches'], 2)
        self.assertEqual(analytics.data['summary']['submitted'], 1)
        export = self.client.get(f'/api/exams/{self.exam.id}/export/')
        self.assertEqual(export.status_code, 200)
        self.assertIn('s@example.com', export.content.decode('utf-8-sig'))

    def test_unenrolled_student_cannot_start(self):
        self.publish()
        self.as_user(self.other)
        self.assertEqual(self.start().status_code, 403)

    def test_student_cannot_self_enroll(self):
        self.as_user(self.other)
        res = self.client.post('/api/courses/enrollments/', {'course': self.course.id}, format='json')
        self.assertEqual(res.status_code, 405)

    def test_draft_and_scheduled_states(self):
        self.assertEqual(self.exam.state, 'draft')
        self.exam.available_from = timezone.now() + timedelta(days=1)
        self.exam.available_until = timezone.now() + timedelta(days=2)
        self.exam.status = ExamStatus.PUBLISHED
        self.exam.save()
        self.assertEqual(self.exam.state, 'scheduled')
        self.as_user(self.student)
        self.assertEqual(self.start().status_code, 403)

    def test_overlapping_exam_for_same_cohort_is_rejected(self):
        self.publish()
        clash = Exam.objects.create(
            course=self.course, created_by=self.teacher, title='Quiz 2',
            available_from=self.exam.available_from + timedelta(minutes=10),
            available_until=self.exam.available_until + timedelta(hours=1),
        )
        ExamQuestion.objects.create(exam=clash, question=self.mcq)
        res = self.client.post(f'/api/exams/{clash.id}/publish/')
        self.assertEqual(res.status_code, 409)

    def test_questions_in_published_exam_are_locked(self):
        self.publish()
        res = self.client.patch(f'/api/questions/{self.mcq.id}/', {'text': 'changed'}, format='json')
        self.assertEqual(res.status_code, 409)
        self.assertEqual(self.client.delete(f'/api/questions/{self.mcq.id}/').status_code, 409)
        res = self.client.post(f'/api/exams/{self.exam.id}/remove_question/',
                               {'exam_question_id': self.eq_mcq.id}, format='json')
        self.assertEqual(res.status_code, 409)

    def test_close_submits_open_attempts_and_reveals_answers(self):
        self.publish()
        self.as_user(self.student)
        self.start()
        self.as_user(self.teacher)
        self.assertEqual(self.client.post(f'/api/exams/{self.exam.id}/close/').data['state'], 'closed')
        self.as_user(self.student)
        result = self.client.get(f'/api/exams/{self.exam.id}/result/')
        self.assertTrue(result.data['answers_revealed'])
        self.assertEqual(result.data['questions'][0]['correct_answer'] in ('4', 'Islamabad'), True)

    def test_instructor_cannot_create_exam_on_another_course(self):
        other_teacher = User.objects.create_user(email='t2@example.com', password='x', role='instructor')
        self.as_user(other_teacher)
        res = self.client.post('/api/exams/', {
            'course': self.course.id, 'title': 'X',
            'available_from': timezone.now().isoformat(),
            'available_until': (timezone.now() + timedelta(hours=1)).isoformat(),
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_short_answers_get_full_partial_or_no_credit(self):
        self.eq_short.marks = 4
        self.eq_short.save()
        self.publish()
        self.as_user(self.student)
        self.start()
        res = self.client.post(f'/api/exams/{self.exam.id}/submit/', {'answers': [
            {'exam_question_id': self.eq_short.id, 'answer_text': 'Islamabd'},  # typo: still correct
        ]}, format='json')
        short = next(q for q in res.data['questions'] if q['exam_question_id'] == self.eq_short.id)
        self.assertTrue(short['is_correct'])
        self.assertEqual(short['awarded_marks'], 4)
        self.assertEqual(short['grading_method'], 'fuzzy')
        self.assertGreaterEqual(short['similarity'], 90)

    @override_settings(SHORT_ANSWER_THRESHOLD=0.95, SHORT_ANSWER_PARTIAL_THRESHOLD=0.8)
    def test_near_miss_short_answer_earns_half_marks(self):
        self.eq_short.marks = 4
        self.eq_short.save()
        self.publish()
        self.as_user(self.student)
        self.start()
        res = self.client.post(f'/api/exams/{self.exam.id}/submit/', {'answers': [
            {'exam_question_id': self.eq_short.id, 'answer_text': 'Islamabd'},
        ]}, format='json')
        short = next(q for q in res.data['questions'] if q['exam_question_id'] == self.eq_short.id)
        self.assertFalse(short['is_correct'])
        self.assertTrue(short['is_partial'])
        self.assertEqual(short['awarded_marks'], 2)
        self.assertEqual(res.data['score'], 2)

    def test_answers_stay_hidden_while_a_classmate_is_still_writing(self):
        self.publish()
        Enrollment.objects.create(course=self.course, student=self.other)
        for student in (self.other, self.student):
            self.as_user(student)
            self.start()
        self.as_user(self.student)
        self.client.post(f'/api/exams/{self.exam.id}/submit/', {'answers': []}, format='json')
        # The window ends, but the classmate who started in time still has minutes left.
        Exam.objects.filter(pk=self.exam.pk).update(available_until=timezone.now() - timedelta(seconds=1))
        result = self.client.get(f'/api/exams/{self.exam.id}/result/')
        self.assertFalse(result.data['answers_revealed'])
        # Once their time is up the key is released.
        ExamAttempt.objects.filter(student=self.other).update(started_at=timezone.now() - timedelta(minutes=30))
        self.assertTrue(self.client.get(f'/api/exams/{self.exam.id}/result/').data['answers_revealed'])

    def test_student_performance_timeline(self):
        self.publish()
        self.as_user(self.student)
        self.start()
        self.client.post(f'/api/exams/{self.exam.id}/submit/', {'answers': [
            {'exam_question_id': self.eq_mcq.id, 'selected_option_id': self.right.id},
        ]}, format='json')

        self.as_user(self.teacher)
        students = self.client.get('/api/exams/students/').data
        self.assertEqual([s['id'] for s in students], [self.student.id])
        res = self.client.get('/api/exams/student_timeline/', {'student': self.student.id})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['summary']['exams_taken'], 1)
        self.assertEqual(res.data['timeline'][0]['score'], 2)
        # Students outside the instructor's courses are not visible.
        self.assertEqual(self.client.get('/api/exams/student_timeline/', {'student': self.other.id}).status_code, 404)
