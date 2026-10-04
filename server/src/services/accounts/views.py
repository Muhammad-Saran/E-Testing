import math
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from src.services.notifications.models import NotificationType
from src.services.notifications.services import notify
from .models import AuthEvent, AuthEventType
from .serializers import (
    LoginTokenSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — create an instructor or student account."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        AuthEvent.log(request, AuthEventType.REGISTER, user=user)
        notify(user, NotificationType.ACCOUNT_ACTIVITY, 'Welcome to e-Testing',
               'Your account was created. Notifications about exams, results and your account appear here.',
               link='/')
        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        refresh['email'] = user.email
        return Response(
            {
                'user': UserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


def lockout_remaining(email):
    """
    Minutes left on a temporary lock, or 0. An account locks after
    LOGIN_MAX_FAILURES failed logins inside the lockout window with no
    successful login in between (scope doc, Module 1 — brute-force resistance).
    """
    if not email:
        return 0
    window = timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    since = timezone.now() - window
    last_ok = (AuthEvent.objects.filter(email__iexact=email, event=AuthEventType.LOGIN, created_at__gte=since)
               .order_by('-created_at').values_list('created_at', flat=True).first())
    failures = AuthEvent.objects.filter(email__iexact=email, event=AuthEventType.LOGIN_FAILED,
                                        created_at__gte=last_ok or since).order_by('-created_at')
    if failures.count() < settings.LOGIN_MAX_FAILURES:
        return 0
    unlock_at = failures.first().created_at + window
    return max(1, math.ceil((unlock_at - timezone.now()).total_seconds() / 60))


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ — email + password -> {access, refresh, user}."""
    serializer_class = LoginTokenSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        email = str(request.data.get('email') or '').strip().lower()
        minutes = lockout_remaining(email)
        if minutes:
            return Response(
                {'detail': f'Too many failed sign-in attempts. This account is locked for {minutes} more '
                           f'minute{"s" if minutes != 1 else ""}. You can also reset your password.',
                 'locked': True, 'retry_after_minutes': minutes},
                status=status.HTTP_429_TOO_MANY_REQUESTS)
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            AuthEvent.log(request, AuthEventType.LOGIN_FAILED, email=email)
            if lockout_remaining(email):
                user = User.objects.filter(email__iexact=email).first()
                AuthEvent.log(request, AuthEventType.LOCKED, user=user, email=email)
                if user:
                    notify(user, NotificationType.ACCOUNT_ACTIVITY, 'Your account was temporarily locked',
                           f'There were {settings.LOGIN_MAX_FAILURES} failed sign-in attempts on your account, so '
                           f'it is locked for {settings.LOGIN_LOCKOUT_MINUTES} minutes. If this was not you, reset '
                           f'your password.', email=True)
            raise
        user = User.objects.filter(email__iexact=email).first()
        AuthEvent.log(request, AuthEventType.LOGIN, user=user, email=email)
        return response


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ — current user's profile."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/ — {current_password, new_password, new_password_confirm}."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        current = request.data.get('current_password') or ''
        new = request.data.get('new_password') or ''
        if not user.check_password(current):
            return Response({'current_password': ['Your current password is incorrect.']},
                            status=status.HTTP_400_BAD_REQUEST)
        if new != (request.data.get('new_password_confirm') or ''):
            return Response({'new_password_confirm': ['The new passwords do not match.']},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new, user=user)
        except DjangoValidationError as exc:
            return Response({'new_password': list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new)
        user.save(update_fields=['password'])
        AuthEvent.log(request, AuthEventType.PASSWORD_CHANGE, user=user)
        notify(user, NotificationType.ACCOUNT_ACTIVITY, 'Your password was changed',
               'The password for your e-Testing account was changed from your profile. If this was not you, '
               'reset your password immediately.', email=True)
        return Response({'detail': 'Password changed.'})


class LogoutView(APIView):
    """
    POST /api/auth/logout/ — body {refresh}. The refresh token is blacklisted
    so it can no longer mint access tokens (explicit session invalidation).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh = request.data.get('refresh')
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass  # already expired / blacklisted — nothing left to invalidate
        AuthEvent.log(request, AuthEventType.LOGOUT, user=request.user)
        return Response({'detail': 'Logged out.'}, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    """
    POST /api/auth/password-reset/ — body {email}. Emails a time-limited,
    single-use reset link. Always answers 200 so the endpoint cannot be used
    to discover which emails are registered.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower().strip()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        AuthEvent.log(request, AuthEventType.PASSWORD_RESET_REQUEST, user=user, email=email)
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f'{settings.FRONTEND_URL.rstrip("/")}/reset-password?uid={uid}&token={token}'
            minutes = settings.PASSWORD_RESET_TIMEOUT // 60
            send_mail(
                subject='Reset your e-Testing password',
                message=(
                    f'Hello {user.full_name},\n\n'
                    f'Use the link below to choose a new password. It can be used once and '
                    f'expires in {minutes} minutes.\n\n{link}\n\n'
                    f'If you did not request this, you can ignore this email.'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        return Response({'detail': 'If that email is registered, a reset link has been sent.'})


class PasswordResetConfirmView(APIView):
    """POST /api/auth/password-reset/confirm/ — body {uid, token, password, password_confirm}."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(data['uid'])), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        # The token embeds the password hash, so it stops working once used.
        if not user or not default_token_generator.check_token(user, data['token']):
            return Response({'detail': 'This reset link is invalid or has expired.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(data['password'], user=user)
        except DjangoValidationError as exc:
            return Response({'password': list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(data['password'])
        user.save(update_fields=['password'])
        AuthEvent.log(request, AuthEventType.PASSWORD_RESET, user=user)
        # Security alert (scope doc, Module 9 — account activity alerts).
        notify(user, NotificationType.ACCOUNT_ACTIVITY, 'Your password was changed',
               'The password for your e-Testing account was just reset. If this was not you, '
               'request a new reset link immediately and contact your administrator.',
               email=True)
        return Response({'detail': 'Password updated. You can now sign in.'})
