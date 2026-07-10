from django.conf import settings
from django.db import models

from src.core.models import TimeStampedModel


class Course(TimeStampedModel):
    """A course owned by an instructor. Students enrol to gain access."""
    code = models.CharField(max_length=20, unique=True, help_text='e.g. CSC336')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='courses_taught', limit_choices_to={'role': 'instructor'},
    )
    is_active = models.BooleanField(default=True)

    class Meta(TimeStampedModel.Meta):
        indexes = [models.Index(fields=['instructor', 'is_active'])]

    def __str__(self):
        return f'{self.code} — {self.title}'


class Enrollment(TimeStampedModel):
    """Join table linking a student to a course."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='enrollments', limit_choices_to={'role': 'student'},
    )

    class Meta(TimeStampedModel.Meta):
        unique_together = ('course', 'student')

    def __str__(self):
        return f'{self.student} in {self.course.code}'


class CourseMaterial(TimeStampedModel):
    """Lecture notes / resources uploaded by an instructor (scope doc, Module 7)."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='course_materials/')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='uploaded_materials',
    )

    def __str__(self):
        return self.title
