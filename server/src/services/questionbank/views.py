import csv
import io

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from src.core.permissions import IsInstructor
from src.services.notifications.models import NotificationType
from src.services.notifications.services import notify
from django.conf import settings

from src.services.ai.engine import duplicate_pairs, similar_questions, similarity_engine
from .bloom import suggest_level
from .filters import QuestionFilter
from .models import Question, QuestionType
from .serializers import QuestionSerializer


class QuestionLocked(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = ('This question is used in a published or closed exam, so it can no longer '
                      'be changed. Create a new question instead.')
    default_code = 'question_locked'


class QuestionViewSet(viewsets.ModelViewSet):
    """
    Full CRUD over an instructor's question bank (scope doc, Module 2).
    Instructors only see and manage their own questions. Supports filtering
    by course/type/difficulty/subject and free-text search, plus CSV import.
    """
    serializer_class = QuestionSerializer
    permission_classes = [IsInstructor]
    filterset_class = QuestionFilter
    search_fields = ['text', 'subject']
    ordering_fields = ['created_at', 'difficulty', 'marks']

    def get_queryset(self):
        return (
            Question.objects
            .filter(created_by=self.request.user)
            .prefetch_related('options')
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.is_locked:
            raise QuestionLocked()
        serializer.save()

    def perform_destroy(self, instance):
        if instance.is_locked:
            raise QuestionLocked()
        instance.delete()

    @action(detail=False, methods=['post'])
    def similar(self, request):
        """
        Bank questions worded like `text` — shown while writing a question so
        the instructor does not add a duplicate. Body {text, exclude?}.
        """
        text = str(request.data.get('text') or '').strip()
        if len(text.split()) < 3:
            return Response({'matches': [], 'engine': None})
        qs = self.get_queryset()
        if str(request.data.get('exclude') or '').isdigit():
            qs = qs.exclude(pk=request.data['exclude'])
        matches = similar_questions(text, qs, settings.SIMILAR_THRESHOLD)
        return Response({
            'engine': similarity_engine(),
            'matches': [{'id': q.id, 'text': q.text, 'question_type': q.question_type,
                         'course_code': q.course.code if q.course else None, 'score': round(score * 100)}
                        for q, score in matches],
        })

    @action(detail=False, methods=['get'])
    def duplicates(self, request):
        """Near-identical pairs across the whole bank (cleanup tool)."""
        qs = self.get_queryset().select_related('course').order_by('id')
        pairs = duplicate_pairs(qs, settings.DUPLICATE_THRESHOLD)

        def brief(q):
            return {'id': q.id, 'text': q.text, 'question_type': q.question_type, 'locked': q.is_locked,
                    'course_code': q.course.code if q.course else None, 'is_active': q.is_active}
        return Response({'engine': similarity_engine(),
                         'pairs': [{'a': brief(a), 'b': brief(b), 'score': round(s * 100)} for a, b, s in pairs]})

    @action(detail=False, methods=['post'])
    def suggest_difficulty(self, request):
        """Bloom's level suggested from the question's action verbs. Body {text}."""
        level, cue = suggest_level(request.data.get('text'))
        return Response({'difficulty': level, 'cue': cue})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Summary counts for the instructor dashboard."""
        qs = self.get_queryset()
        by_type = {t.value: qs.filter(question_type=t.value).count() for t in QuestionType}
        return Response({
            'total': qs.count(),
            'active': qs.filter(is_active=True).count(),
            'ai_generated': qs.filter(is_ai_generated=True).count(),
            'by_type': by_type,
        })

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def import_csv(self, request):
        """
        Bulk import questions from a CSV (scope doc, Module 2).
        Columns: text, question_type, difficulty, subject, marks, correct_answer_text, options

        `options` is only for MCQs: the choices separated by `|`, with
        `correct_answer_text` equal to the correct choice. True/False rows just
        need `correct_answer_text` = true / false.
        """
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'No file provided (field name: file).'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            decoded = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response({'detail': 'File must be UTF-8 encoded CSV.'},
                            status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(io.StringIO(decoded))
        created, errors = 0, []
        for i, row in enumerate(reader, start=2):  # header is row 1
            data = {
                'text': (row.get('text') or '').strip(),
                'question_type': (row.get('question_type') or 'short_answer').strip(),
                'difficulty': (row.get('difficulty') or 'understand').strip(),
                'subject': (row.get('subject') or '').strip(),
                'marks': int(row['marks']) if (row.get('marks') or '').strip().isdigit() else 1,
                'correct_answer_text': (row.get('correct_answer_text') or '').strip(),
            }
            if data['question_type'] == QuestionType.MCQ:
                choices = [c.strip() for c in (row.get('options') or '').split('|') if c.strip()]
                answer = data['correct_answer_text'].lower()
                data['options'] = [{'text': c, 'is_correct': c.lower() == answer} for c in choices]
            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                serializer.save(created_by=request.user)
                created += 1
            else:
                errors.append({'row': i, 'errors': serializer.errors})

        notify(
            request.user, NotificationType.IMPORT_COMPLETE,
            f'Question import finished: {created} added' + (f', {len(errors)} failed' if errors else ''),
            f'{upload.name}: {created} question(s) were added to your bank'
            + (f' and {len(errors)} row(s) were rejected.' if errors else '.'),
            link='/questions',
        )
        return Response(
            {'created': created, 'failed': len(errors), 'errors': errors[:20]},
            status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST,
        )
