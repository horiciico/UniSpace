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
- D-014 · Parity is by week number: 0 ALL, 1 ODD, 2 EVEN
- D-015 · Imported activities are bound to a planning unit; the ETL skips manually modified rows
- D-016 · One-off changes are exceptions; permanent changes go through an admin request
- D-017 · Admin off-limits marks are stored in an off_limits table
- D-018 · Frontend unit tests use Vitest and jsdom, as dev-only tools; the app stays plain files
- D-019 · One email is one professor; the stored id is kept when the API changes it
- D-020 · Role on every sign-in: professor list, then university address, otherwise rejected
- D-021 · The admin signs in with one .env credential pair; the session is the same as Google's
- D-022 · A student chooses a faculty and a study formation on first sign-in

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
- **Evidence:** frontend/pages/shared/index.html, docker-compose.yml (service `frontend`)
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
- **Rule:** nginx serves a frontend page only after `auth_request` to the backend (`/auth/me`; `/auth/admin` for `/admin/`) succeeds. Signed out goes to `/login`; a non-admin on `/admin/` goes to `/`. Public: `/login`, `/styles/`, `/components/`, `/js/`, `/i18n/`, `/health`, `/auth/`. Client scripts never decide access.
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
- **Evidence:** frontend/i18n/i18n.js, frontend/i18n/ro.js, frontend/i18n/en.js, frontend/components/app.js, frontend/components/header.js, backend/tests/test_i18n.py
- **Source:** user · confidence high
- **Confirmed:** 2026-11-17

## D-012 · Records from the backend are shown as they arrive, not translated in the frontend
- **Status:** approved
- **Date:** 2026-11-17
- **Rule:** Courses, rooms, teachers, times of real classes and other records that come from the backend are displayed as received. They are not put in the dictionaries. Labels the frontend defines (headings, buttons, fields, notices, status words such as Free or Cancelled, weekday names, role names) are translated. Sample rows in the placeholder pages are data and stay as they are.
- **Why:** The user decided this: the data changes with the backend, so a copy in the frontend would go stale.
- **Rejected:** translating course and room names in the frontend
- **Evidence:** frontend/pages/student/timetable.html, frontend/js/pages/timetable.js, frontend/pages/student/rooms/index.html
- **Source:** user · confidence high
- **Confirmed:** 2026-11-17

## D-014 · Parity is by week number: 0 ALL, 1 ODD, 2 EVEN
- **Status:** approved
- **Date:** 2026-11-19
- **Rule:** A recurring activity runs in every week (`ALL`, API value 0), only in odd-numbered weeks (`ODD`, API value 1), or only in even-numbered weeks (`EVEN`, API value 2). Week 1 is the first week of the academic year, so it is odd. The ETL maps the API integer to the `Parity` enum (`ALL`, `ODD`, `EVEN`).
- **Why:** Courses run every second week. The user defined the mapping.
- **Rejected:** none stated
- **Evidence:** backend/app/models/enums.py:Parity, docs/agents/OPEN-QUESTIONS.md (Q-013)
- **Source:** user · confidence high
- **Confirmed:** 2026-11-19

## D-015 · Imported activities are bound to a planning unit; the ETL skips manually modified rows
- **Status:** approved
- **Date:** 2026-11-19
- **Rule:** Each imported activity links to its planning time unit (`planning_time_unit_id`) and has an `external_id` that is unique within that unit. The ETL updates rows with `is_manually_modified = false` and skips rows with `is_manually_modified = true`. Student bookings are not activities: they live in the `bookings` table, which has no `external_id` and no planning unit (step 1 of the room booking feature).
- **Why:** The ETL can re-run without duplicates, and admin edits are not overwritten.
- **Rejected:** none stated
- **Evidence:** backend/app/models/activity.py (planned columns), docs/agents/OPEN-QUESTIONS.md (Q-013)
- **Source:** user · confidence high
- **Confirmed:** 2026-11-24

## D-016 · One-off changes are exceptions; permanent changes go through an admin request
- **Status:** approved
- **Date:** 2026-11-19
- **Rule:** A professor can move or cancel one occurrence of a course. That is an `activity_exceptions` row (renamed from `event_exceptions`). A permanent change is a `rule_change_requests` row; an admin reviews it and applies it, which sets `is_manually_modified = true` on the activity.
- **Why:** The user decided professors change single occurrences themselves, and permanent changes need an admin.
- **Rejected:** none stated
- **Evidence:** docs/agents/OPEN-QUESTIONS.md (Q-012)
- **Source:** user · confidence high
- **Confirmed:** 2026-11-19

## D-017 · Admin off-limits marks are stored in an off_limits table
- **Status:** approved
- **Date:** 2026-11-19
- **Rule:** An admin can mark one or more days as off limits, for the whole period or a set period. An admin can mark a room as off limits for one or more days, or for a time window within a day. These marks live in an `off_limits` table. The scope of a day mark (whole university or one faculty) is open in Q-014.
- **Why:** The user described these rules. A table keeps the marks separate from the imported schedule.
- **Rejected:** none stated
- **Evidence:** docs/agents/OPEN-QUESTIONS.md (Q-010, Q-014)
- **Source:** user · confidence high
- **Confirmed:** 2026-11-19

## D-018 · Frontend unit tests use Vitest and jsdom, as dev-only tools; the app stays plain files
- **Status:** approved
- **Date:** 2026-11-23
- **Rule:** The frontend stays plain HTML, CSS and JavaScript with no framework and no bundler (D-003). Its unit tests use Vitest (the test runner of the Vite family) with jsdom. Both are devDependencies in `frontend/package.json`, run only in the `frontend-test` compose service (profile `test`), and are never loaded by a page. nginx serves the same files as before.
- **Why:** The user asked for unit tests with full coverage of the browser scripts, using Vite. Vitest is Vite's own test runner, so no bundler is added to the app.
- **Rejected:** a bundler or framework for the app; a browser-only test run without a DOM library.
- **Evidence:** frontend/package.json, frontend/vitest.config.js, frontend/tests/, docker-compose.yml (service `frontend-test`), docs/agents/ARCHITECTURE.md (Unit tests)
- **Source:** user · confidence high
- **Confirmed:** 2026-11-23

## D-019 · One email is one professor; the stored id is kept when the API changes it
- **Status:** approved
- **Date:** 2026-11-23
- **Rule:** A professor is identified by the normalized email (stripped, lower-case). Records that share an email are one professor. The kept id is the id already stored for that email, else an id used by an activity, else the smallest id. Each other id is left out and logged as a warning. If the API drops the stored id and gives the same email a new id, the stored row takes the new id, and the users and activities that pointed at the old id are moved to the new one. This happens on full runs only (all faculties, every file readable); a partial run reports the refusal instead.
- **Why:** The ULBS system holds duplicate records for one person. `professors.email` must stay unique, and login matches on it, so one person cannot have two rows.
- **Rejected:** storing both ids (the email must be unique); deleting the stored row when the id changes (the professors pipeline never deletes rows).
- **Evidence:** etl/professors/load.py (merge_records, plan_rekeys, rekey_professor), docs/agents/OPEN-QUESTIONS.md (Q-016), etl/professors/tests/
- **Source:** user (answered Q-016 and approved this decision, 2026-11-23) · confidence high
- **Confirmed:** 2026-11-23

## D-020 · Role on every sign-in: professor list, then university address, otherwise rejected
- **Status:** approved
- **Date:** 2026-11-23
- **Rule:** On every Google sign-in the email is normalized (stripped, lower-case) and the role is resolved in this order:
  1. the email is in `professors` → PROFESSOR, on any domain; `users.professor_id` is set to the professor's id;
  2. `is_student_association(email)` is true → STUDENT_ORG (a placeholder hook that returns False until student associations are identified);
  3. the email ends with `@ulbsibiu.ro` and the Google `hd` claim agrees → STUDENT; a former professor who is no longer in `professors` goes back to STUDENT;
  4. anything else → 403. This includes a former professor who signs in from an external address.
  A login never lowers an existing ADMIN or STUDENT_ORG. Invitations are no longer used for sign-in (the `invitations` table is no longer read).
- **Why:** The user decided this on 2026-11-23. Registered professors may sign in from any address; university addresses are students; everyone else is kept out.
- **Rejected:** invitations for external accounts (the professor list replaces them); lowercase role names (the enum values are used).
- **Evidence:** backend/app/auth.py (resolve_user, decide_role, is_student_association), backend/tests/test_auth.py, docs/agents/CONTRACTS.md (C-002)
- **Source:** user (answers 1-4 and the proposal, 2026-11-23) · confidence high
- **Confirmed:** 2026-11-23

## D-021 · The admin signs in with one .env credential pair; the session is the same as Google's
- **Status:** approved
- **Date:** 2026-11-23
- **Rule:** `POST /auth/admin-login` takes `username` and `password` and compares both with `ADMIN_USERNAME` and `ADMIN_PASSWORD` from `.env` using `secrets.compare_digest`. The values are plain text in `.env` for now. If either is empty, the admin login is off and always answers 401. On success the backend creates or updates the `users` row whose email is `ADMIN_USERNAME` (lower-case), with role ADMIN, and issues the usual session cookie (D-009). A wrong username or password answers 401 with the same message. The route is under `/auth/`, outside the `/api/` gate.
- **Why:** The admin needs a sign-in that does not use Google. The user chose a plain-text password in `.env` for now; a stored hash is a possible later change (it would be a PROPOSAL).
- **Rejected:** credentials hard-coded in the source (AGENTS.md forbids secrets in files); `/api/auth/admin-login` (nginx would refuse it to a signed-out admin); a role field in the session cookie (changes D-009).
- **Evidence:** backend/app/routers/auth.py (admin_login), backend/app/config.py, .env.example, infra/nginx/default.conf (`location /auth/`)
- **Source:** user (chose option a and plain text, 2026-11-23) · confidence high
- **Confirmed:** 2026-11-23

## D-022 · A student chooses a faculty and a study formation on first sign-in
- **Status:** approved
- **Date:** 2026-11-23
- **Rule:** On sign-in, a STUDENT whose `users.faculty_id` is empty is asked for a faculty, then for one of that faculty's study formations, in a dialog that cannot be closed. Both are saved on the user row: `faculty_id` (FK to `faculties`) and `study_formation_id` (FK to `student_groups`, ON DELETE SET NULL). Both are nullable and filled only for students. The formation must be one of the faculty's formations (the list of `GET /api/groups?faculty_id=`). Other roles are not asked.
- **Why:** The ULBS data gives no student emails, so a course change cannot be sent to students directly. The faculty and formation on record are what the warnings will be based on. (user request, 2026-11-23)
- **Rejected:** a single column for the formation only (a formation can appear under more than one faculty in the data, so the faculty would be a guess); a dialog the student can skip; a new `student_groups.faculty_id` column (a schema and loader change for a list the existing lookup already gives).
- **Evidence:** backend/alembic/versions/20261123_b0f9c8035187_user_study_profile_faculty_and_formation.py, backend/app/models/user.py (needs_onboarding), backend/app/routers/study_profile.py, backend/app/routers/lookups.py (faculty_groups), frontend/components/onboarding.js
- **Source:** user (request and answers, 2026-11-23) · confidence high
- **Confirmed:** 2026-11-23
