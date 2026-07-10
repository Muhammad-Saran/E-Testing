"""Role-based DRF permissions (scope doc, Module 1 — RBAC)."""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsInstructor(BasePermission):
    """Allow only authenticated instructors."""
    message = 'Only instructors may perform this action.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_instructor)


class IsStudent(BasePermission):
    """Allow only authenticated students."""
    message = 'Only students may perform this action.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_student)


class IsInstructorOrReadOnly(BasePermission):
    """Read for any authenticated user; write for instructors only."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_instructor


class IsOwnerInstructor(BasePermission):
    """Object-level: the instructor who created the object may edit/delete it."""
    message = 'You can only modify your own records.'

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, 'created_by', None) or getattr(obj, 'instructor', None)
        return owner == request.user
