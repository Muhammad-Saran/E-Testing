# Agent guide — e-Testing Service

Instructions for AI assistants working in this repository.

## What this project is
A web-based academic examination platform (Final Year Project, COMSATS University Islamabad).
Two roles — **instructor** and **student**. Backend is a **Django REST Framework** API; frontend
is a **React (Vite)** SPA; database is **SQLite** (`server/db.sqlite3`) in all environments.

Requirements come from the scope document `docs/E-Testing Services.docx`, which defines nine
modules. Phase 1 (this build) delivers Modules 1, 2, and basic 7 & 8, plus the architecture,
schema, and auth foundation.

## Repository layout
| Area | Role |
|------|------|
| `server/manage.py` | Django entrypoint; `DJANGO_SETTINGS_MODULE=config.settings` |
| `server/config/` | Project package: `settings.py`, `urls.py`, `wsgi.py`, `asgi.py` |
| `server/src/core/` | Shared base model, DRF permissions (RBAC), pagination |
| `server/src/services/accounts/` | Custom `User`, JWT auth, register/login/me (Module 1) |
| `server/src/services/courses/` | Course, Enrollment, CourseMaterial |
| `server/src/services/questionbank/` | Question + QuestionOption CRUD, CSV import (Module 2) |
| `server/src/services/dashboard/` | Role-aware summary endpoint (Modules 7 & 8) |
| `client/src/` | React app: `pages/`, `components/`, `context/AuthContext`, `api/client` |
| `docs/` | Scope doc, architecture, schema, mockups |

## Environment & settings
- Config via `django-environ` from `server/.env` (see `.env.example`). No committed `.env` secrets.
- Database: **SQLite** at `server/db.sqlite3` in all environments — no external DB server.
- Custom user model `AUTH_USER_MODEL='accounts.User'` (app label `accounts`). Email is the login
  field; `role` is `instructor` or `student`.
- Passwords hashed with bcrypt (`PASSWORD_HASHERS`); JWT via `rest_framework_simplejwt`.

## API surface (Phase 1)
```
POST /api/auth/register/     POST /api/auth/login/     POST /api/auth/refresh/
GET/PATCH /api/auth/me/      POST /api/auth/logout/
CRUD /api/questions/         GET /api/questions/stats/  POST /api/questions/import_csv/
CRUD /api/courses/           CRUD /api/courses/enrollments/   CRUD /api/courses/materials/
GET  /api/dashboard/summary/
GET  /api/health/
```

## Conventions
- DRF `ModelViewSet` + routers for CRUD; role gates in `src/core/permissions.py`
  (`IsInstructor`, `IsStudent`, `IsInstructorOrReadOnly`, `IsOwnerInstructor`).
- Every business model extends `src.core.models.TimeStampedModel` for `created_at`/`updated_at`.
- Instructors only ever see their own courses/questions; querysets are filtered by `request.user`.
- Prefer small, focused diffs; after model changes run `makemigrations` + `migrate`.

## Testing
`python manage.py test` (Django test runner). A manual API smoke test lives in the scratchpad
during development; convert to `tests.py` per app as coverage grows.
