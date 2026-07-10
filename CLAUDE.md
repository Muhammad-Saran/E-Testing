# Claude / AI context — e-Testing Service

## One-line summary
Web-based examination platform (FYP). **Django + DRF** backend under `server/`, **React (Vite)**
frontend under `client/`, **SQLite** database. Auth is **JWT** (simplejwt) with **bcrypt**
password hashing. See `AGENTS.md` for the full map and `docs/` for scope + design.

## Start here
- `AGENTS.md` — repository map, commands, conventions.
- `docs/E-Testing Services.docx` — the graded scope document (source of truth for requirements).
- `docs/architecture/system-architecture.md` — architecture.
- `docs/database/schema.md` — database design.

## Non-negotiables
- Backend package is `config` (settings/urls/wsgi); apps live under `src/services/*` + `src/core/`.
- Custom user: `accounts.User`, email login, single `role` field (`instructor` | `student`).
- Config from `server/.env` via django-environ. Never commit real secrets; use `.env.example`.
- Database is **SQLite** everywhere (`server/db.sqlite3`).
- The scope doc has been updated to describe the **Django/DRF + SQLite** stack (it originally said
  Node.js/MySQL). Keep any future doc/code edits consistent with this stack.

## Running the project
Django serves the **built** React app, so `runserver` shows the whole UI at `:8000` (bwell-style,
one command). Config: `config/urls.py` has a SPA catch-all serving `client/dist/index.html` +
an `/assets/` route; `FRONTEND_DIST` in settings points at `client/dist`.
```bash
# build the frontend (once, and after any React change)
cd client && npm run build
# run everything
cd server && python manage.py migrate && python manage.py runserver   # http://127.0.0.1:8000
```
Optional hot-reload dev: set `VITE_API_URL=http://127.0.0.1:8000/api` in `client/.env`, run
`npm run dev` (:5173) alongside `runserver`.

## Where things live (backend)
| Concern | Location |
|---------|----------|
| Settings / URLs | `server/config/settings.py`, `server/config/urls.py` |
| Shared core (base model, permissions, pagination) | `server/src/core/` |
| Auth / users (Module 1) | `server/src/services/accounts/` |
| Courses / enrollment / materials | `server/src/services/courses/` |
| Question bank (Module 2) | `server/src/services/questionbank/` |
| Dashboards (Modules 7 & 8) | `server/src/services/dashboard/` |

If anything here disagrees with the code, the code wins — update `AGENTS.md`.
