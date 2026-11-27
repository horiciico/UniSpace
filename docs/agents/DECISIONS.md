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
- D-023 · Any signed-in user can request a room; an admin's booking is approved at once
- D-024 · Admin-managed room fields are never written by the classroom ETL
- D-025 · Admins invite users by email; an invitation admits a new account; admin-set roles persist
- D-026 · A professor moves one teaching occurrence; it takes effect at once and blocks on conflicts
- D-028 · Each faculty has its own academic calendar, with all-faculties periods as the default
- D-029 · A class cannot be moved onto a holiday or into an exam session, and an approval follows the calendar
- D-030 · Exams are scheduled in half hours, only in the groups' exam session
- D-031 · An import updates and never deletes; an admin starts it from the panel

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
- **Confirmed:** 2026-11-26

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
- **Confirmed:** 2026-11-26

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
- **Confirmed:** 2026-11-26

## D-012 · Records from the backend are shown as they arrive, not translated in the frontend
- **Status:** approved
- **Date:** 2026-11-17
- **Rule:** Courses, rooms, teachers, times of real classes and other records that come from the backend are displayed as received. They are not put in the dictionaries. Labels the frontend defines (headings, buttons, fields, notices, status words such as Free or Cancelled, weekday names, role names) are translated. Sample rows in the placeholder pages are data and stay as they are.
- **Why:** The user decided this: the data changes with the backend, so a copy in the frontend would go stale.
- **Rejected:** translating course and room names in the frontend
- **Evidence:** frontend/pages/student/timetable.html, frontend/js/pages/timetable.js, frontend/pages/student/rooms/index.html
- **Source:** user · confidence high
- **Confirmed:** 2026-11-26

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
- **Superseded in part by:** D-025 (a valid invitation admits a new account; a role set by an admin is kept on sign-in).
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
- **Confirmed:** 2026-11-26

## D-023 · Any signed-in user can request a room; an admin's booking is approved at once
- **Status:** approved
- **Date:** 2026-11-24
- **Rule:** Any signed-in role (student, student organization, professor, admin) can request a room booking. A request by an ADMIN is `approved` at once. Any other role's request is `pending` until an admin approves it. Only `approved` bookings block a room; `pending` ones do not.
- **Why:** The user decided that every role books through the same flow, and that an admin's booking needs no second approval.
- **Rejected:** only students and student organizations can book (the earlier default, replaced by the user's decision)
- **Evidence:** backend/app/routers/bookings.py (create_booking), backend/tests/test_bookings_api.py
- **Source:** user · confidence high
- **Confirmed:** 2026-11-24

## D-024 · Admin-managed room fields are never written by the classroom ETL
- **Status:** approved
- **Date:** 2026-11-24
- **Rule:** The classroom loader (`upsert_classroom`) writes only `name`, `capacity` and `faculty_id` of a room. It never writes `is_bookable`, `has_projector`, `board_type`, `access_notes` or `equipment_notes`. An admin sets those through `/api/admin/classrooms` (C-007), and a rerun of the import keeps them.
- **Why:** An admin's edit must survive the next import of the schedule.
- **Rejected:** none stated
- **Evidence:** etl/schedule/loader.py (upsert_classroom), etl/schedule/tests/test_loader_db.py (test_a_rerun_keeps_the_admin_room_fields_and_updates_only_the_etl_fields), backend/app/routers/classroom_attributes.py
- **Source:** user (approved proposal P1, 2026-11-24) · code · confidence high
- **Confirmed:** 2026-11-24

## D-025 · Admins invite users by email; an invitation admits a new account; admin-set roles persist
- **Status:** approved
- **Date:** 2026-11-25
- **Rule:** An admin invites an email with a non-admin role (STUDENT, PROFESSOR, STUDENT_ORG; never ADMIN) through `user_invitations`. An invitation is pending until used, expires 48 hours after it is created, and is revoked if the admin revokes it. When an admin creates an invitation, only an expired pending invitation for the same email is revoked first; an unexpired pending invitation for that email still gives 409. At most one pending invitation per email. The invite link is `/login?invite=<token>`. The login page passes the token to `/auth/login`, which keeps it in the session; the Google callback consumes it. On a new account (no user row with that email or Google id), a pending, unexpired invitation whose token and email match the sign-in gives the invitation's role, after the professor list and before the `@ulbsibiu.ro` and 403 rules. The invitation becomes `accepted`. A role an admin sets (on the Users tab or through an invitation) is kept on every later sign-in, from any address, and a sign-in does not overwrite it (`users.role_set_by_admin`). An account whose role was set this way is not refused for its address. The invitation token is stored in plain text, so an admin can copy the link again: an accepted trade-off.
- **Why:** The user needs a way to add student organization representatives and other users outside the professor list. Admin-set roles must survive the next sign-in (D-020 would otherwise reset them). The user decided this on 2026-11-25, with the answers below the plan.
- **Rejected:** a new registration page with a password (Q-007: Google only); an invitation admitting an existing account (only new accounts); overwriting an admin-set role on sign-in.
- **Evidence:** backend/app/auth.py (resolve_user, decide_role), backend/app/invitations.py, backend/app/models/user_invitation.py, backend/alembic/versions/20261125_b7e2d4a9c013_user_invitations.py, backend/alembic/versions/20261125_c4d1e8f2a7b9_user_role_set_by_admin.py, backend/alembic/versions/20261125_d5a9f0c3b8e1_invitation_expiry_48_hours.py, backend/alembic/versions/20261125_e6b0a1d4c9f2_users_created_at.py, backend/tests/test_user_invitations.py, backend/tests/test_invitation_sign_in.py, backend/tests/test_admin_users.py
- **Source:** user (plan answers 1 to 6, 2026-11-25; wording tweaks 2026-11-25) · confidence high
- **Confirmed:** 2026-11-25

## D-026 · A professor moves one teaching occurrence; it takes effect at once and blocks on conflicts
- **Status:** approved
- **Date:** 2026-11-26
- **Rule:** A PROFESSOR linked to a `professors` row (LOWER(users.email) = LOWER(professors.email)) may move one occurrence of an activity they teach:
  1. The move takes effect at once (no admin approval). It is an `activity_exceptions` row for that occurrence (D-016).
  2. Only one occurrence (one date) moves. Permanent, semester-wide changes stay out of scope (D-016: an admin request).
  3. There is no cancel action. A moved occurrence is the new source of truth; moving it again uses the same flow on the moved occurrence.
  4. A move is allowed only to a slot where every target group and the professor are free, and where a bookable classroom is free (the availability rules of C-009).
  5. The vacated occurrence is freed at once: its classroom and time become bookable and free in the availability and free-room checks across the app (Q-017).
  6. A PROFESSOR user with no matching `professors` row has no activities and cannot move any; the app shows an empty state.
- **Why:** The user approved these rules for the professor reschedule flow (PR 1), which is also the base of Schedule Exam (PR 2). Single occurrences keep the schedule correct for one week without a permanent change.
- **Rejected:** a cancel action (a move replaces it); a permanent change from the professor's own screen (admin request, D-016); a move that needs admin approval.
- **Evidence:** backend/app/professors.py (get_professor_for_user), backend/app/routers/professors.py, backend/app/availability.py, backend/app/planning.py (occurrences), backend/tests/test_professor_timetable.py, backend/tests/test_professor_availability.py. Rules 1 to 6 are enforced by the move endpoint (C-009, backend/app/moves.py, backend/tests/test_professor_move.py). The frontend Move Activity modal is not built yet.
- **Source:** user (business rules 1 to 6, pasted spec "Business Rules (Approved)", 2026-11-26) · confidence high
- **Confirmed:** 2026-11-26

## D-028 · Each faculty has its own academic calendar, with all-faculties periods as the default
- **Status:** approved
- **Date:** 2026-11-26
- **Rule:** An `academic_periods` row belongs to one faculty (`faculty_id`) or to all faculties (`faculty_id` NULL). Periods are set by an admin, `start_date`..`end_date` inclusive, with no overlaps within the same faculty or within the all-faculties rows. For a faculty and a date the type is: the faculty's own covering period, else the all-faculties covering period, else `TEACHING`.
  - `TEACHING`: the 90-minute module grid; weekly recurring courses are active.
  - `EXAM_SESSION`: half-hour steps 08:00 to 22:00, minimum 1 hour (D-030, changed 2026-11-27 from whole hours); weekly recurring courses are suppressed.
  - `HOLIDAY`: weekly recurring courses are suppressed; new bookings are disabled.
  Which faculty counts: a weekly course follows the faculty of its planning unit; a room booking follows the room's faculty (a campus room follows the all-faculties periods); the timetable follows the room's faculty in the room view and the selected faculty in the group and professor views; in "Orarul meu" each course follows its own faculty, the banner names the affected faculties, and the grid is hourly when any of them is in an exam session. Overlap is enforced by the application helper; the database only checks `start_date <= end_date`.
- **Why:** The faculties do not have the same year structure (user, 2026-11-26).
- **Rejected:** per-faculty periods only (a shared holiday would be entered once per faculty and campus rooms would have no calendar); the booker's faculty for room bookings (one room would have different times per person); all-faculties-only banner and grid in "Orarul meu"; a database exclusion constraint.
- **Evidence:** backend/app/academic_calendar.py, backend/app/planning.py, backend/app/routers/academic_periods.py, backend/tests/test_academic_calendar_faculty.py
- **Source:** user (request, answers and plan approval, 2026-11-26) · confidence high
- **Confirmed:** 2026-11-26

## D-029 · A class cannot be moved onto a holiday or into an exam session, and an approval follows the calendar
- **Status:** approved
- **Date:** 2026-11-27
- **Rule:** A professor cannot move a class to a date that is a `HOLIDAY` or an `EXAM_SESSION` (D-028) for the faculty that teaches it or for the faculty of the new room (a campus room follows the all-faculties periods). It is judged per faculty, never for the whole university: faculties differ (two semesters with two sessions, or four modules with four). An activity of type EXAM may move within a session, not onto a holiday. The teaching faculty is the planning unit's; for a class already moved (no unit), the units of its groups' other activities. The move endpoint refuses it (400), and the availability of that date shows every module as unavailable ("Holiday." or "Exam session.") and leaves out rooms of a faculty that has no classes that day. A pending booking cannot be approved when its date has since become a holiday, or an exam session its times do not fit (400); it can still be rejected.
- **Why:** The user: a professor should not be able to move a class into a holiday, and classes cannot be moved during an exam session as there are no classes (2026-11-27). Approvals: review finding 9 on PR #37, which the user asked to address.
- **Rejected:** none stated
- **Evidence:** backend/app/moves.py, backend/app/availability.py, backend/app/academic_calendar.py, backend/app/routers/admin_bookings.py, backend/tests/test_calendar_checks.py
- **Source:** user (2026-11-27) · confidence high
- **Confirmed:** 2026-11-27
## D-030 · Exams are scheduled in half hours, only in the groups' exam session
- **Status:** approved
- **Date:** 2026-11-27
- **Rule:** In an exam session a time is on the hour or the half hour, a slot lasts at least one hour and lies between 08:00 and 22:00. The same rule covers exams and room bookings (`planning.session_window`). The timetable draws an exam-session week in whole-hour rows and offers a free slot only for a whole free hour; a half-hour time is chosen in the booking form or the exam dialog. A professor schedules an exam only for their own subject and one or more of its groups, on a date that is today or later and is an `EXAM_SESSION` for the faculty teaching every chosen group (D-028). The room's faculty need not be in a session but must not be on holiday. The professor, every group and the bookable room must be free for the whole interval (overlap). The exam is a one-off `EXAM` activity, approved at once. Outside a session, courses, moves and bookings stay on the 90-minute modules.
- **Why:** Exams are not 90-minute courses, and one grid for the whole session leaves no half-hour gaps between exams and bookings. The user decided this on 2026-11-26 and 2026-11-27 (answers on the end time, bookings and faculty).
- **Rejected:** an end time of 21:30; whole-hour room bookings beside half-hour exams; requiring the room's faculty to be in a session too.
- **Evidence:** backend/app/planning.py (session_window), backend/app/exams.py, backend/app/academic_calendar.py (all_in_exam_session), backend/tests/test_professor_exams.py, backend/tests/test_bookings_academic_periods.py
- **Source:** user (2026-11-26, 2026-11-27) · confidence high
- **Confirmed:** 2026-11-27

## D-031 · An import updates and never deletes; an admin starts it from the panel
- **Status:** approved
- **Date:** 2026-11-27
- **Rule:** The schedule and professors pipelines delete nothing, from the command line or the panel. An imported weekly class of the loaded planning unit that is no longer in the feed is set `CANCELLED` (also when a move or a change request points at it) and set `APPROVED` again if it returns; a file with no class to store cancels nothing. Admin-edited classes, admin room fields (D-024), bookings, moves and exams are not written. An admin starts both pipelines, schedule then professors, for all faculties from the admin panel; the backend runs them in the background, one run at a time, loading only the files downloaded in that run. The professor load counts as full only when every faculty's file arrived. Afterwards the run lists the imported classes that clash with an approved booking, a moved class or an exam, and keeps both.
- **Why:** Rerunning an import must not lose saved activities, bookings or moves. The user decided this on 2026-11-27 (plan approved; vanished classes: cancel; clashes: keep and list).
- **Rejected:** deleting vanished rows; leaving them visible (a rescheduled class would show twice); resolving clashes automatically.
- **Evidence:** etl/schedule/loader.py (cancel_stale), backend/app/data_import.py, backend/tests/test_data_import.py, etl/schedule/tests/test_loader_db.py
- **Source:** user (2026-11-27) · confidence high
- **Confirmed:** 2026-11-27
