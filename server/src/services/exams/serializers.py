from rest_framework import serializers

from .models import Exam, ExamQuestion
from .services import shuffled_options


class ExamSerializer(serializers.ModelSerializer):
    """Instructor-facing exam representation."""
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    total_marks = serializers.IntegerField(read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    pool_size = serializers.IntegerField(read_only=True)
    uses_pool = serializers.BooleanField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    state = serializers.CharField(read_only=True)
    submission_count = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            'id', 'course', 'course_code', 'course_title', 'title', 'description',
            'available_from', 'available_until', 'duration_minutes', 'shuffle_questions',
            'shuffle_options', 'questions_per_student', 'require_fullscreen', 'max_violations',
            'status', 'status_display', 'state', 'total_marks', 'question_count', 'pool_size', 'uses_pool',
            'submission_count', 'created_at',
        ]
        read_only_fields = ['status', 'created_by']

    def get_submission_count(self, obj):
        return obj.attempts.filter(is_submitted=True).count()

    def validate_course(self, course):
        request = self.context.get('request')
        if request and course.instructor_id != request.user.id:
            raise serializers.ValidationError('You can only create exams for your own courses.')
        return course

    def validate_duration_minutes(self, value):
        if value < 1:
            raise serializers.ValidationError('Duration must be at least 1 minute.')
        return value

    def validate_questions_per_student(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError('Each student needs at least one question.')
        return value

    def validate_max_violations(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError('Use at least 1, or leave empty to only record violations.')
        return value

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
        fields = ['id', 'marks', 'text', 'question_type', 'options']

    def get_options(self, obj):
        # Deliberately omit is_correct so answers aren't leaked to the client,
        # and present MCQ options in this student's shuffled order.
        attempt = self.context.get('attempt')
        options = shuffled_options(attempt, obj) if attempt else obj.question.options.all()
        return [{'id': o.id, 'text': o.text} for o in options]
