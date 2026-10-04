import csv
import io

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db.models import Q
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.http import FileResponse, Http404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from src.core.permissions import IsInstructorOrReadOnly
from .models import Course, CourseMaterial, Enrollment
from .serializers import CourseMaterialSerializer, CourseSerializer, EnrollmentSerializer

User = get_user_model()


def _student_payload(student, enrollment):
    return {
        'enrollment_id': enrollment.id,
        'id': student.id,
        'full_name': student.full_name,
        'email': student.email,
        'registration_number': student.registration_number,
        'enrolled_at': enrollment.created_at,
    }


class CourseViewSet(viewsets.ModelViewSet):
    """Instructors manage their own courses; students see courses they can read."""
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsInstructorOrReadOnly]
    filterset_fields = ['is_active', 'instructor']
    search_fields = ['code', 'title']

    def get_queryset(self):
        user = self.request.user
        if user.is_instructor:
            return Course.objects.filter(instructor=user)
        # students: courses they are enrolled in
        return Course.objects.filter(enrollments__student=user).distinct()

    def perform_create(self, serializer):
        serializer.save(instructor=self.request.user)

    # -- Roster management (instructor adds students, scope doc Module 7/8) -----

    @action(detail=True, methods=['get'])
    def roster(self, request, pk=None):
        """List the students enrolled in this course (instructor only)."""
        if not request.user.is_instructor:
            return Response({'detail': 'Only the course instructor can view the roster.'},
                            status=status.HTTP_403_FORBIDDEN)
        course = self.get_object()
        enrollments = course.enrollments.select_related('student')
        return Response([_student_payload(e.student, e) for e in enrollments])

    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        """Enroll a student into this course by email or registration number."""
        course = self.get_object()
        identifier = (request.data.get('identifier') or '').strip()
        if not identifier:
            return Response({'detail': 'Enter a student email or registration number.'},
                            status=status.HTTP_400_BAD_REQUEST)

        student = (
            User.objects.filter(role='student')
            .filter(Q(email__iexact=identifier) | Q(registration_number__iexact=identifier))
            .first()
        )
        if not student:
            return Response(
                {'detail': f'No student found with email or registration number "{identifier}".'},
                status=status.HTTP_404_NOT_FOUND,
            )

        enrollment, created = Enrollment.objects.get_or_create(course=course, student=student)
        if not created:
            return Response({'detail': f'{student.full_name} is already enrolled.'},
                            status=status.HTTP_409_CONFLICT)
        return Response(_student_payload(student, enrollment), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def enroll_csv(self, request, pk=None):
        """Bulk-enroll a class from a CSV (multipart "file"; create_missing=true to invite new students)."""
        course = self.get_object()
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'Attach a CSV file (field name: file).'}, status=status.HTTP_400_BAD_REQUEST)
        create_missing = str(request.data.get('create_missing', '')).lower() in ('1', 'true', 'yes', 'on')
        report, error = bulk_enroll(course, upload, create_missing)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)
        return Response(report, status=status.HTTP_201_CREATED if report['enrolled'] else status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def unenroll(self, request, pk=None):
        """Remove a student from this course."""
        course = self.get_object()
        student_id = request.data.get('student_id')
        deleted, _ = Enrollment.objects.filter(course=course, student_id=student_id).delete()
        if not deleted:
            return Response({'detail': 'That student is not enrolled in this course.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _send_account_invite(user, course):
    """Email a new student a single-use link to choose their password."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f'{settings.FRONTEND_URL.rstrip("/")}/reset-password?uid={uid}&token={token}'
    send_mail(
        subject='Your e-Testing account',
        message=(f'Hello {user.full_name},\n\nYour instructor enrolled you in {course.code} — {course.title} '
                 f'on e-Testing. Choose your password with the link below, then sign in with this email '
                 f'address.\n\n{link}\n\nThe link can be used once and expires in '
                 f'{settings.PASSWORD_RESET_TIMEOUT // 60} minutes; after that use "Forgot password".'),
        from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[user.email], fail_silently=True,
    )


def bulk_enroll(course, upload, create_missing):
    """
    Enroll every student listed in a CSV. Columns (header row required):
    email and/or registration_number; optional first_name, last_name.
    With create_missing, unknown emails get a new student account and an
    email invite to set their password.
    """
    try:
        text = upload.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        return None, 'File must be a UTF-8 encoded CSV.'
    reader = csv.DictReader(io.StringIO(text))
    headers = {(h or '').strip().lower() for h in (reader.fieldnames or [])}
    if not headers & {'email', 'registration_number'}:
        return None, 'The CSV needs a header row with an "email" or "registration_number" column.'

    report = {'enrolled': 0, 'already': 0, 'created': 0, 'not_found': [], 'errors': []}
    domain = settings.INSTITUTION_EMAIL_DOMAIN.lower().lstrip('@')
    for line, raw in enumerate(reader, start=2):
        row = {(k or '').strip().lower(): (v or '').strip() for k, v in raw.items()}
        email, reg = row.get('email', '').lower(), row.get('registration_number', '')
        if not email and not reg:
            continue
        lookup = Q(email__iexact=email) if email else Q()
        if reg:
            lookup = lookup | Q(registration_number__iexact=reg) if email else Q(registration_number__iexact=reg)
        user = User.objects.filter(lookup).first()
        if user and not user.is_student:
            report['errors'].append({'row': line, 'error': f'{user.email} is an instructor account.'})
            continue
        if not user:
            if not (create_missing and email):
                report['not_found'].append(email or reg)
                continue
            try:
                validate_email(email)
            except DjangoValidationError:
                report['errors'].append({'row': line, 'error': f'"{email}" is not a valid email address.'})
                continue
            if domain and not email.endswith('@' + domain):
                report['errors'].append({'row': line, 'error': f'{email} is not an @{domain} address.'})
                continue
            user = User.objects.create_user(
                email=email, password=None, role='student', registration_number=reg,
                first_name=row.get('first_name', ''), last_name=row.get('last_name', ''),
            )
            _send_account_invite(user, course)
            report['created'] += 1
        _, created = Enrollment.objects.get_or_create(course=course, student=user)
        report['enrolled' if created else 'already'] += 1
    return report, None


class EnrollmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only list of enrollments. Enrolling is done by the course instructor
    through /courses/<id>/enroll/ — students cannot add themselves to a course
    (that would give them access to its exams and materials).
    """
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_instructor:
            return Enrollment.objects.filter(course__instructor=user)
        return Enrollment.objects.filter(student=user)


class CourseMaterialViewSet(viewsets.ModelViewSet):
    """
    Course material repository (scope doc, Module 7). Instructors upload to
    their own courses; students can list/download material for courses they
    are enrolled in.
    """
    serializer_class = CourseMaterialSerializer
    permission_classes = [IsAuthenticated, IsInstructorOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ['course']
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        qs = CourseMaterial.objects.select_related('course')
        if user.is_instructor:
            return qs.filter(course__instructor=user)
        return qs.filter(course__enrollments__student=user).distinct()

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    def perform_destroy(self, instance):
        instance.file.delete(save=False)
        instance.delete()

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Stream the file — only reachable through the enrollment-filtered queryset."""
        material = self.get_object()
        try:
            handle = material.file.open('rb')
        except (FileNotFoundError, ValueError):
            raise Http404('The file for this material is missing.')
        return FileResponse(handle, as_attachment=True, filename=material.file.name.rsplit('/', 1)[-1])
