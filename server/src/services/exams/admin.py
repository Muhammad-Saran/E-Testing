from django.contrib import admin

from .models import Exam, ExamAnswer, ExamAttempt, ExamQuestion, ProctorEvent


class ExamQuestionInline(admin.TabularInline):
    model = ExamQuestion
    extra = 0


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'status', 'available_from', 'available_until', 'duration_minutes']
    list_filter = ['status', 'course']
    search_fields = ['title']
    inlines = [ExamQuestionInline]


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ['exam', 'student', 'is_submitted', 'auto_submitted', 'score', 'started_at', 'submitted_at']
    list_filter = ['is_submitted', 'exam']

    def has_change_permission(self, request, obj=None):
        # Results are immutable once computed.
        return False


@admin.register(ProctorEvent)
class ProctorEventAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'event_type', 'occurred_at']
    list_filter = ['event_type']


admin.site.register(ExamAnswer)
