from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from src.services.accounts.models import User
from src.services.courses.models import Course, Enrollment
from src.services.exams.models import Exam, ExamAttempt, ExamQuestion, ExamStatus
from src.services.questionbank.models import Question, QuestionOption
from .models import Notification, NotificationType
from .services import dispatch_scheduled


@override_settings(EXAM_REMINDER_MINUTES=[1440, 60], NOTIFICATION_EMAILS=True, AI_ENGINE='rule')
class NotificationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.teacher = User.objects.create_user(email='t@example.com', password='x', role='instructor')
        self.other_teacher = User.objects.create_user(email='t2@example.com', password='x', role='instructor')
        self.student = User.objects.create_user(email='s@example.com', password='x', role='student')
        self.course = Course.objects.create(code='CSC101', title='Intro', instructor=self.teacher)
        Enrollment.objects.create(course=self.course, student=self.student)
        self.question = Question.objects.create(created_by=self.teacher, text='2+2?', question_type='mcq')
        self.right = QuestionOption.objects.create(question=self.question, text='4', is_correct=True)
        QuestionOption.objects.create(question=self.question, text='5', is_correct=False)

    def make_exam(self, starts_in, length=timedelta(hours=1), status=ExamStatus.DRAFT, duration=10):
        start = timezone.now() + starts_in
        exam = Exam.objects.create(
            course=self.course, created_by=self.teacher, title='Quiz', status=status,
            available_from=start, available_until=start + length, duration_minutes=duration,
        )
        ExamQuestion.objects.create(exam=exam, question=self.question, marks=1)
        return exam

    def of_type(self, user, type):
        return Notification.objects.filter(user=user, type=type)

    def test_publishing_notifies_and_emails_enrolled_students(self):
        exam = self.make_exam(timedelta(hours=3))
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post(f'/api/exams/{exam.id}/publish/').status_code, 200)
        self.assertEqual(self.of_type(self.student, NotificationType.EXAM_PUBLISHED).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['s@example.com'])
        self.assertIn('Quiz', mail.outbox[0].subject)

    def test_reminder_sends_only_the_closest_interval_once(self):
        self.make_exam(timedelta(minutes=30), status=ExamStatus.PUBLISHED)
        dispatch_scheduled()
        dispatch_scheduled()
        reminders = self.of_type(self.student, NotificationType.EXAM_REMINDER)
        self.assertEqual(reminders.count(), 1)
        self.assertTrue(reminders.first().dedupe_key.endswith(':reminder:60'))

    def test_no_reminder_for_draft_or_far_future_exams(self):
        self.make_exam(timedelta(minutes=30))  # draft
        self.make_exam(timedelta(days=5), status=ExamStatus.PUBLISHED)
        self.assertEqual(dispatch_scheduled()['reminders'], 0)

    def test_results_ready_after_the_window_closes(self):
        exam = self.make_exam(-timedelta(hours=2), status=ExamStatus.PUBLISHED)
        attempt = ExamAttempt.objects.create(exam=exam, student=self.student,
                                             started_at=timezone.now() - timedelta(hours=2))
        dispatch_scheduled()
        attempt.refresh_from_db()
        self.assertTrue(attempt.is_submitted)  # expired attempt was auto-graded first
        self.assertEqual(self.of_type(self.teacher, NotificationType.EXAM_RESULTS_READY).count(), 1)
        self.assertEqual(self.of_type(self.student, NotificationType.ANSWERS_RELEASED).count(), 1)
        self.assertEqual(self.of_type(self.student, NotificationType.RESULT_PUBLISHED).count(), 1)
        dispatch_scheduled()
        self.assertEqual(self.of_type(self.teacher, NotificationType.EXAM_RESULTS_READY).count(), 1)

    def test_results_wait_for_students_still_writing(self):
        # Window ended a minute ago, but this student started just before it and has time left.
        exam = self.make_exam(-timedelta(minutes=61), status=ExamStatus.PUBLISHED, duration=30)
        ExamAttempt.objects.create(exam=exam, student=self.student, started_at=timezone.now() - timedelta(minutes=5))
        dispatch_scheduled()
        self.assertFalse(self.of_type(self.teacher, NotificationType.EXAM_RESULTS_READY).exists())

    def test_submitting_notifies_the_student_of_their_result(self):
        exam = self.make_exam(-timedelta(minutes=5), status=ExamStatus.PUBLISHED)
        self.client.force_authenticate(self.student)
        start = self.client.post(f'/api/exams/{exam.id}/start/')
        self.client.credentials(HTTP_X_EXAM_SESSION=start.data['session_key'])
        eq = exam.exam_questions.first()
        self.client.post(f'/api/exams/{exam.id}/submit/', {'answers': [
            {'exam_question_id': eq.id, 'selected_option_id': self.right.id}]}, format='json')
        note = self.of_type(self.student, NotificationType.RESULT_PUBLISHED).get()
        self.assertIn('1 / 1', note.message)
        self.assertTrue(note.emailed)

    def test_closing_an_exam_tells_the_instructor_results_are_ready(self):
        exam = self.make_exam(-timedelta(minutes=5), status=ExamStatus.PUBLISHED)
        self.client.force_authenticate(self.teacher)
        self.client.post(f'/api/exams/{exam.id}/close/')
        self.assertTrue(self.of_type(self.teacher, NotificationType.EXAM_RESULTS_READY).exists())

    def test_inbox_unread_count_and_mark_read(self):
        for i in range(3):
            Notification.objects.create(user=self.student, type=NotificationType.ANNOUNCEMENT, title=f'N{i}')
        mine = Notification.objects.filter(user=self.student).first()
        other = Notification.objects.create(user=self.teacher, type=NotificationType.ANNOUNCEMENT, title='Not yours')

        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get('/api/notifications/unread_count/').data['unread'], 3)
        self.assertEqual(self.client.get('/api/notifications/').data['count'], 3)
        self.assertTrue(self.client.post(f'/api/notifications/{mine.id}/read/').data['is_read'])
        self.assertEqual(self.client.get('/api/notifications/unread_count/').data['unread'], 2)
        self.assertEqual(self.client.post(f'/api/notifications/{other.id}/read/').status_code, 404)
        self.assertEqual(self.client.post('/api/notifications/mark_all_read/').data['updated'], 2)
        self.assertEqual(self.client.get('/api/notifications/unread_count/').data['unread'], 0)

    def test_instructor_announcement_reaches_enrolled_students(self):
        self.client.force_authenticate(self.teacher)
        res = self.client.post('/api/notifications/announce/', {
            'course': self.course.id, 'title': 'Quiz moved', 'message': 'Now on Friday.', 'email': True,
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['sent'], 1)
        self.assertEqual(self.of_type(self.student, NotificationType.ANNOUNCEMENT).get().title, 'CSC101: Quiz moved')
        self.assertEqual(len(mail.outbox), 1)

        # Students cannot announce, and instructors only to their own courses.
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post('/api/notifications/announce/', {}, format='json').status_code, 403)
        self.client.force_authenticate(self.other_teacher)
        res = self.client.post('/api/notifications/announce/', {
            'course': self.course.id, 'title': 'x', 'message': 'y'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_password_reset_sends_security_alert(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        self.student.set_password('Old-pass-123!')
        self.student.save()
        payload = {
            'uid': urlsafe_base64_encode(force_bytes(self.student.pk)),
            'token': default_token_generator.make_token(self.student),
            'password': 'N3w-strong-pass!', 'password_confirm': 'N3w-strong-pass!',
        }
        self.assertEqual(self.client.post('/api/auth/password-reset/confirm/', payload, format='json').status_code, 200)
        self.assertTrue(self.of_type(self.student, NotificationType.ACCOUNT_ACTIVITY).filter(
            title__icontains='password').exists())
        self.assertEqual(len(mail.outbox), 1)
