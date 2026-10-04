from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class Role(models.TextChoices):
    INSTRUCTOR = 'instructor', 'Instructor'
    STUDENT = 'student', 'Student'


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user for the E-Testing Service.

    Login is by email (scope doc, Module 1). A single `role` field drives the
    dual-role RBAC — every account is either an instructor or a student.
    Passwords are hashed with bcrypt (see PASSWORD_HASHERS in settings).
    """
    email = models.EmailField(unique=True, max_length=255)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)

    # Instructor-issued institutional id / student registration number.
    registration_number = models.CharField(max_length=50, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['-date_joined']
        indexes = [models.Index(fields=['role', 'is_active'])]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        name = f'{self.first_name} {self.last_name}'.strip()
        return name or self.email

    @property
    def is_instructor(self):
        return self.role == Role.INSTRUCTOR

    @property
    def is_student(self):
        return self.role == Role.STUDENT


class AuthEventType(models.TextChoices):
    REGISTER = 'register', 'Registered'
    LOGIN = 'login', 'Logged in'
    LOGIN_FAILED = 'login_failed', 'Failed login'
    LOCKED = 'locked', 'Account temporarily locked'
    LOGOUT = 'logout', 'Logged out'
    PASSWORD_RESET_REQUEST = 'password_reset_request', 'Password reset requested'
    PASSWORD_RESET = 'password_reset', 'Password reset'
    PASSWORD_CHANGE = 'password_change', 'Password changed'


class AuthEvent(models.Model):
    """Audit trail of authentication events (scope doc, Module 1)."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='auth_events')
    # Kept separately so failed logins for unknown accounts are still recorded.
    email = models.EmailField(max_length=255, blank=True)
    event = models.CharField(max_length=30, choices=AuthEventType.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['event', 'created_at'])]

    def __str__(self):
        return f'{self.email or self.user_id} · {self.event}'

    @classmethod
    def log(cls, request, event, user=None, email=''):
        ip = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip() \
            or request.META.get('REMOTE_ADDR') or None
        return cls.objects.create(
            user=user, email=(email or getattr(user, 'email', '') or '')[:255], event=event, ip_address=ip,
        )
