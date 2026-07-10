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
