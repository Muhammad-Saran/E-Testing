from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from src.core.permissions import IsInstructorOrReadOnly
from .models import Course, CourseMaterial, Enrollment
from .serializers import CourseMaterialSerializer, CourseSerializer, EnrollmentSerializer


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
