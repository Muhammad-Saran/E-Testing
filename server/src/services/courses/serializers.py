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


class CourseMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseMaterial
        fields = ['id', 'course', 'title', 'file', 'uploaded_by', 'created_at']
        read_only_fields = ['uploaded_by']
