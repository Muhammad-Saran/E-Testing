"""
Notification dispatch (scope doc, Module 9).

`notify()` is the single entry point the other modules call. It writes the
in-app notification log and, optionally, sends the same message by email.
`dispatch_scheduled()` sends the time-based notifications (exam reminders and
results-ready alerts); it runs from the `send_notifications` management
command and is also triggered, throttled, by the frontend's polling.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mass_mail
from django.db import IntegrityError
from django.utils import timezone

from .models import Notification, NotificationType

logger = logging.getLogger('etesting.notifications')

DISPATCH_CACHE_KEY = 'notifications:last-dispatch'


def _as_list(users):
    if users is None:
        return []
    if hasattr(users, 'pk'):
        return [users]
    return list(users)


def notify(users, type, title, message='', link='', email=False, dedupe_key=''):
    """
    Create one notification per user. With `email=True` the message is also
    mailed (if NOTIFICATION_EMAILS is on). A non-empty `dedupe_key` is sent at
    most once per user. Returns the notifications that were created.
    """
    created = []
    for user in _as_list(users):
        if dedupe_key and Notification.objects.filter(user=user, dedupe_key=dedupe_key).exists():
            continue
        try:
            created.append(Notification.objects.create(
                user=user, type=type, title=title[:255], message=message, link=link, dedupe_key=dedupe_key,
            ))
        except IntegrityError:  # sent concurrently by another request
            continue

    if email and created and settings.NOTIFICATION_EMAILS:
        _send_emails(created)
    return created


def _send_emails(notifications):
    base = settings.FRONTEND_URL.rstrip('/')
    messages = []
    for n in notifications:
        if not n.user.email:
            continue
        body = f'Hello {n.user.full_name},\n\n{n.message or n.title}\n'
        if n.link:
            body += f'\nOpen e-Testing: {base}{n.link}\n'
        messages.append((f'e-Testing: {n.title}', body, settings.DEFAULT_FROM_EMAIL, [n.user.email]))
    try:
        send_mass_mail(messages, fail_silently=False)
    except Exception:  # a mail outage must never break the action that triggered it
        logger.exception('Could not send %d notification email(s)', len(messages))
        return
    Notification.objects.filter(pk__in=[n.pk for n in notifications]).update(emailed=True)


def _humanize(delta):
    minutes = max(1, round(delta.total_seconds() / 60))
    if minutes < 60:
        return f'{minutes} minute{"s" if minutes != 1 else ""}'
    hours = round(minutes / 60)
    if hours < 48:
        return f'{hours} hour{"s" if hours != 1 else ""}'
    return f'{round(hours / 24)} days'


def _send_reminders(now):
    from src.services.exams.models import Exam, ExamStatus

    intervals = sorted(settings.EXAM_REMINDER_MINUTES)
    if not intervals:
        return 0
    horizon = now + timedelta(minutes=max(intervals))
    sent = 0
    exams = Exam.objects.filter(
        status=ExamStatus.PUBLISHED, available_from__gt=now, available_from__lte=horizon,
    ).select_related('course')
    for exam in exams:
        due = [m for m in intervals if now >= exam.available_from - timedelta(minutes=m)]
        if not due:
            continue
        # Only the closest reminder: if the server was idle past the 24h mark,
        # students get one "starts in 50 minutes" message, not two.
        minutes = min(due)
        students = [e.student for e in exam.course.enrollments.select_related('student')]
        opens = timezone.localtime(exam.available_from).strftime('%d %b %Y, %I:%M %p')
        sent += len(notify(
            students, NotificationType.EXAM_REMINDER,
            f'Reminder: {exam.title} starts in {_humanize(exam.available_from - now)}',
            f'{exam.title} ({exam.course.code}) opens on {opens} and lasts {exam.duration_minutes} minutes '
            f'once you start it.',
            link='/exams', email=True, dedupe_key=f'exam:{exam.id}:reminder:{minutes}',
        ))
    return sent


def notify_results_ready(exam):
    """
    Tell the instructor that every attempt is graded, and the students who sat
    the exam that the answer key is now visible. Safe to call more than once.
    """
    from src.services.exams.services import class_average, percentage

    submitted = exam.attempts.filter(is_submitted=True).select_related('student')
    average = class_average(exam)
    avg_text = f'{percentage(average, exam.total_marks)}%' if average is not None else '—'
    notify(
        exam.created_by, NotificationType.EXAM_RESULTS_READY,
        f'Results ready: {exam.title}',
        f'{exam.title} ({exam.course.code}) has closed. {submitted.count()} submission(s) were graded; '
        f'class average {avg_text}.',
        link=f'/results?exam={exam.id}', dedupe_key=f'exam:{exam.id}:results_ready',
    )
    notify(
        [a.student for a in submitted], NotificationType.ANSWERS_RELEASED,
        f'Answer key released: {exam.title}',
        f'{exam.title} has closed. You can now see the correct answers in your result.',
        link=f'/results?exam={exam.id}', dedupe_key=f'exam:{exam.id}:answers',
    )


def _send_results_ready(now):
    from src.services.exams.models import Exam, ExamStatus
    from src.services.exams.services import answers_released, finalize_expired

    done = set(
        Notification.objects.filter(type=NotificationType.EXAM_RESULTS_READY)
        .values_list('dedupe_key', flat=True)
    )
    exams = (Exam.objects.exclude(status=ExamStatus.DRAFT)
             .filter(available_until__lt=now)
             .select_related('course', 'created_by'))
    count = 0
    for exam in exams:
        if f'exam:{exam.id}:results_ready' in done:
            continue
        finalize_expired(exam.attempts.all())
        if answers_released(exam):
            notify_results_ready(exam)
            count += 1
    return count


def dispatch_scheduled(now=None):
    """Send every time-based notification that is due. Idempotent."""
    now = now or timezone.now()
    return {'reminders': _send_reminders(now), 'results_ready': _send_results_ready(now)}


def dispatch_scheduled_throttled():
    """Run `dispatch_scheduled` at most once a minute (called from polling)."""
    if cache.add(DISPATCH_CACHE_KEY, True, timeout=60):
        try:
            dispatch_scheduled()
        except Exception:
            logger.exception('Scheduled notification dispatch failed')
