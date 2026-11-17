# Decisions — UniSpace

<!-- graffino-agentic:begin v1 -->
> Constraints the code must obey. Status: `approved` (obey) · `proposed` (do not
> build on it) · `superseded-by <ID>` (kept to explain old code).
> Adding or changing an entry needs the user's OK (AGENTS.md → The gate).
<!-- graffino-agentic:end -->

## Index
- D-001 · Backend is Python 3.12 with FastAPI
- D-002 · Database is PostgreSQL; schema changes go through Alembic migrations
- D-003 · Frontend is plain HTML, CSS and JavaScript
- D-004 · The local stack runs in Docker Compose
- D-005 · Configuration comes from the environment; .env is never committed
- D-006 · Primary keys are UUIDs; enums are native PostgreSQL enums
- D-007 · Booking priority scale is 1 to 5
- D-008 · day_of_week is an integer 1 to 7, Monday = 1
- D-009 · Login is a signed HttpOnly session cookie, 8 hours · _proposed_
- D-010 · Pages are gated by nginx, not by JavaScript · _proposed_
- D-011 · The interface is in Romanian and English, from one dictionary per language
- D-012 · Records from the backend are shown as they arrive, not translated in the frontend

---

## D-001 · Backend is Python 3.12 with FastAPI
- **Status:** approved
- **Date:** 2026-11-11
- **Rule:** The backend is a FastAPI application in `backend/app/`. HTTP endpoints are FastAPI routes.
- **Why:** The user chose Python with FastAPI for the backend.
- **Rejected:** none stated
- **Evidence:** backend/app/main.py:5, backend/requirements.txt
- **Source:** user · confidence high
- **Confirmed:** 2026-11-12

## D-002 · Database is PostgreSQL; schema changes go through Alembic migrations
- **Status:** approved
- **Date:** 2026-11-11
- **Rule:** The database is PostgreSQL. Every schema change is an Alembic revision in `backend/alembic/versions/`. The app never creates tables at runtime.
- **Why:** The user chose PostgreSQL with Alembic. Revisions keep schema changes reviewable and reproducible.
- **Rejected:** none stated
- **Evidence:** backend/alembic.ini, backend/alembic/env.py, backend/app/db.py:9
- **Source:** user · confidence high
- **Confirmed:** 2026-11-12

## D-003 · Frontend is plain HTML, CSS and JavaScript
- **Status:** approved
- **Date:** 2026-11-11
- **Rule:** The frontend is static HTML, CSS and JS in `frontend/`, served by nginx.
- **Why:** The user chose the usual HTML, CSS and JS for the frontend.
- **Rejected:** none stated
- **Evidence:** frontend/index.html, docker-compose.yml (service `frontend`)
- **Source:** user · confidence medium
- **Owner note:** The user named no framework or bundler, so this entry assumes none. Confirm, or name the tool to add.

## D-004 · The local stack runs in Docker Compose
- **Status:** approved
- **Date:** 2026-11-11
- **Rule:** The database, backend and frontend run as containers defined in `docker-compose.yml`. The backend image is built from `backend/Dockerfile`.
- **Why:** The user asked for containerization with Docker Compose.
- **Rejected:** none stated
- **Evidence:** docker-compose.yml, backend/Dockerfile
- **Source:** user · confidence high
- **Confirmed:** 2026-11-12

## D-005 · Configuration comes from the environment; .env is never committed
- **Status:** approved
- **Date:** 2026-11-11
- **Rule:** Settings are read from environment variables. `DATABASE_URL` is read in `backend/app/config.py`. Local values and secrets live in `.env`, which git ignores. `.env.example` lists the names.
- **Why:** Credentials must stay out of the repository. Compose reads them from `.env`.
- **Rejected:** none stated
- **Evidence:** backend/app/config.py:4, docker-compose.yml (env_file), .env.example, .gitignore
- **Source:** code · confidence high
- **Confirmed:** 2026-11-12

## D-006 · Primary keys are UUIDs; enums are native PostgreSQL enums
- **Status:** approved
- **Date:** 2026-11-12
- **Rule:** Every table has a `uuid` primary key defaulting to `gen_random_uuid()`. Enumerated columns use native PG enum types (SQLAlchemy `Enum`).
- **Why:** The user chose UUIDs so imported and booked rows cannot collide on ids.
- **Rejected:** integer keys
- **Evidence:** backend/app/models/*.py, backend/alembic/versions/20261111_84fcf3042b4d_scheduling_schema.py
- **Source:** user · confidence high
- **Confirmed:** 2026-11-12

## D-007 · Booking priority scale is 1 to 5
- **Status:** approved
- **Date:** 2026-11-12
- **Rule:** Priority is an integer 1-5; a higher number wins a bump: 5 COURSE, 4 EXAM, 3 OFFICIAL_FACULTY, 2 STUDENT_ORG, 1 STUDENT. Enforced by a CHECK on `activity.priority`; the names live in `Priority` (`backend/app/models/enums.py`).
- **Why:** The user confirmed the chain course > exam > official faculty activity > student organization > student.
- **Rejected:** the schema brief's four levels with EXAM above COURSE
- **Evidence:** backend/app/models/enums.py:Priority, backend/app/models/activity.py
- **Source:** user · confidence high
- **Confirmed:** 2026-11-12

## D-008 · day_of_week is an integer 1 to 7, Monday = 1
- **Status:** approved
- **Date:** 2026-11-12
- **Rule:** `activity.day_of_week` is a SmallInteger 1-7 (ISO, Monday = 1), enforced by a CHECK. Python's `date.weekday()` is 0-6, so use `isoweekday()`.
- **Why:** The user asked for a simple integer 1-7.
- **Rejected:** 0-6, a DB enum
- **Evidence:** backend/app/models/activity.py
- **Source:** user · confidence high
- **Confirmed:** 2026-11-12

## D-009 · Login is a signed HttpOnly session cookie, 8 hours
- **Status:** proposed
- **Date:** 2026-11-16
- **Rule:** Sign-in sets Starlette's signed session cookie (`SessionMiddleware`): HttpOnly, SameSite=Lax, 8-hour lifetime, Secure when `COOKIE_SECURE=true`. No JWT for now. The cookie holds `user_id` only.
- **Why:** Authlib needs the session cookie for the OAuth state anyway; one mechanism, no extra library. The user said a separate JWT is "not yet".
- **Rejected:** a separate JWT cookie (for now)
- **Evidence:** backend/app/main.py, backend/app/auth.py:start_session
- **Source:** user (cookie flags, lifetime proposed by the agent) · confidence medium

## D-010 · Pages are gated by nginx, not by JavaScript
- **Status:** proposed
- **Date:** 2026-11-16
- **Rule:** nginx serves a frontend page only after `auth_request` to the backend (`/auth/me`; `/auth/admin` for `/admin/`) succeeds. Signed out goes to `/login`; a non-admin on `/admin/` goes to `/`. Public: `/login`, `/css/`, `/js/`, `/health`, `/auth/`. Client scripts never decide access.
- **Why:** The static files are public on the server, so a script gate is only cosmetic. The user wants the app reachable only when signed in, also by typing a URL.
- **Rejected:** a JavaScript-only gate (the old localStorage dummy)
- **Evidence:** infra/nginx/default.conf, frontend/js/auth.js
- **Source:** user · confidence high

## D-011 · The interface is in Romanian and English, from one dictionary per language
- **Status:** approved
- **Date:** 2026-11-17
- **Rule:** Every text the frontend shows is in `frontend/i18n/ro.js` and `frontend/i18n/en.js` under the same key, used through `data-i18n`, `data-i18n-attr` or `UniSpaceI18n.t()`. The first visit uses the browser language if it lists Romanian or English (the first of them listed), otherwise Romanian. A choice made with the RO | EN toggle is kept in `localStorage` (`unispace-lang`) and wins over the browser. Switching does not reload the page.
- **Why:** The users are Romanian and the brief is in Romanian, and English is needed too. Keys in one place keep both languages complete.
- **Rejected:** a translation library (a dependency with no need yet); JSON fetched at run time; a reload on switch
- **Evidence:** frontend/i18n/i18n.js, frontend/i18n/ro.js, frontend/i18n/en.js, frontend/js/layout.js, backend/tests/test_i18n.py
- **Source:** user · confidence high
- **Confirmed:** 2026-11-17

## D-012 · Records from the backend are shown as they arrive, not translated in the frontend
- **Status:** approved
- **Date:** 2026-11-17
- **Rule:** Courses, rooms, teachers, times of real classes and other records that come from the backend are displayed as received. They are not put in the dictionaries. Labels the frontend defines (headings, buttons, fields, notices, status words such as Free or Cancelled, weekday names, role names) are translated. Sample rows in the placeholder pages are data and stay as they are.
- **Why:** The user decided this: the data changes with the backend, so a copy in the frontend would go stale.
- **Rejected:** translating course and room names in the frontend
- **Evidence:** frontend/timetable.html, frontend/js/timetable.js, frontend/rooms/index.html
- **Source:** user · confidence high
- **Confirmed:** 2026-11-17
