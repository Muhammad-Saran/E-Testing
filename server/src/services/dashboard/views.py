from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.services.courses.models import Course, Enrollment
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
                    'active_courses': courses.filter(is_active=True).count(),
                    'students': Enrollment.objects.filter(course__instructor=user)
                                          .values('student').distinct().count(),
                    'questions': questions.count(),
                    'ai_questions': questions.filter(is_ai_generated=True).count(),
                },
                'recent_courses': list(
                    courses.order_by('-created_at')[:5]
                    .values('id', 'code', 'title')
                ),
            }
        else:
            enrollments = Enrollment.objects.filter(student=user).select_related('course')
            data = {
                'role': 'student',
                'name': user.full_name,
                'stats': {
                    'enrolled_courses': enrollments.count(),
                    'upcoming_exams': 0,       # Module 4 (Phase 2)
                    'completed_exams': 0,      # Module 6 (Phase 2)
                },
                'enrolled_courses': [
                    {'id': e.course.id, 'code': e.course.code, 'title': e.course.title}
                    for e in enrollments[:10]
                ],
            }
        return Response(data)
