from rest_framework import serializers

from .models import Exam, ExamQuestion


class ExamSerializer(serializers.ModelSerializer):
    """Instructor-facing exam representation."""
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    total_marks = serializers.IntegerField(read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Exam
        fields = [
            'id', 'course', 'course_code', 'course_title', 'title', 'description',
            'available_from', 'available_until', 'duration_minutes', 'shuffle_questions',
            'status', 'status_display', 'total_marks', 'question_count', 'created_at',
        ]
        read_only_fields = ['status', 'created_by']

    def validate(self, attrs):
        start = attrs.get('available_from', getattr(self.instance, 'available_from', None))
        end = attrs.get('available_until', getattr(self.instance, 'available_until', None))
        if start and end and end <= start:
            raise serializers.ValidationError({'available_until': 'Must be after the start time.'})
        return attrs


class ExamQuestionSerializer(serializers.ModelSerializer):
    """Exam question with full question detail (instructor view — shows answers)."""
    text = serializers.CharField(source='question.text', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)
    type_display = serializers.CharField(source='question.get_question_type_display', read_only=True)
    difficulty = serializers.CharField(source='question.difficulty', read_only=True)
    options = serializers.SerializerMethodField()

    class Meta:
        model = ExamQuestion
        fields = ['id', 'question', 'order', 'marks', 'text', 'question_type',
                  'type_display', 'difficulty', 'options']

    def get_options(self, obj):
        return [
            {'id': o.id, 'text': o.text, 'is_correct': o.is_correct}
            for o in obj.question.options.all()
        ]


class StudentExamQuestionSerializer(serializers.ModelSerializer):
    """Exam question as shown to a student taking the exam — no correct answers."""
    text = serializers.CharField(source='question.text', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)
    options = serializers.SerializerMethodField()

    class Meta:
        model = ExamQuestion
        fields = ['id', 'order', 'marks', 'text', 'question_type', 'options']

    def get_options(self, obj):
        # Deliberately omit is_correct so answers aren't leaked to the client.
        return [{'id': o.id, 'text': o.text} for o in obj.question.options.all()]
