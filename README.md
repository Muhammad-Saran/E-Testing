# e-Testing Service

A web-based academic examination platform — Final Year Project, BS Computer Science,
COMSATS University Islamabad, Abbottabad Campus (2022–2026).

**Stack:** Django + Django REST Framework (backend) · React + Vite (frontend) · SQLite ·
JWT auth (bcrypt hashing) · Chart.js · T5 Transformer (Hugging Face) for AI question generation
and semantic short-answer grading.

## Repository layout

| Path | Contents |
|------|----------|
| `server/` | Django REST API. Modular apps under `src/services/*` + shared `src/core/`. |
| `client/` | React (Vite) single-page app. |
| `docs/`   | Scope document, system architecture, database schema, mockups. |

## Highlights

- **AI throughout** — T5 question generation (fast/better models, Bloom-level classifier,
  duplicate flags), Sentence-T5 semantic grading with required keywords and an instructor review
  queue, and AI practice tests for students.
- **Secure exams** — question pools (each student gets a different subset), shuffled questions and
  options, server-enforced timer, fullscreen mode, tab-switch / copy-paste detection with
  auto-submit at a violation limit, one active device per attempt, login lockout.
- **Analytics** — score distribution, item analysis (difficulty, discrimination, distractors),
  course trends, at-risk students, per-student timelines, CSV and printable reports.
- **Modern UI** — redesigned React interface with light/dark themes, responsive layout, focused
  exam mode with a question navigator and keyboard shortcuts.

## Modules (scope document)

| # | Module | Status |
|---|--------|------------------------|
| 1 | **User Authentication & Authorization** | Done — JWT, bcrypt, RBAC, domain-gated registration, logout token blacklisting, password reset by email, auth audit log |
| 2 | **Question Bank Management** | Done — CRUD UI, search/filter, CSV import (MCQ / T-F / short answer), versioning, locking of questions used in published exams |
| 3 | **AI-Based Question Generation (T5)** | Done — T5 generates MCQ / true-false / short-answer questions from pasted text or uploaded material (PDF/TXT/DOCX/PPTX) in a background job; instructor reviews, edits and saves them to the bank |
| 4 | **Examination Scheduling & Configuration** | Done — Draft → Scheduled → Active → Closed, pick/random questions from the bank, cohort schedule-conflict check |
| 5 | **Examination Delivery & Proctoring** | Done — server-enforced timer, autosave, auto-submit on expiry, resume after reload, per-student shuffle, tab-switch logging |
| 6 | **Automated Grading & Results** | Done — answer-key grading, Sentence-T5 semantic grading of short answers with full / half / zero marks, question-level feedback, class average, immutable results, grading audit log |
| 7 | **Student Dashboard & Course Material** | Done — upcoming exams with countdowns, recent results, result history chart, material download |
| 8 | **Instructor Dashboard & Analytics** | Done — score distribution, per-question difficulty index, filterable result sheet, CSV export, per-student performance timeline, material upload |
| 9 | **Notification & Communication** | Done — in-app notification log with polling bell, emails for exam scheduling / reminders / results / account alerts, instructor announcements, results-ready and import / AI-complete alerts |

## Getting started

Django serves the built React app, so once it is set up **one command runs the whole project**
at <http://127.0.0.1:8000>. First-time setup takes about 10 minutes (plus the AI model download).

### 1. Install these first

| Tool | Version | Needed for |
|------|---------|------------|
| [Python](https://www.python.org/downloads/) | **3.12 or newer** (tested on 3.14) | the backend — tick *"Add python.exe to PATH"* when installing on Windows |
| [Node.js](https://nodejs.org/) | **18 or newer** (tested on 24 LTS) | building the React frontend |
| [Git](https://git-scm.com/downloads) | any | getting the code |
| Google Chrome | any | only for the end-to-end tests |

About 3 GB of free disk space is needed if you install the AI models (step 5).

### 2. Get the code

```bash
git clone https://github.com/Muhammad-Saran/E-Testing.git
cd E-Testing
```

### 3. Build the frontend (once)

```bash
cd client
npm install
npm run build
cd ..
```

This creates `client/dist`, which Django serves. Run `npm run build` again whenever you change
React code.

### 4. Set up the backend

**Windows (PowerShell):**

```powershell
cd server
python -m venv ..\.venv
..\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process Bypass
python -m pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
```

**macOS / Linux:**

```bash
cd server
python3 -m venv ../.venv
source ../.venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
```

`server/.env` holds the settings (all optional). Two you may want to change straight away:

- `INSTITUTION_EMAIL_DOMAIN=cuiatd.edu.pk` — only emails on this domain can register. Leave it
  empty to allow any email while testing.
- `TIME_ZONE=Asia/Karachi` — used for exam times in emails and exports.

### 5. Install the AI models (recommended)

The app works without this step, using a simpler rule-based engine. To use the real T5 models for
question generation and short-answer grading (no API key or account needed — they run on your
own CPU):

```bash
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-ai.txt
python manage.py ai_warmup --better    # downloads the models once (~2 GB) and checks they load
```

Models are cached in your user folder (`.cache/huggingface`), so this is a one-time download. Do
**not** install `sentence-transformers`: it is not needed, and on some Windows machines its
dependencies are blocked by Windows security.

### 6. Add accounts

Either load the demo data (best for trying the system or presenting it):

```bash
python manage.py seed_demo           # instructor, 24 students, 2 courses, 28 questions, 7 exams with results
```

…or create your own: register at <http://127.0.0.1:8000/register>, and optionally create an admin
for the Django admin panel with `python manage.py createsuperuser`.

### 7. Run it

```bash
python manage.py runserver
```

Open **<http://127.0.0.1:8000>**. With demo data, sign in with:

| Role | Email | Password |
|------|-------|----------|
| Instructor | `instructor@demo.edu` | `Demo@12345` |
| Student | `student@demo.edu` | `Demo@12345` |
| Admin (Django admin at `/admin/`) | `admin@demo.edu` | `Demo@12345` |

The login page also has one-click demo buttons. The demo student has past results and one exam
that is open right now, so you can take an exam live. Remove the demo data any time with
`python manage.py seed_demo --remove` (it only deletes `@demo.edu` accounts and their data).

### Running it again later

```bash
cd server
..\.venv\Scripts\Activate.ps1          # macOS/Linux: source ../.venv/bin/activate
python manage.py runserver
```

After pulling new code, also run `python manage.py migrate` (backend) and `npm run build` in
`client/` (frontend).

### Troubleshooting

| Problem | Fix |
|---------|-----|
| Browser shows `{"error": "Frontend not built yet."}` | Run `npm install` and `npm run build` in `client/` |
| `pip` is not recognised / blocked | Use `python -m pip …` (on Windows also `py -m pip …`) |
| PowerShell refuses to run `Activate.ps1` | Run `Set-ExecutionPolicy -Scope Process Bypass` in that window first |
| Registration says the email domain is not allowed | Empty `INSTITUTION_EMAIL_DOMAIN` in `server/.env`, or use an institutional email |
| `That port is already in use` | `python manage.py runserver 8001` and open port 8001 |
| The first AI request takes 10–20 seconds | Normal — the model is loading into memory. Later requests are fast. `python manage.py ai_warmup` loads them in advance |
| No internet during a presentation | Add `HF_HUB_OFFLINE=1` to `server/.env` so the downloaded models load straight from the cache |
| Emails do not arrive | By default emails are only printed in the `runserver` terminal. For real mail set the Gmail block in `server/.env`, then test with `python manage.py send_test_email you@example.com` |
| "Account locked" after wrong passwords | Wait 15 minutes, or use *Forgot password* |
| Login page shows no demo buttons | Demo data is not loaded — run `python manage.py seed_demo` |

## More ways to run it

### Production server

```bash
python manage.py serve --port 8000   # Waitress (multi-threaded), collects static files first
```

Set `DEBUG=False`, `ALLOWED_HOSTS` and, behind HTTPS, `HTTPS=True` + `CSRF_TRUSTED_ORIGINS` in
`server/.env`. `runserver` is for development only.

### Scheduled notifications (Module 9)

Exam reminders and "results ready" alerts are sent automatically while anyone is using the app.
To send them even when nobody is signed in, schedule this every 5 minutes (cron or Windows Task
Scheduler):

```bash
cd server && python manage.py send_notifications
```

### Live frontend editing (hot reload)

While changing React code you can run the Vite dev server instead of rebuilding each time. Set
`VITE_API_URL=http://127.0.0.1:8000/api` in `client/.env`, keep `runserver` running, and in a
second terminal:

```bash
cd client
npm run dev                       # http://127.0.0.1:5173 (auto-reloads on save)
```

## Tests

```bash
cd server && python manage.py test src     # 85 backend tests (API, grading, security, AI, notifications)
cd client && npm test                      # Vitest unit/component tests
cd client && npm run e2e                   # Playwright end-to-end tests in Chrome (seeds a temporary DB)
```

A concurrency load test (100–200 simultaneous students, zero errors) is described with its
results in [docs/testing/load-test.md](docs/testing/load-test.md).

## API endpoints

```
# Auth (Module 1)
POST   /api/auth/register/                  Register an instructor or student
POST   /api/auth/login/                     Obtain JWT access + refresh tokens
POST   /api/auth/refresh/                   Refresh an access token (rotates the refresh token)
POST   /api/auth/logout/                    Blacklist the refresh token  {refresh}
GET    /api/auth/me/  PATCH                 Current user profile (role/email read-only)
POST   /api/auth/password-reset/            Email a single-use reset link  {email}
POST   /api/auth/password-reset/confirm/    Set a new password  {uid, token, password, password_confirm}
POST   /api/auth/change-password/           {current_password, new_password, new_password_confirm}
       (login is rate-limited per IP and locks an account for 15 min after 5 failures)

# Question bank (Module 2, instructor)
CRUD   /api/questions/                      ?search= &question_type= &difficulty= &course=
GET    /api/questions/stats/
POST   /api/questions/similar/              {text, exclude?} -> near-duplicates while writing
GET    /api/questions/duplicates/           near-identical pairs across the bank
POST   /api/questions/suggest_difficulty/   {text} -> Bloom level from the action verbs
POST   /api/questions/import_csv/           multipart "file"

# Courses & material (Module 7)
CRUD   /api/courses/                        + /<id>/roster/ /<id>/enroll/ /<id>/unenroll/
POST   /api/courses/<id>/enroll_csv/        multipart "file" (+ create_missing) -> bulk enrollment
GET    /api/courses/enrollments/            read-only
CRUD   /api/courses/materials/              + /<id>/download/

# Exams — instructor (Modules 4 & 8)
CRUD   /api/exams/
GET    /api/exams/<id>/questions/           POST /add_question/ /add_from_bank/ /compose/ /remove_question/
POST   /api/exams/<id>/publish/  /unpublish/  /close/
GET    /api/exams/<id>/analytics/           item analysis (difficulty, discrimination, distractors)
GET    /api/exams/<id>/export/              CSV result sheet
GET    /api/exams/<id>/reviews/             short answers flagged for review (?all=1 for all)
POST   /api/exams/<id>/review/              {answer_id, awarded_marks, note} -> audited mark change
GET    /api/exams/course_analytics/?course= course trend, top and at-risk students

# Exams — student (Modules 5 & 6)
GET    /api/exams/available/
POST   /api/exams/<id>/start/  /save/  /proctor-event/  /submit/
       (start returns a session_key; save/proctor-event/submit must send it as X-Exam-Session)
GET    /api/exams/<id>/result/              GET /api/exams/results/

GET    /api/exams/students/                 Students in the instructor's courses
GET    /api/exams/student_timeline/?student=<id>[&course=<id>]   Per-student performance timeline

# AI question generation (Module 3, instructor)
POST   /api/ai/jobs/                        {source_text | material, question_type, count, difficulty, course?} -> 202
GET    /api/ai/jobs/  /api/ai/jobs/<id>/    Poll a job; candidates appear when status = done
POST   /api/ai/jobs/<id>/commit/            {questions: [...]} -> saved to the bank (is_ai_generated)
GET    /api/ai/jobs/status/                 Which engine / models are in use
CRUD   /api/ai/practice/                    Student practice tests  + POST /<id>/check/

# Notifications (Module 9)
GET    /api/notifications/                  ?is_read=false
GET    /api/notifications/unread_count/     Polled by the bell (also dispatches due reminders)
POST   /api/notifications/<id>/read/  /mark_all_read/     DELETE /api/notifications/<id>/
POST   /api/notifications/announce/         Instructor -> course students  {course, title, message, email}

GET    /api/dashboard/summary/              Role-aware dashboard
GET    /api/health/                         Liveness probe
```

## Database

The project uses **SQLite** (`server/db.sqlite3`) in all environments — zero setup, ships with
Python. See [docs/database/schema.md](docs/database/schema.md) for the full schema and
[docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) for the
system design.
