from django.conf import settings
from django.db import models
from django.utils import timezone

from src.core.models import TimeStampedModel


class ExamStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'
    CLOSED = 'closed', 'Closed'


class Exam(TimeStampedModel):
    """
    An examination on a course (scope doc, Module 4). It draws questions from
    the instructor's question bank, is available to students only within
    [available_from, available_until], and must be completed within
    `duration_minutes` once a student starts it.
    """
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='exams')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='exams_created',
        limit_choices_to={'role': 'instructor'},
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    available_from = models.DateTimeField(help_text='When students can begin taking the exam.')
    available_until = models.DateTimeField(help_text='After this, the exam can no longer be started.')
    duration_minutes = models.PositiveIntegerField(default=20, help_text='Time limit once a student starts.')

    shuffle_questions = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=ExamStatus.choices, default=ExamStatus.DRAFT)

    class Meta(TimeStampedModel.Meta):
        indexes = [models.Index(fields=['course', 'status'])]

    def __str__(self):
        return f'{self.title} ({self.course.code})'

    @property
    def total_marks(self):
        return self.exam_questions.aggregate(t=models.Sum('marks'))['t'] or 0

    @property
    def question_count(self):
        return self.exam_questions.count()

    @property
    def is_published(self):
        return self.status == ExamStatus.PUBLISHED

    def is_open(self, now=None):
        """True when a student may start the exam right now."""
        now = now or timezone.now()
        return self.is_published and self.available_from <= now <= self.available_until


class ExamQuestion(models.Model):
    """A question placed into an exam (junction, scope doc Module 4)."""
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='exam_questions')
    question = models.ForeignKey('questionbank.Question', on_delete=models.CASCADE, related_name='exam_links')
    order = models.PositiveSmallIntegerField(default=0)
    marks = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('exam', 'question')

    def __str__(self):
        return f'{self.exam.title} · Q{self.order}'


class ExamAttempt(TimeStampedModel):
    """One student's sitting of an exam (scope doc, Modules 5 & 6)."""
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='exam_attempts',
        limit_choices_to={'role': 'student'},
    )
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    is_submitted = models.BooleanField(default=False)
    score = models.PositiveIntegerField(default=0)

    class Meta(TimeStampedModel.Meta):
        unique_together = ('exam', 'student')

    def __str__(self):
        return f'{self.student} · {self.exam.title}'

    @property
    def deadline(self):
        return self.started_at + timezone.timedelta(minutes=self.exam.duration_minutes)

    @property
    def is_expired(self):
        return timezone.now() > self.deadline


class ExamAnswer(models.Model):
    """A student's answer to one exam question, with its grading result."""
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='answers')
    exam_question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name='answers')
    selected_option = models.ForeignKey(
        'questionbank.QuestionOption', on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    answer_text = models.TextField(blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    awarded_marks = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('attempt', 'exam_question')

    def __str__(self):
        return f'{self.attempt} · answer'
