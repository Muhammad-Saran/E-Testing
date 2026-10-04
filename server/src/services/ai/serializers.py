from django.conf import settings
from rest_framework import serializers

from src.services.courses.models import Enrollment
from .models import GenerationJob


class GenerationJobSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True, default=None)
    material_title = serializers.CharField(source='material.title', read_only=True, default=None)
    source_preview = serializers.SerializerMethodField()
    # Write-only: the text may come from the request or from a course material.
    source_text = serializers.CharField(write_only=True, required=False, allow_blank=True)

    MAX_COUNT = 30

    class Meta:
        model = GenerationJob
        fields = [
            'id', 'course', 'course_code', 'material', 'material_title', 'source_text', 'source_preview',
            'question_type', 'difficulty', 'subject', 'count', 'quality', 'status', 'status_display', 'engine',
            'candidates', 'error', 'started_at', 'finished_at', 'saved_count', 'created_at',
        ]
        read_only_fields = ['status', 'engine', 'candidates', 'error', 'started_at', 'finished_at', 'saved_count']

    def get_source_preview(self, obj):
        text = ' '.join(obj.source_text.split())
        return text[:240] + ('…' if len(text) > 240 else '')

    def validate_count(self, value):
        if not 1 <= value <= self.MAX_COUNT:
            raise serializers.ValidationError(f'Generate between 1 and {self.MAX_COUNT} questions at a time.')
        return value

    def validate_course(self, course):
        if course and course.instructor_id != self.context['request'].user.id:
            raise serializers.ValidationError('You can only use your own courses.')
        return course

    def validate_material(self, material):
        if material and material.course.instructor_id != self.context['request'].user.id:
            raise serializers.ValidationError('You can only use material from your own courses.')
        return material

    def validate(self, attrs):
        text = (attrs.get('source_text') or '').strip()
        if not text and not attrs.get('material'):
            raise serializers.ValidationError({'source_text': 'Paste some text or choose a course material.'})
        if text and len(text.split()) < 15:
            raise serializers.ValidationError({'source_text': 'Provide at least a paragraph (15+ words) of text.'})
        attrs['source_text'] = text[:settings.AI_MAX_SOURCE_CHARS]
        if attrs.get('material') and not attrs.get('course'):
            attrs['course'] = attrs['material'].course
        return attrs


class PracticeSerializer(GenerationJobSerializer):
    """
    A student's self-test generated from their course material or notes.
    The questions are sent without their answers; `check` grades them.
    """
    questions = serializers.SerializerMethodField()

    MAX_COUNT = 15

    class Meta(GenerationJobSerializer.Meta):
        fields = [
            'id', 'course', 'course_code', 'material', 'material_title', 'source_text', 'source_preview',
            'question_type', 'count', 'quality', 'status', 'status_display', 'engine', 'questions', 'error',
            'practice_result', 'finished_at', 'created_at',
        ]
        read_only_fields = ['status', 'engine', 'error', 'finished_at', 'practice_result']

    def get_questions(self, obj):
        return [
            {'index': i, 'text': c['text'], 'question_type': c['question_type'],
             'options': [{'index': j, 'text': o['text']} for j, o in enumerate(c.get('options') or [])]}
            for i, c in enumerate(obj.candidates or [])
        ]

    def _enrolled(self, course):
        return Enrollment.objects.filter(course=course, student=self.context['request'].user).exists()

    def validate_course(self, course):
        if course and not self._enrolled(course):
            raise serializers.ValidationError('You are not enrolled in that course.')
        return course

    def validate_material(self, material):
        if material and not self._enrolled(material.course):
            raise serializers.ValidationError('You are not enrolled in that course.')
        return material


class CommitSerializer(serializers.Serializer):
    """The reviewed questions the instructor chose to keep."""
    questions = serializers.ListField(child=serializers.DictField(), allow_empty=False, max_length=50)
