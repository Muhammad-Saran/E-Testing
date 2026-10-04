from django.conf import settings
from django.db import models

from src.core.models import TimeStampedModel
from src.services.questionbank.models import DifficultyLevel


class JobStatus(models.TextChoices):
    PENDING = 'pending', 'Queued'
    RUNNING = 'running', 'Generating'
    DONE = 'done', 'Ready for review'
    FAILED = 'failed', 'Failed'


class GenerationType(models.TextChoices):
    MCQ = 'mcq', 'Multiple Choice'
    TRUE_FALSE = 'true_false', 'True / False'
    SHORT_ANSWER = 'short_answer', 'Short Answer'
    MIXED = 'mixed', 'Mixed'


class JobPurpose(models.TextChoices):
    BANK = 'bank', 'Instructor question bank'
    PRACTICE = 'practice', 'Student practice test'


class Quality(models.TextChoices):
    FAST = 'fast', 'Fast (T5-small)'
    BETTER = 'better', 'Better (T5-base)'


DIFFICULTY_CHOICES = [('auto', 'Auto (Bloom classifier)')] + list(DifficultyLevel.choices)


class GenerationJob(TimeStampedModel):
    """
    One AI question-generation request (scope doc, Module 3). Generation runs
    in the background; the candidate questions are kept here as JSON until the
    instructor reviews them and commits the chosen ones to the question bank.
    """
    # An instructor (questions for the bank) or a student (a practice test).
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='generation_jobs')
    purpose = models.CharField(max_length=20, choices=JobPurpose.choices, default=JobPurpose.BANK)
    quality = models.CharField(max_length=20, choices=Quality.choices, default=Quality.FAST)
    course = models.ForeignKey('courses.Course', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='generation_jobs')
    material = models.ForeignKey('courses.CourseMaterial', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='generation_jobs')
    source_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=GenerationType.choices, default=GenerationType.MIXED)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='auto')
    subject = models.CharField(max_length=120, blank=True)
    count = models.PositiveSmallIntegerField(default=5)

    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.PENDING)
    # Which engine produced the candidates: "t5" or "rule".
    engine = models.CharField(max_length=20, blank=True)
    candidates = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    saved_count = models.PositiveIntegerField(default=0)
    # Practice tests: the student's last checked answers and score.
    practice_result = models.JSONField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        indexes = [models.Index(fields=['created_by', 'status'])]

    def __str__(self):
        return f'Job {self.pk} · {self.get_status_display()}'
