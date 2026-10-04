from django.contrib import admin

from .models import GenerationJob


@admin.register(GenerationJob)
class GenerationJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_by', 'course', 'question_type', 'count', 'status', 'engine', 'saved_count', 'created_at']
    list_filter = ['status', 'engine', 'question_type']
    readonly_fields = ['candidates']
