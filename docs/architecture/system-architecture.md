# e-Testing Service — System Architecture

**Project:** e-Testing Service (FYP, COMSATS University Islamabad)
**Milestone:** 100% — all nine modules
**Stack:** Django REST Framework · React (Vite) · SQLite · JWT · T5 Transformer (Hugging Face)

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
│       ├── exams/              # Modules 4–6 — scheduling, delivery, proctoring, grading, analytics
│       ├── ai/                 # Modules 3 & 6 — T5 question generation, Sentence-T5 answer grading
│       ├── notifications/      # Module 9 — in-app log, email, reminders, announcements
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
| Logout | Refresh token is blacklisted (`token_blacklist`); refresh tokens rotate on every use. |
| Account recovery | Emailed reset link built from Django's token generator — single-use (tied to the password hash) and expires after `PASSWORD_RESET_TIMEOUT` (1 h). |
| Self-service limits | `role` and `email` are read-only on `/auth/me/`, so users cannot change their own role. |
| Audit trail | `AuthEvent` rows for register, login, failed login, logout, reset request and reset. |

## 4a. Examination lifecycle (Modules 4–6)

```
 Draft ──publish──► Scheduled ──(available_from)──► Active ──(available_until / close)──► Closed
   ▲                    │
   └────unpublish───────┘   (only while no student has started)
```

- **Stored vs. derived state.** `Exam.status` stores what the instructor chose (draft / published /
  closed). The API exposes `state`, derived from `status` plus the availability window, so the
  Scheduled → Active → Closed transitions need no background job.
- **Scheduling conflicts.** Publishing (or editing a published exam) is rejected with `409` when
  another published exam overlaps in time for the same cohort — the same course, or any course
  that shares enrolled students.
- **Composition.** Questions come from the instructor's bank (picked, or drawn at random by type
  and difficulty) or are written on the spot and saved to the bank. Questions can only change
  while the exam is a draft; a question used by a non-draft exam is locked.
- **Delivery.** `start` creates the attempt and returns the questions in a per-student order
  (shuffle seeded by the attempt, so a reload keeps the order). Answers are autosaved to the
  server; a reload resumes the attempt with the clock still running.
- **Server-enforced timer.** The deadline is `started_at + duration`. After it (plus a 15 s grace
  for network delay) the submit payload is ignored and only autosaved answers are graded.
  Expired attempts are also finalised automatically whenever exam lists, results or analytics
  are read, so closing the browser cannot extend an exam.
- **Question pools and shuffling.** When `questions_per_student` is set, each student receives a
  random subset of the exam's questions (all pool questions carry equal marks, so every sitting has
  the same weight). The subset and its order are fixed on the attempt (`question_order`) when it
  starts; grading and results use only those questions. MCQ options are shuffled per student too.
- **Proctoring and exam security.** The client reports tab switches (`visibilitychange`), leaving
  fullscreen (when the exam requires it) and copy/paste attempts; events are stored as
  `ProctorEvent` rows and shown per student. Reaching `max_violations` submits the exam
  automatically (`submit_reason = violations`). Each `start` issues a new `session_key` that the
  browser must send as `X-Exam-Session`; a second tab or device therefore takes over the attempt,
  the first is locked out, and the switch is logged as a `new_session` event. The client also
  disables the context menu and text selection outside answer boxes.
- **Grading.** MCQ / true-false by answer key; short answers by similarity to the reference
  answer (see §4b). The result includes question-level feedback, the similarity score for short
  answers, and the class average. Correct answers are revealed only once the exam is closed
  **and** no student is still within their time limit. Submitted attempts are immutable, and
  every grading operation is written to `logs/audit.log`.
- **Analytics.** Per exam: score distribution (10 % bands), per-question difficulty index
  (% of students correct), full result sheet with tab-switch counts, and CSV export.
  Per student: a performance timeline across all of the instructor's exams, against the class
  average.

## 4b. AI layer (Modules 3 & 6)

All inference runs **server-side** inside the Django process (`src/services/ai/engine.py`); no
model endpoint is exposed to clients. Models are loaded lazily, once per process, on CPU
(`python manage.py ai_warmup` pre-loads them).

| Task | Model | How it is used |
|------|-------|----------------|
| Question generation | `valhalla/t5-small-qa-qg-hl` (T5 fine-tuned for answer-aware question generation) | `extract answers:` picks an answer span per sentence; `generate question:` writes a question for the highlighted answer |
| Short-answer grading | `sentence-transformers/sentence-t5-base` (Sentence-T5 encoder) | cosine similarity between the reference and the student's answer |

**Generation pipeline** (`ai/generation.py`): split the source text (pasted, or extracted from a
PDF/TXT/DOCX/PPTX course material) into sentences → extract an answer per sentence → T5 writes
the question → build the requested type: short answer; **MCQ** with distractors taken from the
other answers in the text (same kind — numbers with numbers, names with names); **true/false**
as the original sentence or the sentence with its answer swapped for a distractor. Generation is
**asynchronous**: `POST /api/ai/jobs/` returns `202` at once and a background thread fills the
`GenerationJob`; the React page polls it, and a notification is sent when it finishes. The
instructor reviews, edits and selects candidates; `commit` validates each through the normal
`QuestionSerializer` and saves it with `is_ai_generated = true`.

**Short-answer grading** (`engine.answer_similarity`):

| Reference answer | Method |
|------------------|--------|
| identical after normalising case, punctuation, spaces and articles | exact → full marks |
| 1–3 words (names, terms, numbers) | spelling-tolerant character match; numbers must match exactly |
| longer, descriptive | Sentence-T5 cosine similarity, scaled down for answers much shorter than the reference |

Score ≥ `SHORT_ANSWER_THRESHOLD` (0.86) earns full marks; ≥ `SHORT_ANSWER_PARTIAL_THRESHOLD`
(0.80) earns half marks. A question may list **required keywords** (`"last in first out | LIFO,
stack"`): an answer missing some earns at most half marks and one missing all earns none — the
safeguard against answers that sound right but say the opposite. Judged scores inside the review
band (0.78–0.92), and answers the model liked but that miss keywords, are flagged `needs_review`;
the instructor's **review queue** confirms or changes the marks, and that override (who, when,
before/after, note) is the only sanctioned change to a submitted result. The thresholds were calibrated on paraphrased, wrong and vague answers.
Short factual answers are not graded by embeddings because embeddings rate different words of
the same kind (e.g. two city names) as similar. A known limitation of any sentence-embedding
model is that an answer stating the opposite in similar words ("first in first out" for "last in
first out") can still score high.

**More AI features.** The generator offers two models — *fast* (`t5-small-qa-qg-hl`) and *better*
(`t5-base-qa-qg-hl`). Difficulty can be set automatically by a Bloom's-taxonomy classifier that
matches the question's action verb against the verb lists of the six cognitive levels
(`questionbank/bloom.py`). Generated questions that repeat one already in the bank are flagged,
and the bank has a *duplicate finder* and an as-you-type *similar question* warning — all using
cached Sentence-T5 embeddings of the bank's questions. Students can generate **practice tests**
from their course material with the same pipeline; answers are checked instantly and never count
towards results.

**Fallback.** If `torch`/`transformers` are not installed, a model cannot be downloaded, or
`AI_ENGINE=rule`, the same pipeline runs with heuristic answer selection, fill-in-the-blank
questions and lexical similarity, so the system keeps working without the models.

## 4c. Notifications (Module 9)

`notifications.services.notify()` is the single entry point used by all modules: it writes the
in-app `Notification` log and, for important events, sends the same message by email
(`NOTIFICATION_EMAILS`). Events:

| Recipient | Event | Email |
|-----------|-------|-------|
| Students | exam published, reminder before it opens (`EXAM_REMINDER_MINUTES`, default 24 h and 1 h), result published, answer key released, instructor announcement | yes (except answer key) |
| Instructor | exam results computed (on close / when the window ends), CSV import finished, AI generation finished | in-app |
| Any user | welcome, password changed (security alert) | password change only |

Time-based notifications (reminders, results-ready) are sent by `dispatch_scheduled()`, which is
**idempotent** through a per-user `dedupe_key`. It runs from `python manage.py
send_notifications` (schedule it with cron / Windows Task Scheduler) and also, throttled to once
a minute, whenever a signed-in browser polls `unread_count` — so it works with no extra process.
The React bell polls every 30 s and shows unread notifications without a page reload.

## 4d. Security hardening

| Threat | Control |
|--------|---------|
| Password guessing | Per-IP throttling on login / register / password reset; account locked for 15 min after 5 failed logins (computed from the `AuthEvent` audit trail), with an email alert |
| Answer sharing | Question pools, per-student question and option order, answer key hidden until everyone has finished |
| Second device / helper | One active session per attempt (`X-Exam-Session`), takeover logged |
| Leaving the exam | Tab-switch and fullscreen-exit detection, configurable auto-submit |
| Timer tampering | Server-side deadline; late payloads ignored |
| Production | `DEBUG=False` enables secure headers; `HTTPS=True` adds HSTS, secure cookies and HTTPS redirects; Waitress serves the app (`manage.py serve`), WhiteNoise serves static files |

## 4e. Performance

SQLite runs in WAL mode with `IMMEDIATE` transactions and a 20 s lock timeout; autosave writes all
answers in one transaction with bulk inserts/updates. A load test with 100 and 200 students
starting, autosaving and submitting at the same instant completed with **zero errors** at about 20
requests per second (`docs/testing/load-test.md`).

## 5. Frontend structure

```
client/src/
├── api/client.js               # axios instance + JWT request/refresh interceptors
├── context/AuthContext.jsx     # login / register / logout / current user
├── components/                 # ProtectedRoute, Layout, NotificationBell, QuestionFormModal,
│                               # ResultDetail, StudentTimeline
├── utils/format.js             # date/countdown formatting, error text, authenticated downloads
└── pages/                      # Login, Register, Forgot/ResetPassword, dashboards, Courses,
                                # QuestionBank, AIGenerate, Instructor/Student Exams, Results,
                                # Materials, Notifications
```

**Design system.** `index.css` defines colour, radius and shadow tokens for a light theme and a
dark theme (`<html data-theme>`, toggled in the top bar and remembered per browser). Shared
components (`components/ui.jsx`) provide page headers, stat cards, empty states, alerts, tabs,
skeleton loaders and a score ring; `ToastContext` shows transient messages; `utils/charts.js`
themes Chart.js. Pages are lazy-loaded. The exam runs in a focused full-window mode with a question
navigator, flag-for-review, one-question or all-questions view and keyboard shortcuts. The layout
is responsive down to phone width (the sidebar becomes a drawer).

Routing (`react-router-dom`) guards every private route with `ProtectedRoute`, which redirects
unauthenticated users to `/login` and role-mismatched users to their own dashboard. Analytics
use **Chart.js** via `react-chartjs-2`.

## 6. Configuration & environments

Config is loaded from `server/.env` via `django-environ` (see `.env.example`). The database is
**SQLite** (`server/db.sqlite3`) in every environment — it ships with Python, needs no external
server, and keeps development and deployment identical with zero database setup.

## 7. Scope status

All nine modules in the scope document are implemented. Items outside the scope (native mobile
apps, video proctoring, LMS integration, offline exams, multi-tenancy) are deliberately not built
— see §6.2 of the scope document.
