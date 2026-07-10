from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from src.core.permissions import IsInstructorOrReadOnly
from .models import Course, CourseMaterial, Enrollment
from .serializers import CourseMaterialSerializer, CourseSerializer, EnrollmentSerializer

User = get_user_model()


def _student_payload(student, enrollment):
    return {
        'enrollment_id': enrollment.id,
        'id': student.id,
        'full_name': student.full_name,
        'email': student.email,
        'registration_number': student.registration_number,
        'enrolled_at': enrollment.created_at,
    }


class CourseViewSet(viewsets.ModelViewSet):
    """Instructors manage their own courses; students see courses they can read."""
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsInstructorOrReadOnly]
    filterset_fields = ['is_active', 'instructor']
    search_fields = ['code', 'title']

    def get_queryset(self):
        user = self.request.user
        if user.is_instructor:
            return Course.objects.filter(instructor=user)
        # students: courses they are enrolled in
        return Course.objects.filter(enrollments__student=user).distinct()

    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)

    # -- Roster management (instructor adds students, scope doc Module 7/8) -----

    @action(detail=True, methods=['get'])
    def roster(self, request, pk=None):
        """List the students enrolled in this course."""
        course = self.get_object()
        enrollments = course.enrollments.select_related('student')
        return Response([_student_payload(e.student, e) for e in enrollments])

    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        """Enroll a student into this course by email or registration number."""
        course = self.get_object()
        identifier = (request.data.get('identifier') or '').strip()
        if not identifier:
            return Response({'detail': 'Enter a student email or registration number.'},
                            status=status.HTTP_400_BAD_REQUEST)

        student = (
            User.objects.filter(role='student')
            .filter(Q(email__iexact=identifier) | Q(registration_number__iexact=identifier))
            .first()
        )
        if not student:
            return Response(
                {'detail': f'No student found with email or registration number "{identifier}".'},
                status=status.HTTP_404_NOT_FOUND,
            )

        enrollment, created = Enrollment.objects.get_or_create(course=course, student=student)
        if not created:
            return Response({'detail': f'{student.full_name} is already enrolled.'},
                            status=status.HTTP_409_CONFLICT)
        return Response(_student_payload(student, enrollment), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def unenroll(self, request, pk=None):
        """Remove a student from this course."""
        course = self.get_object()
        student_id = request.data.get('student_id')
        deleted, _ = Enrollment.objects.filter(course=course, student_id=student_id).delete()
        if not deleted:
            return Response({'detail': 'That student is not enrolled in this course.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EnrollmentViewSet(viewsets.ModelViewSet):
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_instructor:
            return Enrollment.objects.filter(course__instructor=user)
        return Enrollment.objects.filter(student=user)

    def perform_create(self, serializer):
        # A student enrols themselves; an instructor may enrol a named student.
        if self.request.user.is_student:
            serializer.save(student=self.request.user)
        else:
            serializer.save()


class CourseMaterialViewSet(viewsets.ModelViewSet):
    serializer_class = CourseMaterialSerializer
    permission_classes = [IsAuthenticated, IsInstructorOrReadOnly]
    filterset_fields = ['course']

    def get_queryset(self):
        user = self.request.user
        if user.is_instructor:
            return CourseMaterial.objects.filter(course__instructor=user)
        return CourseMaterial.objects.filter(course__enrollments__student=user).distinct()

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)
