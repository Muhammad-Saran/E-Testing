from django.conf import settings
from django.db import models

from src.core.models import TimeStampedModel


class NotificationType(models.TextChoices):
    # Students
    EXAM_PUBLISHED = 'exam_published', 'Exam scheduled'
    EXAM_REMINDER = 'exam_reminder', 'Exam reminder'
    RESULT_PUBLISHED = 'result_published', 'Result published'
    ANSWERS_RELEASED = 'answers_released', 'Answer key released'
    ANNOUNCEMENT = 'announcement', 'Instructor announcement'
    # Instructors
    EXAM_RESULTS_READY = 'exam_results_ready', 'Exam results computed'
    REVIEW_NEEDED = 'review_needed', 'Answers to review'
    IMPORT_COMPLETE = 'import_complete', 'Question import finished'
    AI_GENERATION_COMPLETE = 'ai_generation_complete', 'AI question generation finished'
    # Everyone
    ACCOUNT_ACTIVITY = 'account_activity', 'Account activity'


class Notification(TimeStampedModel):
    """
    One message to one user (scope doc, Module 9). The table doubles as the
    persistent notification log shown in the notifications panel. `dedupe_key`
    makes scheduled notifications (reminders, results-ready) idempotent: the
    same key is never sent twice to the same user.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=30, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    # In-app route the notification points at, e.g. "/exams" or "/results?exam=3".
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    emailed = models.BooleanField(default=False)
    dedupe_key = models.CharField(max_length=120, blank=True)

    class Meta(TimeStampedModel.Meta):
        indexes = [models.Index(fields=['user', 'is_read'])]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'dedupe_key'], condition=~models.Q(dedupe_key=''),
                name='unique_notification_dedupe_key',
            ),
        ]

    def __str__(self):
        return f'{self.user} · {self.title}'
