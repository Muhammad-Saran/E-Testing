from django.contrib import admin

from .models import Course, CourseMaterial, Enrollment


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'instructor', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['code', 'title']


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'created_at']
    search_fields = ['student__email', 'course__code']


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'uploaded_by', 'created_at']
