# Agent guide — e-Testing Service

Instructions for AI assistants working in this repository.

## What this project is
A web-based academic examination platform (Final Year Project, COMSATS University Islamabad).
Two roles — **instructor** and **student**. Backend is a **Django REST Framework** API; frontend
is a **React (Vite)** SPA; database is **SQLite** (`server/db.sqlite3`) in all environments.

Requirements come from the scope document `docs/E-Testing Services.docx`, which defines nine
modules — all nine are implemented (status table in `README.md`).

## Repository layout
| Area | Role |
|------|------|
| `server/manage.py` | Django entrypoint; `DJANGO_SETTINGS_MODULE=config.settings` |
| `server/config/` | Project package: `settings.py`, `urls.py`, `wsgi.py`, `asgi.py` |
| `server/src/core/` | Shared base model, DRF permissions (RBAC), pagination |
| `server/src/services/accounts/` | Custom `User`, JWT auth, register/login/me (Module 1) |
| `server/src/services/courses/` | Course, Enrollment, CourseMaterial |
| `server/src/services/questionbank/` | Question + QuestionOption CRUD, CSV import (Module 2) |
| `server/src/services/exams/` | Exam, ExamQuestion, ExamAttempt, ExamAnswer, ProctorEvent (Modules 4–6, analytics for 8). Grading/timer logic in `services.py` |
| `server/src/services/ai/` | Module 3 + Module 6 grading: `engine.py` (model loading, T5 inference, `answer_similarity`), `generation.py` (question pipeline), `GenerationJob` + background `services.py` |
| `server/src/services/notifications/` | Module 9: `Notification` log, `notify()` (in-app + email), `dispatch_scheduled()` reminders / results-ready, announcements |
| `server/src/services/dashboard/` | Role-aware summary endpoint (Modules 7 & 8) |
| `client/src/` | React app: `pages/`, `components/`, `context/AuthContext`, `api/client`, `utils/format.js` |
| `docs/` | Scope doc, architecture, schema, mockups |

## Environment & settings
- Config via `django-environ` from `server/.env` (see `.env.example`). No committed `.env` secrets.
- Database: **SQLite** at `server/db.sqlite3` in all environments — no external DB server.
- Custom user model `AUTH_USER_MODEL='accounts.User'` (app label `accounts`). Email is the login
  field; `role` is `instructor` or `student`.
- Passwords hashed with bcrypt (`PASSWORD_HASHERS`); JWT via `rest_framework_simplejwt`.

## API surface
Full list in `README.md`. Groups: `/api/auth/` (incl. logout blacklist + password reset),
`/api/questions/`, `/api/courses/` (+ materials with authenticated download), `/api/exams/`
(instructor CRUD/compose/publish/close/analytics/export; student available/start/save/
proctor-event/submit/result/results; instructor students/student_timeline), `/api/ai/jobs/`
(create/poll/commit/status), `/api/notifications/` (list/unread_count/read/mark_all_read/announce),
`/api/dashboard/summary/`, `/api/health/`.

## Exam rules worth knowing
- Stored `Exam.status` is draft/published/closed; the API also returns a derived `state`
  (draft/scheduled/active/closed) computed from the availability window.
- The timer is enforced server-side: expired attempts are auto-graded by
  `exams.services.finalize_expired` whenever lists/results are read, and late submits only
  count answers autosaved before the deadline (+15 s grace).
- Submitted attempts are immutable (`ExamAttempt.save` raises). Questions used in a non-draft
  exam are locked (409 on edit/delete). Exam questions can only change while the exam is a draft.
- Correct answers are only revealed after the exam's state is `closed` and nobody is still
  within their time limit (`exams.services.answers_released`).
- Short answers are graded by `ai.engine.answer_similarity`: exact → full; 1–3-word references
  by spelling-tolerant match (numbers exact); longer ones by Sentence-T5. Thresholds
  `SHORT_ANSWER_THRESHOLD` (full) / `SHORT_ANSWER_PARTIAL_THRESHOLD` (half marks).

## Exam delivery rules (security)
- `start` assigns the attempt's questions once (`ExamAttempt.question_order`; a random subset when
  `Exam.questions_per_student` is set — pool questions must have equal marks, checked on publish).
  Grading, results and saving all use the attempt's questions only (`exams.services.attempt_questions`).
- MCQ options are shuffled per student (`shuffle_options`, seeded by attempt + question).
- `start` rotates `ExamAttempt.session_key`; save / proctor-event / submit must send it in the
  `X-Exam-Session` header, otherwise 409 `session_replaced` (one active tab/device). Opening the
  exam from another tab records a `new_session` proctor event. Tests use a `start()` helper that sets it.
- Violations (`VIOLATION_TYPES`: tab switch, blur, fullscreen exit) auto-submit the attempt at
  `Exam.max_violations` with `submit_reason='violations'`.
- Short answers in the review band, or missing `Question.required_keywords`, get `needs_review`;
  `exams.services.review_answer` is the only sanctioned change to a submitted result (audited).

## AI + notifications rules worth knowing
- AI models are optional: `AI_ENGINE=auto` uses T5 if `torch`/`transformers` import, else the
  rule-based fallback. Tests force `AI_ENGINE='rule'` (and `AI_ASYNC=False`) so they never load
  models. Models load in float32 (T5 is unstable in fp16). Sentence-T5 is implemented on plain
  `transformers` — do not add `sentence-transformers` (it pulls scipy, whose DLLs are blocked
  by Windows Application Control on the dev machine).
- Other modules send notifications only through `notifications.services.notify(...)`; pass a
  `dedupe_key` for anything a scheduler may fire twice.
- Grading writes one line per attempt to `server/logs/audit.log` (`etesting.audit` logger;
  silenced during tests).

## Conventions
- DRF `ModelViewSet` + routers for CRUD; role gates in `src/core/permissions.py`
  (`IsInstructor`, `IsStudent`, `IsInstructorOrReadOnly`, `IsOwnerInstructor`).
- Every business model extends `src.core.models.TimeStampedModel` for `created_at`/`updated_at`.
- Instructors only ever see their own courses/questions; querysets are filtered by `request.user`.
- Prefer small, focused diffs; after model changes run `makemigrations` + `migrate`.

## Testing
`python manage.py test src` (Django test runner) from `server/`. Each app has `tests.py` plus
feature files (`test_*.py`: lockout, bulk enroll, question tools, practice, exam features).

## Management commands
- `python manage.py ai_warmup [--better]` — download/load the T5 models.
- `python manage.py send_notifications` — send due reminders / results-ready alerts (cron).
- `python manage.py seed_demo [--fast] [--load-test N] [--remove]` — demo data (@demo.edu, password Demo@12345).
- `python manage.py serve` — production server (Waitress); `send_test_email <to>` checks SMTP.
- `server/scripts/load_test.py` — concurrent exam load test (see docs/testing/load-test.md).
- Login is throttled (`THROTTLE_*`) and accounts lock after `LOGIN_MAX_FAILURES`; throttles are
  disabled when `manage.py test` runs.

## Frontend
- Design system in `client/src/index.css` (CSS variables, light + `[data-theme='dark']`); shared
  components in `components/ui.jsx` (PageHeader, StatCard, EmptyState, Alert, ScoreRing, Tabs…),
  toasts via `context/ToastContext`, theme via `context/ThemeContext`, Chart.js theming in
  `utils/charts.js` (give charts `key={theme}` so they re-render on theme change). Icons: lucide-react.
- Pages are lazy-loaded in `App.jsx`. Tests: `npm test` (Vitest, `*.test.jsx`), `npm run e2e`
  (Playwright, `client/e2e/`, system Chrome, temporary seeded DB).
