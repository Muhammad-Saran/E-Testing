"""Exam delivery + grading logic shared by the student and instructor views."""
import logging
import random
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Sum
from django.utils import timezone

from src.services.ai.engine import answer_similarity, keyword_groups, missing_keywords, normalize
from src.services.notifications.models import NotificationType
from src.services.notifications.services import notify
from src.services.questionbank.models import QuestionOption, QuestionType
from .models import Exam, ExamAnswer, ExamAttempt, ExamState, ExamStatus, SubmitReason

# Every grading operation is written to the audit log (scope doc, Module 6).
audit = logging.getLogger('etesting.audit')

# Allowance for network delay between the client's timer hitting zero and the
# submit request reaching the server.
SUBMIT_GRACE = timedelta(seconds=15)

# Methods whose score is a judgement call (as opposed to an answer key / exact match).
JUDGED_METHODS = ('sentence-t5', 'lexical', 'fuzzy')


# ---------------------------------------------------------------------------
# Which questions a student gets, and in what order
# ---------------------------------------------------------------------------
def assign_questions(attempt):
    """
    Pick this attempt's questions (a random subset when the exam uses a
    question pool) and their order. Seeded by the attempt, so it is
    reproducible, and stored on the attempt when it starts.
    """
    exam = attempt.exam
    ids = list(exam.exam_questions.values_list('id', flat=True))
    rng = random.Random(attempt.id)
    if exam.uses_pool:
        chosen = set(rng.sample(ids, exam.questions_per_student))
        ids = [i for i in ids if i in chosen]
    if exam.shuffle_questions:
        rng.shuffle(ids)
    return ids


def attempt_questions(attempt):
    """The exam questions this student received, in the order they see them."""
    eqs = list(attempt.exam.exam_questions.select_related('question').prefetch_related('question__options'))
    if attempt.question_order:
        by_id = {eq.id: eq for eq in eqs}
        return [by_id[i] for i in attempt.question_order if i in by_id]
    # Attempts started before question pools existed: every question, seeded shuffle.
    if attempt.exam.shuffle_questions:
        random.Random(attempt.id).shuffle(eqs)
    return eqs


# Kept for callers that only need the order.
ordered_exam_questions = attempt_questions


def shuffled_options(attempt, eq):
    """MCQ options in this student's order (true/false keeps its natural order)."""
    options = list(eq.question.options.all())
    if attempt.exam.shuffle_options and eq.question.question_type == QuestionType.MCQ:
        random.Random(f'{attempt.id}:{eq.id}').shuffle(options)
    return options


def save_answers(attempt, answers):
    """
    Store the student's in-progress answers (ungraded). Returns how many were
    saved. All answers go in one transaction with bulk writes, so an autosave
    takes the SQLite write lock once instead of once per question.
    """
    if not isinstance(answers, list):
        return 0
    exam_questions = {eq.id: eq for eq in attempt_questions(attempt)}
    wanted = {}
    for item in answers:
        if not isinstance(item, dict):
            continue
        try:
            eq = exam_questions.get(int(item.get('exam_question_id')))
        except (TypeError, ValueError):
            eq = None
        if eq:
            wanted[eq.id] = (eq, item)

    # Only accept options that really belong to their question.
    option_ids = [item.get('selected_option_id') for eq, item in wanted.values()
                  if eq.question.question_type != QuestionType.SHORT_ANSWER and str(item.get('selected_option_id') or '').isdigit()]
    options = {o.id: o for o in QuestionOption.objects.filter(id__in=option_ids)}

    with transaction.atomic():
        existing = {a.exam_question_id: a for a in attempt.answers.all()}
        to_create, to_update = [], []
        for eq_id, (eq, item) in wanted.items():
            option, answer_text = None, ''
            if eq.question.question_type == QuestionType.SHORT_ANSWER:
                answer_text = str(item.get('answer_text') or '').strip()[:5000]
            else:
                option = options.get(int(item['selected_option_id'])) if str(item.get('selected_option_id') or '').isdigit() else None
                if option and option.question_id != eq.question_id:
                    option = None
            answer = existing.get(eq_id)
            if answer is None:
                to_create.append(ExamAnswer(attempt=attempt, exam_question=eq, selected_option=option,
                                            answer_text=answer_text))
            elif answer.selected_option_id != (option.id if option else None) or answer.answer_text != answer_text:
                answer.selected_option, answer.answer_text = option, answer_text
                to_update.append(answer)
        ExamAnswer.objects.bulk_create(to_create)
        ExamAnswer.objects.bulk_update(to_update, ['selected_option', 'answer_text'])
    return len(wanted)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------
def grade_answer(question, answer, marks):
    """
    Grade one answer. Returns (is_correct, awarded_marks, similarity, method, needs_review).

    Objective questions are compared with the answer key. Short answers are
    scored by similarity to the reference answer (Sentence-T5 for descriptive
    answers, typo-tolerant matching for one-to-three-word facts): at or above
    SHORT_ANSWER_THRESHOLD earns full marks, at or above the partial threshold
    earns half marks (rounded down).

    If the question lists required keywords, an answer missing some of them
    can earn at most half marks, and one missing all of them earns none. This
    catches answers that sound right but state the wrong thing.

    Borderline scores, and answers the model liked but that miss keywords, are
    flagged for the instructor's review.
    """
    if answer is None:
        return False, 0, None, '', False
    if question.question_type in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
        correct = bool(answer.selected_option and answer.selected_option.is_correct)
        return correct, marks if correct else 0, None, 'key', False
    reference = (question.correct_answer_text or '').strip()
    if not reference or not normalize(answer.answer_text):
        return False, 0, None, '', False

    score, method = answer_similarity(reference, answer.answer_text)
    if score >= settings.SHORT_ANSWER_THRESHOLD:
        correct, awarded = True, marks
    elif score >= settings.SHORT_ANSWER_PARTIAL_THRESHOLD:
        correct, awarded = False, marks // 2
    else:
        correct, awarded = False, 0

    needs_review = (method in JUDGED_METHODS
                    and settings.SHORT_ANSWER_REVIEW_MIN <= score < settings.SHORT_ANSWER_REVIEW_MAX)

    if question.required_keywords:
        missing = missing_keywords(question.required_keywords, answer.answer_text)
        if missing:
            all_missing = len(missing) == len(keyword_groups(question.required_keywords))
            correct, awarded = False, 0 if all_missing else min(awarded, marks // 2)
            if score >= settings.SHORT_ANSWER_PARTIAL_THRESHOLD:
                needs_review = True
    return correct, awarded, score, method, needs_review


SUBMIT_MESSAGES = {
    SubmitReason.TIME: ' The exam was submitted automatically when the time ran out.',
    SubmitReason.VIOLATIONS: ' The exam was submitted automatically after repeated proctoring violations.',
    SubmitReason.CLOSED: ' The exam was submitted when your instructor closed it.',
}


def grade_attempt(attempt, auto=False, reason=''):
    """
    Grade the saved answers and lock the attempt. `auto` marks a submission
    made by the server; `reason` says why (time / violations / closed).
    Results are immutable, so an attempt that is already submitted is returned
    unchanged.
    """
    reason = reason or (SubmitReason.TIME if auto else SubmitReason.STUDENT)
    answers = {a.exam_question_id: a for a in attempt.answers.select_related('selected_option')}
    exam_questions = attempt_questions(attempt)
    # Model inference happens before the write transaction so the database is
    # not locked while Sentence-T5 runs.
    graded = {eq.id: grade_answer(eq.question, answers.get(eq.id), eq.marks) for eq in exam_questions}

    with transaction.atomic():
        if ExamAttempt.objects.filter(pk=attempt.pk, is_submitted=True).exists():
            attempt.refresh_from_db()
            return attempt  # graded concurrently by another request
        score = 0
        for eq in exam_questions:
            correct, awarded, similarity, method, needs_review = graded[eq.id]
            score += awarded
            fields = {'is_correct': correct, 'awarded_marks': awarded, 'similarity': similarity,
                      'grading_method': method, 'needs_review': needs_review}
            answer = answers.get(eq.id)
            if answer is None:
                ExamAnswer.objects.create(attempt=attempt, exam_question=eq, **fields)
            else:
                for field, value in fields.items():
                    setattr(answer, field, value)
                answer.save(update_fields=list(fields))

        now = timezone.now()
        attempt.score = score
        attempt.is_submitted = True
        attempt.auto_submitted = auto
        attempt.submit_reason = reason
        attempt.submitted_at = min(now, attempt.deadline) if reason == SubmitReason.TIME else now
        attempt.save()

    exam = attempt.exam
    total = exam.total_marks
    flagged = sum(1 for g in graded.values() if g[4])
    audit.info(
        'graded attempt=%s exam=%s student=%s score=%s/%s reason=%s methods=%s flagged=%s',
        attempt.id, exam.id, attempt.student.email, score, total, reason,
        ','.join(sorted({g[3] for g in graded.values() if g[3]})) or '-', flagged,
    )
    notify(
        attempt.student, NotificationType.RESULT_PUBLISHED,
        f'Result published: {exam.title}',
        f'You scored {score} / {total} ({percentage(score, total)}%) in {exam.title} ({exam.course.code}).'
        + SUBMIT_MESSAGES.get(reason, ''),
        link=f'/results?exam={exam.id}', email=True,
    )
    if flagged:
        notify(
            exam.created_by, NotificationType.REVIEW_NEEDED,
            f'Short answers to review: {exam.title}',
            f'Some short answers in {exam.title} ({exam.course.code}) scored close to the pass mark or miss '
            f'required keywords. Review them to confirm or adjust the marks.',
            link=f'/results?exam={exam.id}&tab=review', dedupe_key=f'exam:{exam.id}:review',
        )
    return attempt


def review_answer(answer, reviewer, awarded, note=''):
    """
    Instructor override of an automatically graded answer. Results are
    otherwise immutable; this is the one sanctioned change, and it records who
    changed what, when and why (on the answer and in the audit log).
    """
    attempt = answer.attempt
    marks = answer.exam_question.marks
    before = answer.awarded_marks
    with transaction.atomic():
        ExamAnswer.objects.filter(pk=answer.pk).update(
            awarded_marks=awarded, is_correct=awarded == marks, needs_review=False,
            reviewed_by=reviewer, reviewed_at=timezone.now(), review_note=note,
            original_marks=answer.original_marks if answer.original_marks is not None else before,
        )
        score = attempt.answers.aggregate(s=Sum('awarded_marks'))['s'] or 0
        # .update() deliberately bypasses ExamAttempt.save()'s immutability guard.
        ExamAttempt.objects.filter(pk=attempt.pk).update(score=score)
    audit.info('review answer=%s attempt=%s exam=%s by=%s marks=%s->%s note=%r',
               answer.pk, attempt.pk, attempt.exam_id, reviewer.email, before, awarded, note)
    if awarded != before:
        exam = attempt.exam
        total = exam.total_marks
        notify(
            attempt.student, NotificationType.RESULT_PUBLISHED,
            f'Mark reviewed: {exam.title}',
            f'Your instructor reviewed a short answer in {exam.title}: {before} -> {awarded} of {marks} marks. '
            f'Your score is now {score} / {total} ({percentage(score, total)}%).'
            + (f' Note: {note}' if note else ''),
            link=f'/results?exam={exam.id}', email=True,
        )
    answer.refresh_from_db()
    return answer, score


def finalize_expired(attempts):
    """
    Auto-submit any unsubmitted attempt whose time limit has passed. The
    countdown is enforced here, on the server, so closing the browser or
    tampering with the client timer cannot extend an exam.
    """
    cutoff = timezone.now() - SUBMIT_GRACE
    for attempt in attempts.filter(is_submitted=False).select_related('exam'):
        if attempt.deadline < cutoff:
            grade_attempt(attempt, auto=True, reason=SubmitReason.TIME)


def class_average(exam):
    avg = ExamAttempt.objects.filter(exam=exam, is_submitted=True).aggregate(a=Avg('score'))['a']
    return round(avg, 2) if avg is not None else None


def percentage(score, total):
    return round(score / total * 100, 1) if total else 0


def answers_released(exam):
    """
    Correct answers stay hidden until the exam has closed AND nobody is still
    writing it — a student who starts a minute before `available_until` keeps
    their full duration, and must not be able to see a classmate's answer key.
    """
    if exam.state != ExamState.CLOSED:
        return False
    cutoff = timezone.now() - SUBMIT_GRACE
    still_writing = [a for a in exam.attempts.filter(is_submitted=False) if a.deadline >= cutoff]
    return not still_writing


def build_result(attempt):
    """Full result payload for a submitted attempt, with question-level feedback."""
    exam = attempt.exam
    total = exam.total_marks
    answers = {a.exam_question_id: a for a in attempt.answers.select_related('selected_option')}
    reveal = answers_released(exam)
    questions = []
    for eq in attempt_questions(attempt):
        question = eq.question
        answer = answers.get(eq.id)
        missing = []
        if question.question_type == QuestionType.SHORT_ANSWER:
            your_answer = answer.answer_text if answer else ''
            correct_answer = question.correct_answer_text
            if question.required_keywords and your_answer:
                missing = missing_keywords(question.required_keywords, your_answer)
        else:
            your_answer = answer.selected_option.text if (answer and answer.selected_option) else ''
            correct_answer = next((o.text for o in question.options.all() if o.is_correct), '')
        questions.append({
            'exam_question_id': eq.id,
            'text': question.text,
            'question_type': question.question_type,
            'marks': eq.marks,
            'awarded_marks': answer.awarded_marks if answer else 0,
            'is_correct': bool(answer and answer.is_correct),
            'is_partial': bool(answer and not answer.is_correct and answer.awarded_marks > 0),
            'similarity': round(answer.similarity * 100) if (answer and answer.similarity is not None) else None,
            'grading_method': answer.grading_method if answer else '',
            'under_review': bool(answer and answer.needs_review),
            'reviewed': bool(answer and answer.reviewed_at),
            'review_note': answer.review_note if answer else '',
            'answered': bool(your_answer),
            'your_answer': your_answer,
            'correct_answer': correct_answer if reveal else None,
            'missing_keywords': missing if reveal else [],
        })

    average = class_average(exam)
    return {
        'exam_id': exam.id,
        'exam_title': exam.title,
        'course_code': exam.course.code,
        'score': attempt.score,
        'total_marks': total,
        'percentage': percentage(attempt.score, total),
        'correct_count': sum(1 for q in questions if q['is_correct']),
        'question_count': len(questions),
        'class_average': average,
        'class_average_percentage': percentage(average, total) if average is not None else None,
        'submitted_at': attempt.submitted_at,
        'auto_submitted': attempt.auto_submitted,
        'submit_reason': attempt.submit_reason,
        'answers_revealed': reveal,
        'questions': questions,
    }


def find_schedule_conflict(exam):
    """
    Another published exam whose availability window overlaps this one for the
    same cohort — i.e. the same course, or a course sharing enrolled students
    (scope doc, Module 4). Returns the clashing exam or None.
    """
    student_ids = exam.course.enrollments.values_list('student_id', flat=True)
    overlapping = (
        Exam.objects.filter(
            status=ExamStatus.PUBLISHED,
            available_from__lt=exam.available_until,
            available_until__gt=exam.available_from,
        )
        .exclude(pk=exam.pk)
        .select_related('course')
    )
    same_course = overlapping.filter(course=exam.course).first()
    if same_course:
        return same_course
    return overlapping.filter(course__enrollments__student_id__in=student_ids).first()


# ---------------------------------------------------------------------------
# Analytics helpers (scope doc, Module 8)
# ---------------------------------------------------------------------------
def discrimination_label(d):
    """Ebel's classic guidelines for the discrimination index."""
    if d is None:
        return 'Not enough data'
    if d >= 0.4:
        return 'Excellent'
    if d >= 0.3:
        return 'Good'
    if d >= 0.2:
        return 'Fair'
    if d >= 0:
        return 'Poor - revise'
    return 'Negative - check the key'


def item_analysis(exam, attempts):
    """
    Per-question statistics from submitted attempts:
      * difficulty index — share of the students who got the question right;
      * discrimination index — accuracy in the top 27 % minus the bottom 27 %
        of the class (Kelley's groups); needs at least 4 submissions;
      * distractor analysis — how often each MCQ / true-false option was chosen.
    """
    attempts = sorted(attempts, key=lambda a: a.score, reverse=True)
    group = round(len(attempts) * 0.27) if len(attempts) >= 4 else 0
    upper = {a.id for a in attempts[:group]} if group else set()
    lower = {a.id for a in attempts[-group:]} if group else set()

    rows = ExamAnswer.objects.filter(attempt__in=[a.id for a in attempts]).values(
        'exam_question_id', 'attempt_id', 'is_correct', 'selected_option_id', 'needs_review')
    by_question = {}
    for row in rows:
        by_question.setdefault(row['exam_question_id'], []).append(row)

    def accuracy(answers, ids):
        chosen = [r for r in answers if r['attempt_id'] in ids]
        return sum(1 for r in chosen if r['is_correct']) / len(chosen) if chosen else None

    result = []
    for number, eq in enumerate(exam.exam_questions.select_related('question').prefetch_related('question__options'),
                                start=1):
        answers = by_question.get(eq.id, [])
        correct = sum(1 for r in answers if r['is_correct'])
        p_upper, p_lower = accuracy(answers, upper), accuracy(answers, lower)
        disc = round(p_upper - p_lower, 2) if (p_upper is not None and p_lower is not None) else None
        options = []
        if eq.question.question_type != QuestionType.SHORT_ANSWER:
            counts = {}
            for r in answers:
                counts[r['selected_option_id']] = counts.get(r['selected_option_id'], 0) + 1
            options = [{'id': o.id, 'text': o.text, 'is_correct': o.is_correct, 'count': counts.get(o.id, 0)}
                       for o in eq.question.options.all()]
            options.append({'id': None, 'text': 'No answer', 'is_correct': False, 'count': counts.get(None, 0)})
        result.append({
            'exam_question_id': eq.id,
            'number': number,
            'text': eq.question.text,
            'question_type': eq.question.question_type,
            'marks': eq.marks,
            'attempted_by': len(answers),
            'correct_count': correct,
            # Difficulty index = share of students who got it right (higher = easier).
            'accuracy': round(correct / len(answers) * 100, 1) if answers else None,
            'discrimination': disc,
            'discrimination_label': discrimination_label(disc),
            'needs_review': sum(1 for r in answers if r['needs_review']),
            'options': options,
        })
    return result
