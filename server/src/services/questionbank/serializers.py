from django.db import transaction
from rest_framework import serializers

from .models import Question, QuestionOption, QuestionType


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'is_correct', 'order']


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, required=False)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    type_display = serializers.CharField(source='get_question_type_display', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)

    course_code = serializers.CharField(source='course.code', read_only=True, default=None)
    locked = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id', 'course', 'course_code', 'text', 'question_type', 'type_display',
            'difficulty', 'difficulty_display', 'subject', 'marks',
            'correct_answer_text', 'required_keywords', 'options', 'is_ai_generated', 'is_active',
            'version', 'locked', 'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'version', 'is_ai_generated']

    def get_locked(self, obj):
        return obj.is_locked

    def validate_course(self, course):
        request = self.context.get('request')
        if course and request and course.instructor_id != request.user.id:
            raise serializers.ValidationError('You can only use your own courses.')
        return course

    def validate(self, attrs):
        qtype = attrs.get('question_type', getattr(self.instance, 'question_type', None))
        options = attrs.get('options')
        type_changed = self.instance is not None and qtype != self.instance.question_type

        if qtype == QuestionType.TRUE_FALSE and not options and (self.instance is None or type_changed):
            # Accept a plain 'true' / 'false' reference answer (e.g. CSV import)
            # and expand it into the two selectable options used for grading.
            answer = (attrs.get('correct_answer_text') or '').strip().lower()
            if answer not in ('true', 'false'):
                raise serializers.ValidationError(
                    {'correct_answer_text': "True/False questions need the answer 'true' or 'false'."}
                )
            options = attrs['options'] = [
                {'text': 'True', 'is_correct': answer == 'true'},
                {'text': 'False', 'is_correct': answer == 'false'},
            ]

        if qtype in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
            if options is None and (self.instance is None or type_changed):
                raise serializers.ValidationError({'options': 'Add the answer options.'})
            if options is not None:
                if len(options) < 2:
                    raise serializers.ValidationError({'options': 'Add at least two options.'})
                if sum(1 for o in options if o.get('is_correct')) != 1:
                    raise serializers.ValidationError({'options': 'Mark exactly one option as correct.'})

        if qtype == QuestionType.SHORT_ANSWER:
            answer = attrs.get('correct_answer_text', getattr(self.instance, 'correct_answer_text', ''))
            if not answer:
                raise serializers.ValidationError(
                    {'correct_answer_text': 'Short-answer questions need a reference answer.'}
                )
        elif attrs.get('required_keywords'):
            attrs['required_keywords'] = ''  # keywords only apply to short answers
        if attrs.get('required_keywords'):
            attrs['required_keywords'] = ', '.join(
                ' | '.join(a.strip() for a in part.split('|') if a.strip())
                for part in attrs['required_keywords'].split(',') if part.strip()
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        options = validated_data.pop('options', [])
        question = Question.objects.create(**validated_data)
        self._sync_options(question, options)
        return question

    @transaction.atomic
    def update(self, instance, validated_data):
        options = validated_data.pop('options', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.version += 1  # question versioning (scope doc, Module 2)
        instance.save()
        if options is not None:
            instance.options.all().delete()
            self._sync_options(instance, options)
        return instance

    @staticmethod
    def _sync_options(question, options):
        QuestionOption.objects.bulk_create([
            QuestionOption(
                question=question,
                text=o['text'],
                is_correct=o.get('is_correct', False),
                order=o.get('order', i),
            )
            for i, o in enumerate(options)
        ])
