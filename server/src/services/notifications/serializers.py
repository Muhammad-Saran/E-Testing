from rest_framework import serializers

from src.services.courses.models import Course
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'type', 'type_display', 'title', 'message', 'link', 'is_read', 'emailed', 'created_at']
        read_only_fields = fields


class AnnouncementSerializer(serializers.Serializer):
    """An instructor's message to every student enrolled in one of their courses."""
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    title = serializers.CharField(max_length=200)
    message = serializers.CharField(max_length=5000)
    email = serializers.BooleanField(default=True)

    def validate_course(self, course):
        if course.instructor_id != self.context['request'].user.id:
            raise serializers.ValidationError('You can only post announcements to your own courses.')
        return course
