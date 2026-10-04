import csv
import random
import secrets

from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from src.core.permissions import IsInstructor, IsStudent
from src.services.courses.models import Enrollment
from src.services.notifications.models import NotificationType
from src.services.notifications.services import notify, notify_results_ready
from src.services.questionbank.models import Question, QuestionType
from src.services.questionbank.serializers import QuestionSerializer
from src.services.questionbank.models import QuestionType as QType
from .models import (
    VIOLATION_TYPES,
    Exam,
    ExamAnswer,
    ExamAttempt,
    ExamQuestion,
    ExamStatus,
    ProctorEvent,
    ProctorEventType,
    SubmitReason,
)
from .serializers import ExamQuestionSerializer, ExamSerializer, StudentExamQuestionSerializer
from .services import (
    SUBMIT_GRACE,
    assign_questions,
    attempt_questions,
    build_result,
    class_average,
    finalize_expired,
    find_schedule_conflict,
    grade_attempt,
    item_analysis,
    percentage,
    review_answer,
    save_answers,
)

SESSION_HEADER = 'HTTP_X_EXAM_SESSION'


def _client_ip(request):
    return ((request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR') or None)


def _conflict_response(clash):
    return Response(
        {'detail': (
            f'Schedule conflict: "{clash.title}" ({clash.course.code}) is already published for '
            f'these students in an overlapping time window. Change the dates or unpublish that exam.'
        )},
        status=status.HTTP_409_CONFLICT,
    )


# ===========================================================================
# INSTRUCTOR — create, configure, compose, publish (scope doc Module 4)
#              + results, analytics and export (Module 8)
# ===========================================================================
class ExamViewSet(viewsets.ModelViewSet):
    serializer_class = ExamSerializer
    permission_classes = [IsInstructor]
    lookup_value_regex = r'\d+'
    filterset_fields = ['course', 'status']

    def get_queryset(self):
        return Exam.objects.filter(created_by=self.request.user).select_related('course')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def update(self, request, *args, **kwargs):
        exam = self.get_object()
        if exam.attempts.exists():
            return Response({'detail': 'Students have already started this exam, so it can no longer be edited.'},
                            status=status.HTTP_409_CONFLICT)
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(exam, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        if exam.is_published:
            # Re-check the new window against the rest of the timetable.
            for field in ('available_from', 'available_until', 'course'):
                setattr(exam, field, serializer.validated_data.get(field, getattr(exam, field)))
            clash = find_schedule_conflict(exam)
            if clash:
                return _conflict_response(clash)
        serializer.save()
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        exam = self.get_object()
        if exam.attempts.exists():
            return Response({'detail': 'This exam has student attempts and cannot be deleted. Close it instead.'},
                            status=status.HTTP_409_CONFLICT)
        exam.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- Composition -------------------------------------------------------

    def _editable_or_response(self, exam):
        """Questions may only change while the exam is a draft."""
        if exam.status != ExamStatus.DRAFT:
            return Response({'detail': 'Unpublish the exam before changing its questions.'},
                            status=status.HTTP_409_CONFLICT)
        return None

    def _totals(self, exam):
        return {'question_count': exam.question_count, 'total_marks': exam.total_marks,
                'pool_size': exam.pool_size}

    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        exam = self.get_object()
        qs = exam.exam_questions.select_related('question').prefetch_related('question__options')
        return Response(ExamQuestionSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def bank_summary(self, request):
        """How many bank questions the instructor has per type (to compose from)."""
        qs = Question.objects.filter(created_by=request.user, is_active=True)
        return Response({t.value: qs.filter(question_type=t.value).count() for t in QuestionType})

    @action(detail=True, methods=['post'])
    def compose(self, request, pk=None):
        """
        Add N questions of a type (optionally a difficulty) drawn at random from
        the instructor's bank: body {question_type, difficulty?, count}.
        """
        exam = self.get_object()
        blocked = self._editable_or_response(exam)
        if blocked:
            return blocked
        qtype = request.data.get('question_type')
        difficulty = request.data.get('difficulty')
        try:
            count = int(request.data.get('count', 0))
        except (TypeError, ValueError):
            count = 0
        if qtype not in QuestionType.values:
            return Response({'detail': 'Invalid question_type.'}, status=status.HTTP_400_BAD_REQUEST)
        if count < 1:
            return Response({'detail': 'Count must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)

        pool = Question.objects.filter(created_by=request.user, is_active=True, question_type=qtype)
        if difficulty:
            pool = pool.filter(difficulty=difficulty)
        already = set(exam.exam_questions.values_list('question_id', flat=True))
        candidates = [q for q in pool if q.id not in already]
        random.shuffle(candidates)
        chosen = candidates[:count]

        order = exam.exam_questions.count()
        for i, q in enumerate(chosen):
            ExamQuestion.objects.create(exam=exam, question=q, order=order + i, marks=q.marks)

        return Response({
            'added': len(chosen),
            'requested': count,
            'short_by': max(0, count - len(chosen)),
            **self._totals(exam),
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def add_from_bank(self, request, pk=None):
        """Attach specific bank questions to the exam: body {question_ids: [..]}."""
        exam = self.get_object()
        blocked = self._editable_or_response(exam)
        if blocked:
            return blocked
        ids = request.data.get('question_ids')
        if not isinstance(ids, list) or not ids:
            return Response({'detail': 'Select at least one question.'}, status=status.HTTP_400_BAD_REQUEST)

        already = set(exam.exam_questions.values_list('question_id', flat=True))
        chosen = Question.objects.filter(created_by=request.user, is_active=True, id__in=ids).exclude(id__in=already)
        order = exam.exam_questions.count()
        added = 0
        for q in chosen:
            ExamQuestion.objects.create(exam=exam, question=q, order=order + added, marks=q.marks)
            added += 1
        return Response({'added': added, **self._totals(exam)}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def add_question(self, request, pk=None):
        """
        Create a brand-new question directly on this exam (scope doc Module 2/4).
        Accepts the full question payload (text, type, difficulty, marks, options,
        correct_answer_text); the question is saved to the bank and attached.
        """
        exam = self.get_object()
        blocked = self._editable_or_response(exam)
        if blocked:
            return blocked
        serializer = QuestionSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        question = serializer.save(created_by=request.user, course=exam.course)
        eq = ExamQuestion.objects.create(
            exam=exam, question=question, order=exam.exam_questions.count(), marks=question.marks,
        )
        return Response(ExamQuestionSerializer(eq).data | self._totals(exam), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def remove_question(self, request, pk=None):
        """Detach a question from the exam. The question itself stays in the bank."""
        exam = self.get_object()
        blocked = self._editable_or_response(exam)
        if blocked:
            return blocked
        eq = exam.exam_questions.filter(id=request.data.get('exam_question_id')).first()
        if not eq:
            return Response({'detail': 'Question not in this exam.'}, status=status.HTTP_404_NOT_FOUND)
        eq.delete()
        return Response(self._totals(exam))

    # -- Lifecycle: Draft -> Scheduled -> Active -> Closed ------------------

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        exam = self.get_object()
        if exam.status == ExamStatus.CLOSED:
            return Response({'detail': 'A closed exam cannot be published again.'},
                            status=status.HTTP_409_CONFLICT)
        if exam.question_count == 0:
            return Response({'detail': 'Add at least one question before publishing.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if exam.questions_per_student:
            if exam.questions_per_student > exam.pool_size:
                return Response({'detail': f'Each student should get {exam.questions_per_student} questions, but the '
                                           f'pool only has {exam.pool_size}. Add questions or lower the number.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if exam.uses_pool and not exam.pool_marks_uniform:
                return Response({'detail': 'In a question pool every question must carry the same marks, so that '
                                           'every student sits an exam of equal weight.'},
                                status=status.HTTP_400_BAD_REQUEST)
        if exam.available_until <= timezone.now():
            return Response({'detail': 'The availability window has already passed. Update the dates first.'},
                            status=status.HTTP_400_BAD_REQUEST)
        clash = find_schedule_conflict(exam)
        if clash:
            return _conflict_response(clash)
        exam.status = ExamStatus.PUBLISHED
        exam.save(update_fields=['status', 'updated_at'])
        # Tell the cohort (in-app + email, scope doc Modules 4 & 9).
        opens = timezone.localtime(exam.available_from).strftime('%d %b %Y, %I:%M %p')
        closes = timezone.localtime(exam.available_until).strftime('%d %b %Y, %I:%M %p')
        notify(
            [e.student for e in exam.course.enrollments.select_related('student')],
            NotificationType.EXAM_PUBLISHED,
            f'New exam scheduled: {exam.title}',
            f'{exam.title} ({exam.course.code}) is available from {opens} until {closes}. '
            f'It has {exam.question_count} question(s), {exam.total_marks} mark(s), and a time limit of '
            f'{exam.duration_minutes} minutes once you start.',
            link='/exams', email=True,
        )
        return Response(self.get_serializer(exam).data)

    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        exam = self.get_object()
        if exam.status != ExamStatus.PUBLISHED:
            return Response({'detail': 'Only a published exam can be moved back to draft.'},
                            status=status.HTTP_409_CONFLICT)
        if exam.attempts.exists():
            return Response({'detail': 'Students have already started this exam. Close it instead.'},
                            status=status.HTTP_409_CONFLICT)
        exam.status = ExamStatus.DRAFT
        exam.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(exam).data)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """End the exam now: no new starts, and every open attempt is submitted."""
        exam = self.get_object()
        if exam.status != ExamStatus.PUBLISHED:
            return Response({'detail': 'Only a published exam can be closed.'}, status=status.HTTP_409_CONFLICT)
        for attempt in exam.attempts.filter(is_submitted=False):
            grade_attempt(attempt, auto=True, reason=SubmitReason.CLOSED)
        exam.status = ExamStatus.CLOSED
        exam.save(update_fields=['status', 'updated_at'])
        notify_results_ready(exam)
        return Response(self.get_serializer(exam).data)

    # -- Results & analytics (scope doc Module 8) ---------------------------

    def _submitted_attempts(self, exam):
        finalize_expired(exam.attempts.all())
        return (
            exam.attempts.filter(is_submitted=True)
            .select_related('student')
            .annotate(violations=Count('proctor_events', filter=Q(proctor_events__event_type__in=VIOLATION_TYPES)))
            .order_by('-score', 'submitted_at')
        )

    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Score distribution, per-question difficulty index and the result sheet."""
        exam = self.get_object()
        attempts = list(self._submitted_attempts(exam))
        total = exam.total_marks
        scores = [a.score for a in attempts]

        # Histogram over ten percentage bands: 0-9, 10-19, … 90-100.
        buckets = [0] * 10
        for score in scores:
            buckets[min(9, int(percentage(score, total) // 10))] += 1

        questions = item_analysis(exam, attempts)

        return Response({
            'exam': self.get_serializer(exam).data,
            'summary': {
                'enrolled': exam.course.enrollments.count(),
                'submitted': len(attempts),
                'in_progress': exam.attempts.filter(is_submitted=False).count(),
                'median_percentage': _median([percentage(s, total) for s in scores]),
                'pass_rate': round(sum(1 for s in scores if percentage(s, total) >= 50) / len(scores) * 100, 1)
                if scores else None,
                'average': class_average(exam),
                'average_percentage': percentage(sum(scores) / len(scores), total) if scores else None,
                'highest': max(scores) if scores else None,
                'lowest': min(scores) if scores else None,
                'total_marks': total,
            },
            'distribution': {
                'labels': [f'{i * 10}-{i * 10 + 9}%' if i < 9 else '90-100%' for i in range(10)],
                'counts': buckets,
            },
            'questions': questions,
            'results': [
                {
                    'attempt_id': a.id,
                    'student_id': a.student_id,
                    'student_name': a.student.full_name,
                    'email': a.student.email,
                    'registration_number': a.student.registration_number,
                    'score': a.score,
                    'percentage': percentage(a.score, total),
                    'started_at': a.started_at,
                    'submitted_at': a.submitted_at,
                    'auto_submitted': a.auto_submitted,
                    'submit_reason': a.submit_reason,
                    'tab_switches': a.violations,
                }
                for a in attempts
            ],
            'pending_reviews': ExamAnswer.objects.filter(attempt__exam=exam, attempt__is_submitted=True,
                                                         needs_review=True).count(),
        })

    @action(detail=False, methods=['get'])
    def student_timeline(self, request):
        """
        One student's performance across this instructor's exams, oldest first
        (scope doc Module 8 — individual student performance timeline).
        Query: ?student=<id>  [&course=<id>]
        """
        student_id = request.query_params.get('student')
        if not str(student_id or '').isdigit():
            return Response({'detail': 'Pass ?student=<id>.'}, status=status.HTTP_400_BAD_REQUEST)
        enrollments = Enrollment.objects.filter(course__instructor=request.user, student_id=student_id)
        if not enrollments.exists():
            return Response({'detail': 'That student is not enrolled in any of your courses.'},
                            status=status.HTTP_404_NOT_FOUND)
        student = enrollments.select_related('student').first().student
        attempts = ExamAttempt.objects.filter(exam__created_by=request.user, student_id=student_id)
        finalize_expired(attempts)
        attempts = attempts.filter(is_submitted=True).select_related('exam__course').order_by('submitted_at')
        course = request.query_params.get('course')
        if str(course or '').isdigit():
            attempts = attempts.filter(exam__course_id=course)

        points = []
        for a in attempts:
            total = a.exam.total_marks
            average = class_average(a.exam)
            points.append({
                'exam_id': a.exam_id,
                'exam_title': a.exam.title,
                'course_code': a.exam.course.code,
                'submitted_at': a.submitted_at,
                'score': a.score,
                'total_marks': total,
                'percentage': percentage(a.score, total),
                'class_average_percentage': percentage(average, total) if average is not None else None,
                'auto_submitted': a.auto_submitted,
                'tab_switches': a.proctor_events.filter(event_type__in=VIOLATION_TYPES).count(),
            })
        pcts = [p['percentage'] for p in points]
        return Response({
            'student': {'id': student.id, 'full_name': student.full_name, 'email': student.email,
                        'registration_number': student.registration_number},
            'courses': [{'id': e.course_id, 'code': e.course.code} for e in enrollments.select_related('course')],
            'summary': {
                'exams_taken': len(points),
                'average_percentage': round(sum(pcts) / len(pcts), 1) if pcts else None,
                'best_percentage': max(pcts) if pcts else None,
                'trend': round(pcts[-1] - pcts[0], 1) if len(pcts) > 1 else None,
            },
            'timeline': points,
        })

    @action(detail=False, methods=['get'])
    def students(self, request):
        """Students enrolled in the instructor's courses — to pick a timeline from."""
        rows = (Enrollment.objects.filter(course__instructor=request.user)
                .select_related('student').order_by('student__first_name', 'student__email'))
        seen, data = set(), []
        for e in rows:
            if e.student_id in seen:
                continue
            seen.add(e.student_id)
            data.append({'id': e.student_id, 'full_name': e.student.full_name, 'email': e.student.email,
                         'registration_number': e.student.registration_number})
        return Response(data)

    # -- Short-answer review (Module 6 safeguard) -----------------------------

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """
        Graded short answers for the instructor to check. By default only the
        flagged ones; ?all=1 lists every short answer.
        """
        exam = self.get_object()
        finalize_expired(exam.attempts.all())
        qs = (ExamAnswer.objects.filter(attempt__exam=exam, attempt__is_submitted=True,
                                        exam_question__question__question_type=QType.SHORT_ANSWER)
              .select_related('attempt__student', 'exam_question__question', 'reviewed_by')
              .order_by('-needs_review', 'exam_question__order', 'exam_question_id', 'attempt__student__email'))
        if request.query_params.get('all') not in ('1', 'true'):
            qs = qs.filter(needs_review=True)
        from src.services.ai.engine import missing_keywords
        data = []
        for a in qs:
            q = a.exam_question.question
            data.append({
                'answer_id': a.id,
                'student_name': a.attempt.student.full_name,
                'student_email': a.attempt.student.email,
                'question': q.text,
                'reference_answer': q.correct_answer_text,
                'required_keywords': q.required_keywords,
                'missing_keywords': missing_keywords(q.required_keywords, a.answer_text) if q.required_keywords else [],
                'answer_text': a.answer_text,
                'similarity': round(a.similarity * 100) if a.similarity is not None else None,
                'grading_method': a.grading_method,
                'awarded_marks': a.awarded_marks,
                'marks': a.exam_question.marks,
                'needs_review': a.needs_review,
                'reviewed': bool(a.reviewed_at),
                'reviewed_by': a.reviewed_by.full_name if a.reviewed_by else None,
                'reviewed_at': a.reviewed_at,
                'original_marks': a.original_marks,
                'review_note': a.review_note,
            })
        return Response(data)

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """Confirm or change the marks of one short answer: {answer_id, awarded_marks, note?}."""
        exam = self.get_object()
        answer = (ExamAnswer.objects.filter(pk=request.data.get('answer_id'), attempt__exam=exam,
                                            attempt__is_submitted=True)
                  .select_related('attempt__student', 'attempt__exam__course', 'exam_question').first())
        if not answer:
            return Response({'detail': 'Answer not found in this exam.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            awarded = int(request.data.get('awarded_marks'))
        except (TypeError, ValueError):
            return Response({'awarded_marks': ['Enter a whole number of marks.']}, status=status.HTTP_400_BAD_REQUEST)
        if not 0 <= awarded <= answer.exam_question.marks:
            return Response({'awarded_marks': [f'Marks must be between 0 and {answer.exam_question.marks}.']},
                            status=status.HTTP_400_BAD_REQUEST)
        note = str(request.data.get('note') or '').strip()[:1000]
        answer, score = review_answer(answer, request.user, awarded, note)
        return Response({'answer_id': answer.id, 'awarded_marks': answer.awarded_marks,
                         'attempt_score': score, 'reviewed_at': answer.reviewed_at})

    # -- Course-level analytics ------------------------------------------------

    @action(detail=False, methods=['get'])
    def course_analytics(self, request):
        """Trend across all exams of one course, plus top and at-risk students. ?course=<id>"""
        course_id = request.query_params.get('course')
        # Only exams that have opened: a scheduled exam has no results to trend yet.
        exams = (Exam.objects.filter(created_by=request.user, course_id=course_id,
                                     available_from__lte=timezone.now())
                 .exclude(status=ExamStatus.DRAFT).select_related('course').order_by('available_from'))
        if not str(course_id or '').isdigit() or not exams.exists():
            return Response({'detail': 'No published exams for that course yet.'}, status=status.HTTP_404_NOT_FOUND)
        course = exams.first().course
        timeline, per_student = [], {}
        for exam in exams:
            finalize_expired(exam.attempts.all())
            total = exam.total_marks
            attempts = list(exam.attempts.filter(is_submitted=True).select_related('student'))
            pcts = [percentage(a.score, total) for a in attempts]
            timeline.append({
                'exam_id': exam.id, 'title': exam.title, 'date': exam.available_from, 'state': exam.state,
                'submitted': len(attempts),
                'average_percentage': round(sum(pcts) / len(pcts), 1) if pcts else None,
                'highest_percentage': max(pcts) if pcts else None,
                'lowest_percentage': min(pcts) if pcts else None,
            })
            for a, pct in zip(attempts, pcts):
                row = per_student.setdefault(a.student_id, {
                    'id': a.student_id, 'full_name': a.student.full_name, 'email': a.student.email,
                    'registration_number': a.student.registration_number, 'percentages': []})
                row['percentages'].append(pct)
        students = []
        for row in per_student.values():
            pcts = row.pop('percentages')
            row['exams_taken'] = len(pcts)
            row['average_percentage'] = round(sum(pcts) / len(pcts), 1)
            students.append(row)
        students.sort(key=lambda r: -r['average_percentage'])
        all_avgs = [t['average_percentage'] for t in timeline if t['average_percentage'] is not None]
        enrolled = course.enrollments.count()
        return Response({
            'course': {'id': course.id, 'code': course.code, 'title': course.title},
            'summary': {
                'exams': len(timeline),
                'enrolled': enrolled,
                'average_percentage': round(sum(all_avgs) / len(all_avgs), 1) if all_avgs else None,
                'participation': round(sum(t['submitted'] for t in timeline) / (len(timeline) * enrolled) * 100, 1)
                if timeline and enrolled else None,
            },
            'timeline': timeline,
            'top_students': students[:5],
            'at_risk': [s for s in students if s['average_percentage'] < 50][:10],
        })

    @action(detail=True, methods=['get'], url_path='export')
    def export(self, request, pk=None):
        """Download the result sheet as CSV."""
        exam = self.get_object()
        total = exam.total_marks
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="exam-{exam.id}-results.csv"'
        response.write('﻿')  # BOM so Excel opens it as UTF-8
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Registration number', 'Score', 'Total marks', 'Percentage',
                         'Started at', 'Submitted at', 'Auto-submitted', 'Submit reason', 'Violations'])
        for a in self._submitted_attempts(exam):
            writer.writerow([
                a.student.full_name, a.student.email, a.student.registration_number,
                a.score, total, percentage(a.score, total),
                timezone.localtime(a.started_at).strftime('%Y-%m-%d %H:%M:%S'),
                timezone.localtime(a.submitted_at).strftime('%Y-%m-%d %H:%M:%S'),
                'yes' if a.auto_submitted else 'no', a.get_submit_reason_display(), a.violations,
            ])
        return response


# ===========================================================================
# STUDENT — list, start (timer), autosave, proctoring, submit + results
#           (scope doc Modules 5 & 6)
# ===========================================================================
def _median(values):
    if not values:
        return None
    values = sorted(values)
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else round((values[mid - 1] + values[mid]) / 2, 1)


def _enrolled(student, course):
    return Enrollment.objects.filter(course=course, student=student).exists()


def _active_attempt_or_response(request, pk):
    """
    The student's running attempt on exam `pk`, or the error response to send.
    Only the browser session that started (or last resumed) the attempt may
    use it — it proves this with the X-Exam-Session header.
    """
    attempt = ExamAttempt.objects.filter(exam_id=pk, student=request.user).select_related('exam').first()
    if not attempt:
        return None, Response({'detail': 'You have not started this exam.'}, status=status.HTTP_404_NOT_FOUND)
    if attempt.is_submitted:
        return None, Response({'detail': 'This exam has already been submitted.', 'score': attempt.score},
                              status=status.HTTP_409_CONFLICT)
    if attempt.session_key and request.META.get(SESSION_HEADER) != attempt.session_key:
        return None, Response(
            {'detail': 'This exam is open in another tab or device. Only the most recently opened one can '
                       'continue.', 'session_replaced': True},
            status=status.HTTP_409_CONFLICT)
    return attempt, None


class AvailableExamsView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        student = request.user
        finalize_expired(ExamAttempt.objects.filter(student=student))
        course_ids = Enrollment.objects.filter(student=student).values_list('course_id', flat=True)
        exams = (Exam.objects.filter(course_id__in=course_ids)
                 .exclude(status=ExamStatus.DRAFT)
                 .select_related('course').order_by('available_from'))
        attempts = {a.exam_id: a for a in ExamAttempt.objects.filter(student=student)}
        now = timezone.now()
        data = []
        for e in exams:
            a = attempts.get(e.id)
            submitted = bool(a and a.is_submitted)
            total = e.total_marks
            data.append({
                'id': e.id,
                'title': e.title,
                'course_code': e.course.code,
                'course_title': e.course.title,
                'available_from': e.available_from,
                'available_until': e.available_until,
                'duration_minutes': e.duration_minutes,
                'question_count': e.question_count,
                'total_marks': total,
                'state': e.state_at(now),
                'is_open': e.is_open(now),
                'in_progress': bool(a and not a.is_submitted),
                'attempted': submitted,
                'score': a.score if submitted else None,
                'percentage': percentage(a.score, total) if submitted else None,
            })
        return Response(data)


class StartExamView(APIView):
    """Start the exam, or resume it after a page reload — the clock keeps running."""
    permission_classes = [IsStudent]

    def post(self, request, pk):
        student = request.user
        exam = get_object_or_404(Exam.objects.select_related('course'), pk=pk)
        if exam.status == ExamStatus.DRAFT or not _enrolled(student, exam.course):
            return Response({'detail': 'You are not enrolled in this exam.'}, status=status.HTTP_403_FORBIDDEN)

        finalize_expired(ExamAttempt.objects.filter(exam=exam, student=student))
        attempt = ExamAttempt.objects.filter(exam=exam, student=student).first()
        if attempt and attempt.is_submitted:
            return Response({'detail': 'You have already submitted this exam.', 'score': attempt.score},
                            status=status.HTTP_409_CONFLICT)
        if not attempt:
            if not exam.is_open():
                return Response({'detail': 'This exam is not open right now.'}, status=status.HTTP_403_FORBIDDEN)
            attempt, created = ExamAttempt.objects.get_or_create(exam=exam, student=student)
            if created:
                attempt.question_order = assign_questions(attempt)
        elif attempt.session_key and request.META.get(SESSION_HEADER) != attempt.session_key:
            # Opened again from a different tab/device: that one takes over, and
            # the switch is reported to the instructor.
            ProctorEvent.objects.create(attempt=attempt, event_type=ProctorEventType.NEW_SESSION)

        attempt.session_key = secrets.token_urlsafe(24)
        attempt.ip_address = _client_ip(request)
        attempt.user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:255]
        attempt.save(update_fields=['question_order', 'session_key', 'ip_address', 'user_agent', 'updated_at'])

        eqs = attempt_questions(attempt)
        remaining = int((attempt.deadline - timezone.now()).total_seconds())
        violations = attempt.proctor_events.filter(event_type__in=VIOLATION_TYPES).count()
        return Response({
            'attempt_id': attempt.id,
            'session_key': attempt.session_key,
            'exam': {'id': exam.id, 'title': exam.title, 'total_marks': exam.total_marks,
                     'duration_minutes': exam.duration_minutes, 'course_code': exam.course.code,
                     'require_fullscreen': exam.require_fullscreen, 'max_violations': exam.max_violations},
            'started_at': attempt.started_at,
            'deadline': attempt.deadline,
            'server_time': timezone.now(),
            'remaining_seconds': max(0, remaining),
            'questions': StudentExamQuestionSerializer(eqs, many=True, context={'attempt': attempt}).data,
            'answers': [
                {'exam_question_id': a.exam_question_id, 'selected_option_id': a.selected_option_id,
                 'answer_text': a.answer_text}
                for a in attempt.answers.all()
            ],
            'tab_switches': violations,
            'violations': violations,
        })


class SaveAnswersView(APIView):
    """
    POST /api/exams/<id>/save/ — autosave while the exam is being taken, so the
    server always holds the latest answers and can submit them when time is up.
    """
    permission_classes = [IsStudent]

    def post(self, request, pk):
        attempt, error = _active_attempt_or_response(request, pk)
        if error:
            return error
        if timezone.now() > attempt.deadline + SUBMIT_GRACE:
            grade_attempt(attempt, auto=True)
            return Response({'detail': 'Time is up — your exam was submitted automatically.', 'expired': True},
                            status=status.HTTP_409_CONFLICT)
        saved = save_answers(attempt, request.data.get('answers'))
        remaining = int((attempt.deadline - timezone.now()).total_seconds())
        return Response({'saved': saved, 'remaining_seconds': max(0, remaining)})


class ProctorEventView(APIView):
    """POST /api/exams/<id>/proctor-event/ — log a tab switch / focus loss."""
    permission_classes = [IsStudent]

    def post(self, request, pk):
        attempt, error = _active_attempt_or_response(request, pk)
        if error:
            return error
        event_type = request.data.get('event_type')
        if event_type not in ProctorEventType.values or event_type == ProctorEventType.NEW_SESSION:
            event_type = ProctorEventType.TAB_SWITCH
        ProctorEvent.objects.create(attempt=attempt, event_type=event_type)
        violations = attempt.proctor_events.filter(event_type__in=VIOLATION_TYPES).count()
        limit = attempt.exam.max_violations
        if limit and violations >= limit:
            grade_attempt(attempt, auto=True, reason=SubmitReason.VIOLATIONS)
            return Response({'tab_switches': violations, 'violations': violations, 'terminated': True,
                             'detail': f'You reached the limit of {limit} violations, so your exam was submitted.'},
                            status=status.HTTP_201_CREATED)
        return Response({'tab_switches': violations, 'violations': violations, 'limit': limit},
                        status=status.HTTP_201_CREATED)


class SubmitExamView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        attempt, error = _active_attempt_or_response(request, pk)
        if error:
            return error
        # Inside the time limit the submitted answers are stored and graded.
        # After it, the payload is ignored and only what was saved in time counts.
        late = timezone.now() > attempt.deadline + SUBMIT_GRACE
        if not late:
            save_answers(attempt, request.data.get('answers'))
        auto = late or bool(request.data.get('auto'))
        grade_attempt(attempt, auto=auto, reason=SubmitReason.TIME if auto else SubmitReason.STUDENT)
        return Response(build_result(attempt))


class ExamResultView(APIView):
    """GET /api/exams/<id>/result/ — a student's own result with question feedback."""
    permission_classes = [IsStudent]

    def get(self, request, pk):
        finalize_expired(ExamAttempt.objects.filter(exam_id=pk, student=request.user))
        attempt = get_object_or_404(
            ExamAttempt.objects.select_related('exam__course'),
            exam_id=pk, student=request.user, is_submitted=True,
        )
        return Response(build_result(attempt))


class MyResultsView(APIView):
    """GET /api/exams/results/ — the student's result history, newest first."""
    permission_classes = [IsStudent]

    def get(self, request):
        finalize_expired(ExamAttempt.objects.filter(student=request.user))
        attempts = (ExamAttempt.objects.filter(student=request.user, is_submitted=True)
                    .select_related('exam__course').order_by('-submitted_at'))
        data = []
        for a in attempts:
            total = a.exam.total_marks
            average = class_average(a.exam)
            data.append({
                'exam_id': a.exam_id,
                'exam_title': a.exam.title,
                'course_code': a.exam.course.code,
                'score': a.score,
                'total_marks': total,
                'percentage': percentage(a.score, total),
                'class_average_percentage': percentage(average, total) if average is not None else None,
                'submitted_at': a.submitted_at,
                'auto_submitted': a.auto_submitted,
            })
        return Response(data)
