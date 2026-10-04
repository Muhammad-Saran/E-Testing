from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification, NotificationType
from .serializers import AnnouncementSerializer, NotificationSerializer
from .services import dispatch_scheduled_throttled, notify


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """
    The signed-in user's notification log (scope doc, Module 9).
    The React app polls `unread_count` to keep the bell badge current.
    """
    serializer_class = NotificationSerializer
    filterset_fields = ['is_read', 'type']

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        # Polling doubles as the scheduler for reminders / results-ready alerts.
        dispatch_scheduled_throttled()
        qs = self.get_queryset().filter(is_read=False)
        latest = qs.first()
        return Response({
            'unread': qs.count(),
            'latest_id': latest.id if latest else None,
        })

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read', 'updated_at'])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'updated': updated})

    @action(detail=False, methods=['post'])
    def announce(self, request):
        """Instructor -> all students enrolled in one course (in-app + optional email)."""
        if not request.user.is_instructor:
            return Response({'detail': 'Only instructors may post announcements.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = AnnouncementSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        course = data['course']
        students = [e.student for e in course.enrollments.select_related('student')]
        sent = notify(
            students, NotificationType.ANNOUNCEMENT,
            f'{course.code}: {data["title"]}', data['message'],
            link='/student', email=data['email'],
        )
        return Response({'sent': len(sent)}, status=status.HTTP_201_CREATED)
