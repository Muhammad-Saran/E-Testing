from rest_framework import serializers

from .models import Course, CourseMaterial, Enrollment


class CourseSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.full_name', read_only=True)
    enrolled_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'code', 'title', 'description', 'instructor', 'instructor_name',
            'is_active', 'enrolled_count', 'created_at',
        ]
        read_only_fields = ['instructor']

    def get_enrolled_count(self, obj):
        return obj.enrollments.count()


class EnrollmentSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'course', 'course_code', 'course_title', 'student', 'created_at']
        read_only_fields = ['student']


MATERIAL_EXTENSIONS = ('.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.txt', '.zip')
MATERIAL_MAX_BYTES = 20 * 1024 * 1024


class CourseMaterialSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    file_name = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()

    class Meta:
        model = CourseMaterial
        fields = ['id', 'course', 'course_code', 'course_title', 'title', 'file',
                  'file_name', 'file_size', 'uploaded_by', 'created_at']
        read_only_fields = ['uploaded_by']

    def get_file_name(self, obj):
        return obj.file.name.rsplit('/', 1)[-1] if obj.file else ''

    def get_file_size(self, obj):
        try:
            return obj.file.size
        except (OSError, ValueError):
            return None

    def validate_course(self, course):
        request = self.context.get('request')
        if request and course.instructor_id != request.user.id:
            raise serializers.ValidationError('You can only add material to your own courses.')
        return course

    def validate_file(self, file):
        if not file.name.lower().endswith(MATERIAL_EXTENSIONS):
            raise serializers.ValidationError(
                'Unsupported file type. Allowed: ' + ', '.join(MATERIAL_EXTENSIONS) + '.')
        if file.size > MATERIAL_MAX_BYTES:
            raise serializers.ValidationError('File is too large (maximum 20 MB).')
        return file
