"""Background execution of AI question-generation jobs (scope doc, Module 3)."""
import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from src.services.notifications.models import NotificationType
from src.services.notifications.services import notify
from src.services.questionbank.models import Question
from .engine import model_for, similar_questions
from .generation import generate_questions
from .models import GenerationJob, JobPurpose, JobStatus

logger = logging.getLogger('etesting.ai')

# A job still "running" after this long was interrupted (e.g. server restart).
STALE_AFTER = timedelta(minutes=15)


def mark_duplicates(job):
    """Flag candidates that repeat a question already in the instructor's bank."""
    bank = list(Question.objects.filter(created_by=job.created_by))
    if not bank:
        return
    for candidate in job.candidates:
        match = similar_questions(candidate['text'], bank, settings.DUPLICATE_THRESHOLD, limit=1)
        if match:
            question, score = match[0]
            candidate['duplicate_of'] = {'id': question.id, 'text': question.text, 'score': round(score * 100)}


def run_job(job_id):
    """Generate the candidates for one job. Never raises — failures are stored on the job."""
    job = GenerationJob.objects.select_related('created_by').get(pk=job_id)
    job.status = JobStatus.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=['status', 'started_at', 'updated_at'])
    try:
        candidates, engine_name = generate_questions(
            job.source_text, job.question_type, job.count, job.difficulty, job.subject, seed=job.id,
            model_name=model_for(job.quality),
        )
        job.candidates = candidates
        job.engine = engine_name
        job.status = JobStatus.DONE
        if not candidates:
            job.error = ('No questions could be generated. Use longer, complete sentences '
                         '(at least a paragraph of factual text).')
        elif job.purpose == JobPurpose.BANK:
            mark_duplicates(job)
    except Exception as exc:
        logger.exception('AI generation job %s failed', job_id)
        job.status = JobStatus.FAILED
        job.error = f'Generation failed: {exc}'
    job.finished_at = timezone.now()
    job.save(update_fields=['candidates', 'engine', 'status', 'error', 'finished_at', 'updated_at'])

    practice = job.purpose == JobPurpose.PRACTICE
    if job.status == JobStatus.DONE and job.candidates:
        title, message = ((f'Your practice test is ready ({len(job.candidates)} questions)',
                           'Open it to start practising. It does not count towards your results.')
                          if practice else
                          (f'{len(job.candidates)} AI questions ready for review',
                           'Your generated questions are ready. Review, edit and save the ones you want.'))
    elif job.status == JobStatus.DONE:
        title, message = 'AI generation found no questions', job.error
    else:
        title, message = 'AI question generation failed', job.error
    link = f'/practice?session={job.id}' if practice else f'/ai-generate?job={job.id}'
    notify(job.created_by, NotificationType.AI_GENERATION_COMPLETE, title, message, link=link)
    return job


def _run_in_thread(job_id):
    close_old_connections()
    try:
        run_job(job_id)
    finally:
        close_old_connections()


def start_job(job):
    """Queue the job. Inference is slow, so by default it runs off the request thread."""
    if settings.AI_ASYNC:
        thread = threading.Thread(target=_run_in_thread, args=(job.id,), daemon=True, name=f'ai-job-{job.id}')
        transaction.on_commit(thread.start)
    else:
        run_job(job.id)


def expire_stale(queryset):
    cutoff = timezone.now() - STALE_AFTER
    queryset.filter(status__in=[JobStatus.PENDING, JobStatus.RUNNING], created_at__lt=cutoff).update(
        status=JobStatus.FAILED, error='Generation was interrupted (the server restarted). Please try again.',
        finished_at=timezone.now(),
    )
