from django_filters import rest_framework as filters

from .models import Question


class QuestionFilter(filters.FilterSet):
    subject = filters.CharFilter(field_name='subject', lookup_expr='icontains')

    class Meta:
        model = Question
        fields = ['course', 'question_type', 'difficulty', 'subject', 'is_active', 'is_ai_generated']
