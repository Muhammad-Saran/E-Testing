from django.conf import settings
from django.db import models
from django.utils import timezone

from src.core.models import TimeStampedModel


class ExamStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'
    CLOSED = 'closed', 'Closed'


class ExamState(models.TextChoices):
    """
    Lifecycle an exam moves through (scope doc, Module 4). Draft and Closed are
    set by the instructor; Scheduled -> Active -> Closed follow the clock, so
    the state is derived from `status` plus the availability window.
    """
    DRAFT = 'draft', 'Draft'
    SCHEDULED = 'scheduled', 'Scheduled'
    ACTIVE = 'active', 'Active'
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
    # Shuffle the order of MCQ options for every student.
    shuffle_options = models.BooleanField(default=True)
    # Question pool: when set, each student gets this many questions drawn at
    # random from the exam's questions (scope doc Module 4, "number of
    # questions to be drawn"). All pool questions must carry the same marks.
    questions_per_student = models.PositiveIntegerField(null=True, blank=True)
    # Exam security (Module 5).
    require_fullscreen = models.BooleanField(default=False)
    # Auto-submit once a student reaches this many violations (tab switches,
    # leaving fullscreen). Empty = only record them.
    max_violations = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ExamStatus.choices, default=ExamStatus.DRAFT)

    class Meta(TimeStampedModel.Meta):
        indexes = [models.Index(fields=['course', 'status'])]

    def __str__(self):
        return f'{self.title} ({self.course.code})'

    @property
    def pool_size(self):
        """Questions attached to the exam (the pool students draw from)."""
        return self.exam_questions.count()

    @property
    def uses_pool(self):
        return bool(self.questions_per_student) and self.questions_per_student < self.pool_size

    @property
    def question_count(self):
        """Questions each student answers."""
        pool = self.pool_size
        return min(self.questions_per_student, pool) if self.questions_per_student else pool

    @property
    def total_marks(self):
        """Marks available to each student."""
        if self.uses_pool:
            marks = list(self.exam_questions.values_list('marks', flat=True))
            # Pool questions carry equal marks (enforced on publish); while a
            # draft is being composed, show the average as a guide.
            return round(sum(marks) / len(marks) * self.questions_per_student)
        return self.exam_questions.aggregate(t=models.Sum('marks'))['t'] or 0

    @property
    def pool_marks_uniform(self):
        return self.exam_questions.values('marks').distinct().count() <= 1

    @property
    def is_published(self):
        return self.status == ExamStatus.PUBLISHED

    def state_at(self, now=None):
        now = now or timezone.now()
        if self.status == ExamStatus.DRAFT:
            return ExamState.DRAFT
        if self.status == ExamStatus.CLOSED or now > self.available_until:
            return ExamState.CLOSED
        if now < self.available_from:
            return ExamState.SCHEDULED
        return ExamState.ACTIVE

    @property
    def state(self):
        return self.state_at()

    def is_open(self, now=None):
        """True when a student may start the exam right now."""
        return self.state_at(now) == ExamState.ACTIVE


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


class SubmitReason(models.TextChoices):
    STUDENT = 'student', 'Submitted by the student'
    TIME = 'time', 'Time ran out'
    VIOLATIONS = 'violations', 'Too many proctoring violations'
    CLOSED = 'closed', 'Exam closed by the instructor'


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
    # True when the server submitted the attempt (time ran out, too many
    # violations, or the instructor closed the exam) — see submit_reason.
    auto_submitted = models.BooleanField(default=False)
    submit_reason = models.CharField(max_length=20, choices=SubmitReason.choices, blank=True)
    score = models.PositiveIntegerField(default=0)
    # The exam-question ids this student received, in the order shown.
    question_order = models.JSONField(default=list, blank=True)
    # One active browser session per attempt: a new start rotates the key and
    # the old tab/device can no longer save or submit.
    session_key = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

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

    def save(self, *args, **kwargs):
        # Results are immutable once computed (scope doc, Module 6).
        if self.pk and ExamAttempt.objects.filter(pk=self.pk, is_submitted=True).exists():
            raise ValueError('A submitted exam attempt cannot be modified.')
        super().save(*args, **kwargs)


class ProctorEventType(models.TextChoices):
    TAB_SWITCH = 'tab_switch', 'Left the exam tab'
    WINDOW_BLUR = 'window_blur', 'Exam window lost focus'
    FULLSCREEN_EXIT = 'fullscreen_exit', 'Left fullscreen'
    COPY_PASTE = 'copy_paste', 'Tried to copy or paste'
    NEW_SESSION = 'new_session', 'Exam opened in another tab or device'


# Events that count towards Exam.max_violations.
VIOLATION_TYPES = ('tab_switch', 'window_blur', 'fullscreen_exit')


class ProctorEvent(models.Model):
    """An anti-cheating signal recorded while a student sits an exam (Module 5)."""
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='proctor_events')
    event_type = models.CharField(max_length=20, choices=ProctorEventType.choices)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['occurred_at']

    def __str__(self):
        return f'{self.attempt} · {self.event_type}'


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
    # Short answers: similarity to the reference answer (0..1) and how it was
    # measured — exact / fuzzy / sentence-t5 / lexical (scope doc, Module 6).
    similarity = models.FloatField(null=True, blank=True)
    grading_method = models.CharField(max_length=20, blank=True)
    # Borderline short answers are flagged for the instructor, who may confirm
    # or change the marks. Every change is recorded here and in the audit log.
    needs_review = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    original_marks = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('attempt', 'exam_question')

    def __str__(self):
        return f'{self.attempt} · answer'
