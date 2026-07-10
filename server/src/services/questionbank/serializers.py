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

    class Meta:
        model = Question
        fields = [
            'id', 'course', 'text', 'question_type', 'type_display',
            'difficulty', 'difficulty_display', 'subject', 'marks',
            'correct_answer_text', 'options', 'is_ai_generated', 'is_active',
            'version', 'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'version', 'is_ai_generated']

    def validate(self, attrs):
        qtype = attrs.get('question_type', getattr(self.instance, 'question_type', None))
        options = attrs.get('options')

        if qtype == QuestionType.MCQ and options is not None:
            if len(options) < 2:
                raise serializers.ValidationError({'options': 'MCQ needs at least two options.'})
            if not any(o.get('is_correct') for o in options):
                raise serializers.ValidationError({'options': 'Mark at least one option correct.'})

        if qtype == QuestionType.SHORT_ANSWER:
            answer = attrs.get('correct_answer_text', getattr(self.instance, 'correct_answer_text', ''))
            if not answer:
                raise serializers.ValidationError(
                    {'correct_answer_text': 'Short-answer questions need a reference answer.'}
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
