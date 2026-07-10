import random

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from src.core.permissions import IsInstructor, IsStudent
from src.services.courses.models import Enrollment
from src.services.questionbank.models import Question, QuestionOption, QuestionType
from src.services.questionbank.serializers import QuestionSerializer
from .models import Exam, ExamAnswer, ExamAttempt, ExamQuestion, ExamStatus
from .serializers import ExamQuestionSerializer, ExamSerializer, StudentExamQuestionSerializer


# ===========================================================================
# INSTRUCTOR — create, configure, compose, publish (scope doc Module 4)
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
        Add N questions of a type (optionally a difficulty) drawn from the
        instructor's bank: body {question_type, difficulty?, count}.
        """
        exam = self.get_object()
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
            'question_count': exam.question_count,
            'total_marks': exam.total_marks,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def add_question(self, request, pk=None):
        """
        Create a brand-new question directly on this exam (scope doc Module 2/4).
        Accepts the full question payload (text, type, difficulty, marks, options,
        correct_answer_text); the question is saved and attached to the exam.
        """
        exam = self.get_object()
        serializer = QuestionSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        question = serializer.save(created_by=request.user)
        eq = ExamQuestion.objects.create(
            exam=exam, question=question, order=exam.exam_questions.count(), marks=question.marks,
        )
        return Response(
            ExamQuestionSerializer(eq).data
            | {'question_count': exam.question_count, 'total_marks': exam.total_marks},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def remove_question(self, request, pk=None):
        exam = self.get_object()
        eq = exam.exam_questions.filter(id=request.data.get('exam_question_id')).first()
        if not eq:
            return Response({'detail': 'Question not in this exam.'}, status=status.HTTP_404_NOT_FOUND)
        question = eq.question
        eq.delete()
        # Questions are authored per-exam; drop the question if no exam uses it.
        if not question.exam_links.exists():
            question.delete()
        return Response({'question_count': exam.question_count, 'total_marks': exam.total_marks})

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        exam = self.get_object()
        if exam.question_count == 0:
            return Response({'detail': 'Add at least one question before publishing.'},
                            status=status.HTTP_400_BAD_REQUEST)
        exam.status = ExamStatus.PUBLISHED
        exam.save(update_fields=['status', 'updated_at'])
        return Response(ExamSerializer(exam).data)

    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        exam = self.get_object()
        exam.status = ExamStatus.DRAFT
        exam.save(update_fields=['status', 'updated_at'])
        return Response(ExamSerializer(exam).data)


# ===========================================================================
# STUDENT — list available, start (timer), submit + auto-grade (Modules 5 & 6)
# ===========================================================================
def _enrolled(student, course):
    return Enrollment.objects.filter(course=course, student=student).exists()


class AvailableExamsView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        student = request.user
        course_ids = Enrollment.objects.filter(student=student).values_list('course_id', flat=True)
        exams = (Exam.objects.filter(course_id__in=course_ids, status=ExamStatus.PUBLISHED)
                 .select_related('course'))
        attempts = {a.exam_id: a for a in ExamAttempt.objects.filter(student=student)}
        now = timezone.now()
        data = []
        for e in exams:
            a = attempts.get(e.id)
            data.append({
                'id': e.id,
                'title': e.title,
                'course_code': e.course.code,
                'course_title': e.course.title,
                'available_from': e.available_from,
                'available_until': e.available_until,
                'duration_minutes': e.duration_minutes,
                'question_count': e.question_count,
                'total_marks': e.total_marks,
                'is_open': e.is_open(now),
                'attempted': bool(a and a.is_submitted),
                'score': a.score if (a and a.is_submitted) else None,
            })
        return Response(data)


class StartExamView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        student = request.user
        exam = get_object_or_404(Exam.objects.select_related('course'), pk=pk, status=ExamStatus.PUBLISHED)
        if not _enrolled(student, exam.course):
            return Response({'detail': 'You are not enrolled in this course.'}, status=status.HTTP_403_FORBIDDEN)
        if not exam.is_open():
            return Response({'detail': 'This exam is not open right now.'}, status=status.HTTP_403_FORBIDDEN)

        attempt, _created = ExamAttempt.objects.get_or_create(exam=exam, student=student)
        if attempt.is_submitted:
            return Response({'detail': 'You have already submitted this exam.', 'score': attempt.score},
                            status=status.HTTP_409_CONFLICT)

        eqs = list(exam.exam_questions.select_related('question').prefetch_related('question__options'))
        if exam.shuffle_questions:
            random.shuffle(eqs)
        remaining = int((attempt.deadline - timezone.now()).total_seconds())
        return Response({
            'attempt_id': attempt.id,
            'exam': {'id': exam.id, 'title': exam.title, 'total_marks': exam.total_marks,
                     'duration_minutes': exam.duration_minutes},
            'started_at': attempt.started_at,
            'deadline': attempt.deadline,
            'remaining_seconds': max(0, remaining),
            'questions': StudentExamQuestionSerializer(eqs, many=True).data,
        })


class SubmitExamView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        student = request.user
        exam = get_object_or_404(Exam, pk=pk)
        attempt = get_object_or_404(ExamAttempt, exam=exam, student=student)
        if attempt.is_submitted:
            return Response({'detail': 'Already submitted.', 'score': attempt.score},
                            status=status.HTTP_409_CONFLICT)

        submitted = {str(a.get('exam_question_id')): a for a in request.data.get('answers', [])}
        score = 0
        results = []
        for eq in exam.exam_questions.select_related('question'):
            ans = submitted.get(str(eq.id), {})
            qtype = eq.question.question_type
            selected_option_id = ans.get('selected_option_id')
            answer_text = (ans.get('answer_text') or '').strip()

            if qtype in (QuestionType.MCQ, QuestionType.TRUE_FALSE):
                opt = QuestionOption.objects.filter(id=selected_option_id, question=eq.question).first()
                is_correct = bool(opt and opt.is_correct)
                selected_option_id = opt.id if opt else None
            else:  # short answer — normalized exact match (T5 semantic grading is Phase 2)
                ref = (eq.question.correct_answer_text or '').strip().lower()
                is_correct = bool(ref and answer_text.lower() == ref)
                selected_option_id = None

            awarded = eq.marks if is_correct else 0
            score += awarded
            ExamAnswer.objects.update_or_create(
                attempt=attempt, exam_question=eq,
                defaults={'selected_option_id': selected_option_id, 'answer_text': answer_text,
                          'is_correct': is_correct, 'awarded_marks': awarded},
            )
            results.append({'exam_question_id': eq.id, 'is_correct': is_correct, 'awarded_marks': awarded})

        attempt.score = score
        attempt.is_submitted = True
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=['score', 'is_submitted', 'submitted_at', 'updated_at'])

        total = exam.total_marks
        return Response({
            'score': score,
            'total_marks': total,
            'percentage': round(score / total * 100, 1) if total else 0,
            'correct_count': sum(1 for r in results if r['is_correct']),
            'question_count': len(results),
            'results': results,
        })


class ExamResultView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk):
        attempt = get_object_or_404(ExamAttempt, exam_id=pk, student=request.user, is_submitted=True)
        total = attempt.exam.total_marks
        return Response({
            'exam_title': attempt.exam.title,
            'score': attempt.score,
            'total_marks': total,
            'percentage': round(attempt.score / total * 100, 1) if total else 0,
            'submitted_at': attempt.submitted_at,
        })
