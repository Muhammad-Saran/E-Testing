"""
Django settings for the E-Testing Service backend.

Config is loaded from a `.env` file at the backend root (same folder as
manage.py) via django-environ. See `.env.example` for the variable names.

Database: SQLite (`db.sqlite3`) is the project standard for all environments.
"""
import sys
from datetime import timedelta
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    ENVIRONMENT=(str, 'local'),
    SECRET_KEY=(str, 'django-insecure-dev-key-change-me-in-production'),
    ALLOWED_HOSTS=(str, '127.0.0.1,localhost'),
    CORS_ALLOWED_ORIGINS=(str, 'http://127.0.0.1:5173,http://localhost:5173'),
)
environ.Env.read_env(BASE_DIR / '.env')

DEBUG = env('DEBUG')
ENVIRONMENT = env('ENVIRONMENT')
SECRET_KEY = env('SECRET_KEY')
ALLOWED_HOSTS = [h.strip() for h in env('ALLOWED_HOSTS').split(',') if h.strip()]

# Institutional email domain used to gate registration (scope doc, Module 1).
INSTITUTION_EMAIL_DOMAIN = env('INSTITUTION_EMAIL_DOMAIN', default='')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # THIRD PARTY
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',

    # PROJECT APPS
    'src.core',
    'src.services.accounts',
    'src.services.courses',
    'src.services.questionbank',
    'src.services.exams',
    'src.services.dashboard',
    'src.services.notifications',
    'src.services.ai',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    # Serves collected static files (admin CSS/JS) in production.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
AUTH_USER_MODEL = 'accounts.User'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# DATABASE — SQLite (project standard, all environments).
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': env('DATABASE_PATH', default=str(BASE_DIR / 'db.sqlite3')),
        'OPTIONS': {
            # AI jobs and many concurrent exam submissions write at once: wait for
            # the lock instead of failing, take it up front (IMMEDIATE) to avoid
            # deadlock-style "database is locked" errors, and use WAL so readers
            # never block writers.
            'timeout': 20,
            'transaction_mode': 'IMMEDIATE',
            'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;',
        },
    }
}

# ---------------------------------------------------------------------------
# PASSWORD HASHING — bcrypt first (scope doc, Module 1), PBKDF2 fallback.
# ---------------------------------------------------------------------------
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# DJANGO REST FRAMEWORK + JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'src.core.pagination.DefaultPagination',
    'PAGE_SIZE': 20,
    # Brute-force protection on the public auth endpoints (per client IP).
    'DEFAULT_THROTTLE_RATES': {
        'login': env('THROTTLE_LOGIN', default='20/min'),
        'register': env('THROTTLE_REGISTER', default='20/hour'),
        'password_reset': env('THROTTLE_PASSWORD_RESET', default='5/hour'),
    },
}
TESTING = 'test' in sys.argv[1:2]
if TESTING:  # the suite logs in many times from the same "IP"
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {k: '10000/min' for k in REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']}

# Account lockout: this many failed logins within the window locks the account
# for LOGIN_LOCKOUT_MINUTES (scope doc, Module 1 — brute-force resistance).
LOGIN_MAX_FAILURES = env.int('LOGIN_MAX_FAILURES', default=5)
LOGIN_LOCKOUT_MINUTES = env.int('LOGIN_LOCKOUT_MINUTES', default=15)

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env.int('JWT_ACCESS_MINUTES', default=60)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env.int('JWT_REFRESH_DAYS', default=7)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# ---------------------------------------------------------------------------
# EMAIL + ACCOUNT RECOVERY (scope doc, Module 1)
# Local dev prints emails to the runserver console; set EMAIL_BACKEND to the
# SMTP backend (plus EMAIL_HOST etc.) to send real mail.
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='localhost')
EMAIL_PORT = env.int('EMAIL_PORT', default=25)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=False)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='e-Testing <no-reply@e-testing.local>')

# Password-reset links are single-use and expire after this many seconds.
PASSWORD_RESET_TIMEOUT = env.int('PASSWORD_RESET_TIMEOUT', default=60 * 60)
# Where the React app is reachable — used to build links placed in emails.
FRONTEND_URL = env('FRONTEND_URL', default='http://127.0.0.1:8000')

# ---------------------------------------------------------------------------
# NOTIFICATIONS (scope doc, Module 9)
# ---------------------------------------------------------------------------
# Send notification emails (exam scheduled, reminders, results, account alerts).
NOTIFICATION_EMAILS = env.bool('NOTIFICATION_EMAILS', default=True)
# Reminders go out this many minutes before an exam opens (comma-separated).
EXAM_REMINDER_MINUTES = [int(m) for m in env('EXAM_REMINDER_MINUTES', default='1440,60').split(',') if m.strip()]

# ---------------------------------------------------------------------------
# AI — T5 question generation (Module 3) + semantic short-answer grading (Module 6)
# Install the models with `pip install -r requirements-ai.txt`. Without them
# (or with AI_ENGINE=rule) a lightweight rule-based engine is used instead.
# ---------------------------------------------------------------------------
AI_ENGINE = env('AI_ENGINE', default='auto')  # auto | t5 | rule
AI_QG_MODEL = env('AI_QG_MODEL', default='valhalla/t5-small-qa-qg-hl')
# "Better quality" option in the generator: the t5-base version of the same model.
AI_QG_MODEL_BETTER = env('AI_QG_MODEL_BETTER', default='valhalla/t5-base-qa-qg-hl')
AI_SIMILARITY_MODEL = env('AI_SIMILARITY_MODEL', default='sentence-transformers/sentence-t5-base')
# Short answers at or above this similarity get full marks; at or above the
# partial threshold they get half marks (rounded down).
SHORT_ANSWER_THRESHOLD = env.float('SHORT_ANSWER_THRESHOLD', default=0.86)
SHORT_ANSWER_PARTIAL_THRESHOLD = env.float('SHORT_ANSWER_PARTIAL_THRESHOLD', default=0.80)
# Judged short answers scoring inside this band are flagged for instructor review.
SHORT_ANSWER_REVIEW_MIN = env.float('SHORT_ANSWER_REVIEW_MIN', default=0.78)
SHORT_ANSWER_REVIEW_MAX = env.float('SHORT_ANSWER_REVIEW_MAX', default=0.92)
# Question-bank duplicate detection (Sentence-T5 cosine; lexical when no model).
DUPLICATE_THRESHOLD = env.float('DUPLICATE_THRESHOLD', default=0.93)
SIMILAR_THRESHOLD = env.float('SIMILAR_THRESHOLD', default=0.88)
# Run AI generation jobs in a background thread (False = inline, used by tests).
AI_ASYNC = env.bool('AI_ASYNC', default=True)
AI_MAX_SOURCE_CHARS = env.int('AI_MAX_SOURCE_CHARS', default=20000)

# ---------------------------------------------------------------------------
# AUDIT LOG — grading operations (scope doc, Module 6) go to logs/audit.log.
# Authentication events are stored in the AuthEvent table (Module 1).
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'audit': {'format': '%(asctime)s %(levelname)s %(name)s %(message)s'}},
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
        # Test runs must not write into the real audit trail.
        'audit_file': {'class': 'logging.NullHandler'} if 'test' in sys.argv[1:2] else {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'audit.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'audit',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'etesting.audit': {'handlers': ['audit_file'], 'level': 'INFO', 'propagate': False},
        'etesting': {'handlers': ['console'], 'level': 'INFO'},
    },
}

# ---------------------------------------------------------------------------
# CORS (React dev server)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [o.strip() for o in env('CORS_ALLOWED_ORIGINS').split(',') if o.strip()]
CORS_ALLOW_CREDENTIALS = True
# The exam client identifies its browser session with this header (Module 5).
CORS_ALLOW_HEADERS = (*default_headers, 'x-exam-session')
CORS_EXPOSE_HEADERS = ['Content-Disposition']

# ---------------------------------------------------------------------------
# PRODUCTION HARDENING — active when DEBUG=False. Put the app behind HTTPS
# (e.g. Caddy / IIS / nginx) and set HTTPS=True so cookies and redirects are secure.
# ---------------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env('CSRF_TRUSTED_ORIGINS', default='').split(',') if o.strip()]
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_REFERRER_POLICY = 'same-origin'
    if env.bool('HTTPS', default=False):
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
        SECURE_SSL_REDIRECT = True
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30

# ---------------------------------------------------------------------------
# I18N / STATIC
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = env('TIME_ZONE', default='UTC')
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Built React SPA (client/dist) — Django serves it so `runserver` shows the app.
FRONTEND_DIST = BASE_DIR.parent / 'client' / 'dist'
