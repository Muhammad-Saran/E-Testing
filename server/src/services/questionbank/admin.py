from django.contrib import admin

from .models import Question, QuestionOption


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'question_type', 'difficulty', 'subject', 'marks', 'created_by', 'is_active']
    list_filter = ['question_type', 'difficulty', 'is_active', 'is_ai_generated']
    search_fields = ['text', 'subject']
    inlines = [QuestionOptionInline]
