from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.services.ai.models import GenerationJob, JobStatus
from src.services.courses.models import Course, Enrollment
from src.services.exams.models import Exam, ExamAnswer, ExamAttempt, ExamState, ExamStatus
from src.services.exams.services import finalize_expired, percentage
from src.services.notifications.models import Notification, NotificationType
from src.services.questionbank.models import Question


class DashboardSummaryView(APIView):
    """
    GET /api/dashboard/summary/ — role-aware at-a-glance stats
    (scope doc, Modules 7 & 8). Returns a different payload per role.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_instructor:
            return Response(self._instructor(user))
        return Response(self._student(user))

    def _instructor(self, user):
        courses = Course.objects.filter(instructor=user)
        exams = Exam.objects.filter(created_by=user).select_related('course')
        finalize_expired(ExamAttempt.objects.filter(exam__created_by=user))
        now = timezone.now()

        recent_exams = []
        active = 0
        annotated = exams.annotate(
            submitted=Count('attempts', filter=Q(attempts__is_submitted=True)),
            average=Avg('attempts__score', filter=Q(attempts__is_submitted=True)),
        ).order_by('-available_from')
        for exam in annotated:
            state = exam.state_at(now)
            if state == ExamState.ACTIVE:
                active += 1
            if len(recent_exams) < 6:
                total = exam.total_marks
                recent_exams.append({
                    'id': exam.id,
                    'title': exam.title,
                    'course_code': exam.course.code,
                    'state': state,
                    'available_from': exam.available_from,
                    'submitted': exam.submitted,
                    'average_percentage': percentage(exam.average, total) if exam.average is not None else None,
                })

        # AI-generated questions waiting for the instructor's review (Module 3).
        unreviewed = GenerationJob.objects.filter(created_by=user, status=JobStatus.DONE, saved_count=0)
        pending_review = sum(len(j.candidates) for j in unreviewed.only('candidates'))

        return {
            'role': 'instructor',
            'name': user.full_name,
            'stats': {
                'courses': courses.count(),
                'students': Enrollment.objects.filter(course__instructor=user)
                                      .values('student').distinct().count(),
                'questions': Question.objects.filter(created_by=user).count(),
                'exams': exams.count(),
                'active_exams': active,
                'submissions': ExamAttempt.objects.filter(exam__created_by=user, is_submitted=True).count(),
                'pending_review': pending_review,
                'answers_to_review': ExamAnswer.objects.filter(attempt__exam__created_by=user,
                                                               attempt__is_submitted=True, needs_review=True).count(),
            },
            'recent_submissions': [
                {
                    'exam_id': a.exam_id, 'exam_title': a.exam.title, 'course_code': a.exam.course.code,
                    'student_name': a.student.full_name, 'submitted_at': a.submitted_at,
                    'percentage': percentage(a.score, a.exam.total_marks), 'submit_reason': a.submit_reason,
                }
                for a in ExamAttempt.objects.filter(exam__created_by=user, is_submitted=True)
                .select_related('exam__course', 'student').order_by('-submitted_at')[:6]
            ],
            'recent_courses': list(courses.order_by('-created_at')[:5].values('id', 'code', 'title')),
            'recent_exams': recent_exams,
        }

    def _student(self, user):
        finalize_expired(ExamAttempt.objects.filter(student=user))
        enrollments = Enrollment.objects.filter(student=user).select_related('course')
        course_ids = list(enrollments.values_list('course_id', flat=True))
        now = timezone.now()
        attempts = {a.exam_id: a for a in ExamAttempt.objects.filter(student=user)}

        # Exams still ahead of the student: scheduled, or active and not yet submitted.
        upcoming = []
        pending = (Exam.objects.filter(course_id__in=course_ids, status=ExamStatus.PUBLISHED,
                                       available_until__gte=now)
                   .select_related('course').order_by('available_from'))
        for exam in pending:
            attempt = attempts.get(exam.id)
            if attempt and attempt.is_submitted:
                continue
            upcoming.append({
                'id': exam.id,
                'title': exam.title,
                'course_code': exam.course.code,
                'state': exam.state_at(now),
                'available_from': exam.available_from,
                'available_until': exam.available_until,
                'duration_minutes': exam.duration_minutes,
                'in_progress': bool(attempt),
            })

        submitted = [a for a in attempts.values() if a.is_submitted]
        recent = (ExamAttempt.objects.filter(student=user, is_submitted=True)
                  .select_related('exam__course').order_by('-submitted_at')[:8])
        recent_results = []
        for a in recent:
            total = a.exam.total_marks
            recent_results.append({
                'exam_id': a.exam_id,
                'exam_title': a.exam.title,
                'course_code': a.exam.course.code,
                'score': a.score,
                'total_marks': total,
                'percentage': percentage(a.score, total),
                'submitted_at': a.submitted_at,
            })

        return {
            'role': 'student',
            'name': user.full_name,
            'server_time': now,
            'stats': {
                'enrolled_courses': len(course_ids),
                'upcoming_exams': len(upcoming),
                'completed_exams': len(submitted),
                'average_percentage': round(sum(r['percentage'] for r in recent_results) / len(recent_results), 1)
                if recent_results else None,
                'best_percentage': max((r['percentage'] for r in recent_results), default=None),
            },
            'enrolled_courses': [
                {'id': e.course.id, 'code': e.course.code, 'title': e.course.title}
                for e in enrollments[:10]
            ],
            'upcoming_exams': upcoming,
            'recent_results': recent_results,
            # Notifications from instructors (scope doc, Module 7).
            'announcements': [
                {'id': n.id, 'title': n.title, 'message': n.message, 'created_at': n.created_at, 'is_read': n.is_read}
                for n in Notification.objects.filter(user=user, type=NotificationType.ANNOUNCEMENT)[:5]
            ],
        }
