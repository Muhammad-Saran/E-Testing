# e-Testing Service — System Architecture

**Project:** e-Testing Service (FYP, COMSATS University Islamabad)
**Phase:** 1 (30% delivery)
**Stack:** Django REST Framework · React (Vite) · SQLite · JWT

---

## 1. Architectural style

The system is a **client–server single-page application** with a clear separation between:

- **Presentation tier** — a React SPA that renders all UI and holds no business rules.
- **Application tier** — a Django REST Framework API exposing stateless JSON endpoints.
- **Data tier** — a relational database (SQLite) accessed through the Django ORM.

Communication is exclusively over a **RESTful HTTP API** secured with **JWT bearer tokens**.
The frontend and backend are deployed and scaled independently.

```
┌──────────────────────────────┐        HTTPS / JSON        ┌───────────────────────────────┐
│        CLIENT (React SPA)     │  ───────────────────────► │      SERVER (Django + DRF)     │
│                               │   Authorization: Bearer   │                                │
│  pages/  components/  context │  ◄─────────────────────── │  config/  ·  src/services/*    │
│  AuthContext · axios client   │        JWT access token   │  src/core (RBAC, pagination)   │
└──────────────────────────────┘                            └───────────────┬────────────────┘
        localStorage: access / refresh                                       │ Django ORM
                                                                             ▼
                                                              ┌───────────────────────────────┐
                                                              │        DATABASE (SQLite)        │
                                                              │  users · courses · questions …  │
                                                              └───────────────────────────────┘
```

## 2. Backend structure (modular monolith)

The Django project is organised as a **modular monolith** — one deployable, many cohesive apps.

```
server/
├── config/                     # project package (settings, urls, wsgi, asgi)
├── src/
│   ├── core/                   # shared: TimeStampedModel, RBAC permissions, pagination
│   └── services/
│       ├── accounts/           # Module 1 — custom User, JWT auth, RBAC
│       ├── courses/            # Course, Enrollment, CourseMaterial
│       ├── questionbank/       # Module 2 — Question, QuestionOption, CSV import
│       └── dashboard/          # Modules 7 & 8 — role-aware summary
└── manage.py
```

**Why modular monolith:** a two-person FYP benefits from one codebase and one deployment,
while per-module apps keep boundaries clean and let each of the nine modules evolve
independently. Each app owns its models, serializers, views, URLs, and admin.

## 3. Request lifecycle

1. React calls `api/*` via an axios instance that attaches the JWT access token.
2. `CorsMiddleware` admits the request from the React origin (`:5173`).
3. DRF authenticates the token (`JWTAuthentication`) and resolves `request.user`.
4. A **role-based permission** (`IsInstructor` / `IsStudent` / `IsInstructorOrReadOnly`)
   authorises the action.
5. The ViewSet filters its queryset by `request.user` (an instructor only ever sees their
   own courses/questions), runs the serializer, and returns JSON.
6. On a `401`, the axios response interceptor silently refreshes the token once and replays
   the request; a failed refresh redirects to `/login`.

## 4. Authentication & authorization (Module 1)

| Concern | Decision |
|---------|----------|
| Identity | Custom `accounts.User`, **email as username**, single `role` field. |
| Sessions | **Stateless JWT** (`djangorestframework-simplejwt`) — access + refresh tokens. |
| Passwords | **bcrypt** (`BCryptSHA256PasswordHasher`) — adaptive cost, per scope doc. |
| RBAC | Two roles: `instructor`, `student`. Enforced by DRF permission classes. |
| Registration gate | Optional institutional email-domain check (`INSTITUTION_EMAIL_DOMAIN`). |

## 5. Frontend structure

```
client/src/
├── api/client.js               # axios instance + JWT request/refresh interceptors
├── context/AuthContext.jsx     # login / register / logout / current user
├── components/                 # ProtectedRoute (role guard), Layout, Navbar
└── pages/                      # Login, Register, Student/Instructor dashboards, QuestionBank
```

Routing (`react-router-dom`) guards every private route with `ProtectedRoute`, which redirects
unauthenticated users to `/login` and role-mismatched users to their own dashboard. Analytics
use **Chart.js** via `react-chartjs-2`.

## 6. Configuration & environments

Config is loaded from `server/.env` via `django-environ` (see `.env.example`). The database is
**SQLite** (`server/db.sqlite3`) in every environment — it ships with Python, needs no external
server, and keeps development and deployment identical with zero database setup.

## 7. Roadmap (Phase 2 modules)

Modules 3 (AI/T5 question generation), 4 (exam scheduling), 5 (delivery/proctoring),
6 (auto-grading), and 9 (notifications) attach to this same architecture: new `src/services/*`
apps exposing REST endpoints, with the T5 model served from a Python inference layer that the
Django backend calls. The current schema already reserves the fields (`is_ai_generated`,
`correct_answer_text`, difficulty tiers) these modules will use.
