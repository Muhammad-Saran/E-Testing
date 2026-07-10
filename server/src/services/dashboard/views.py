from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils import timezone

from src.services.courses.models import Course, Enrollment
from src.services.exams.models import Exam, ExamAttempt, ExamStatus
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
            courses = Course.objects.filter(instructor=user)
            questions = Question.objects.filter(created_by=user)
            data = {
                'role': 'instructor',
                'name': user.full_name,
                'stats': {
                    'courses': courses.count(),
                    'students': Enrollment.objects.filter(course__instructor=user)
                                          .values('student').distinct().count(),
                    'questions': questions.count(),
                    'exams': Exam.objects.filter(created_by=user).count(),
                },
                'recent_courses': list(
                    courses.order_by('-created_at')[:5]
                    .values('id', 'code', 'title')
                ),
            }
        else:
            enrollments = Enrollment.objects.filter(student=user).select_related('course')
            course_ids = enrollments.values_list('course_id', flat=True)
            now = timezone.now()
            submitted_exam_ids = ExamAttempt.objects.filter(
                student=user, is_submitted=True).values_list('exam_id', flat=True)
            open_exams = Exam.objects.filter(
                course_id__in=course_ids, status=ExamStatus.PUBLISHED,
                available_from__lte=now, available_until__gte=now,
            ).exclude(id__in=submitted_exam_ids)
            data = {
                'role': 'student',
                'name': user.full_name,
                'stats': {
                    'enrolled_courses': enrollments.count(),
                    'upcoming_exams': open_exams.count(),
                    'completed_exams': len(submitted_exam_ids),
                },
                'enrolled_courses': [
                    {'id': e.course.id, 'code': e.course.code, 'title': e.course.title}
                    for e in enrollments[:10]
                ],
            }
        return Response(data)
