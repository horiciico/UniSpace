# Contracts — UniSpace

<!-- graffino-agentic:begin v1 -->
> Promises across a boundary. **Provided:** this repo owns the contract; the text
> lives here only. **Consumed:** a link to the provider's entry plus the fields this
> repo relies on. **External:** what we rely on from a third-party service.
> Changing a provided contract is a PROPOSAL (AGENTS.md → The gate) and the plan
> lists the consumers' files too. Status: `approved` · `proposed` · `superseded-by`.
<!-- graffino-agentic:end -->

## Index
- C-001 · GET /health · provided
- C-002 · Auth routes (Google sign-in and admin sign-in) · provided
- C-003 · Timetable and free-room API (/api/*) · provided
- C-004 · PUT /api/me/study-profile · provided
- C-005 · Room bookings API (/api/bookings) · provided
- C-006 · Admin booking review API (/api/admin/bookings) · provided
- C-007 · Admin room attributes API (/api/admin/classrooms) · provided

---

## Provided

### C-001 · GET /health
- **Status:** approved
- **Interface:** HTTP `GET /health` on the backend (port 8000 locally).
- **Consumers:** the browser, through nginx on the same origin (`/health`, see `infra/nginx/default.conf`). The frontend does not call it from code yet.
- **Shape:** 200 with `{"status": "ok"}`. No other fields.
- **Rules:** No auth. Any change to the shape is a PROPOSAL.
- **Evidence:** backend/app/routers/health.py:7; consumer link in frontend/pages/shared/index.html
- **Source:** code · confidence high

### C-002 · Auth routes (Google sign-in and admin sign-in)
- **Status:** approved
- **Interface:** HTTP on the backend, no `/api` prefix, also proxied by nginx on the frontend origin (`:8080` locally): `GET /auth/login` (redirect to Google), `GET /auth/callback` (Google redirect URI; resolves the role, sets the session cookie, 303 to `POST_LOGIN_URL`), `POST /auth/admin-login` (admin sign-in with `.env` credentials, D-021), `GET /auth/me`, `GET /auth/admin` (204 for ADMIN, 403 otherwise, 401 signed out), `POST /auth/logout`.
- **Consumers:** nginx (`infra/nginx/default.conf`: `auth_request` on `/auth/me` and `/auth/admin`; turns `/auth/callback` 403 and 400 into `/login?error=denied|failed`); the frontend (`frontend/js/auth.js` reads `/auth/me` and posts `/auth/logout`; `frontend/pages/shared/login.html` links `/auth/login`).
- **Shape:** `/auth/me` returns 200 `{"id", "email", "name", "role", "faculty_id", "study_formation_id", "needs_onboarding", "picture"}` or 401 (the last four are nullable / specific; D-022). `/auth/logout` returns 204. `/auth/admin-login` takes `{"username", "password"}`: 200 with the same user shape and the session cookie, or 401 `{"detail": "Invalid admin credentials."}`. Rejections are 403 `{"detail": ...}` with the text "Access denied. Login is restricted to @ulbsibiu.ro accounts or registered faculty members." Google failures are 400.
- **Rules:** the role is resolved on every sign-in as in D-020. An email in `professors` is a PROFESSOR on any domain; an `@ulbsibiu.ro` address with the matching `hd` claim is a STUDENT; anything else is a 403. Google accounts must have a verified email. Linking a seeded row with no Google id is allowed when the rule above admits it.
- **Change 2026-11-23:** `/auth/me` and the sign-in responses carry `faculty_id`, `study_formation_id` and `needs_onboarding` (D-022). Consumer: `frontend/components/onboarding.js`; the rest of the frontend reads the user as before.
- **Change 2026-11-24:** `/auth/me` and the sign-in responses carry `picture` (Google profile picture URL, nullable). Consumer: `frontend/components/header.js`.
- **Evidence:** backend/app/routers/auth.py, backend/app/auth.py, backend/app/routers/auth.py (admin_login), infra/nginx/default.conf (`location /auth/`)
- **Source:** user (decisions D-020 and D-021, 2026-11-23) · code · confidence high
- **Confirmed:** 2026-11-23

### C-003 · Timetable and free-room API (/api/*)
- **Status:** approved
- **Interface:** HTTP JSON on the backend, same origin, through nginx at `/api/`. Signed in only: nginx checks `/auth/me` first and answers a signed-out request with 401 (no redirect). Every route is `GET`.
- **Consumers:** `frontend/js/api.js` (the only fetch wrapper); `frontend/js/pages/free.js` (Liber acum); `frontend/js/pages/timetable.js` (Orar); `infra/nginx/default.conf` (the gate).
- **Shape:**
  - `GET /api/faculties` → `[{id, code, name}]`, by name.
  - `GET /api/groups?faculty_id=UUID` (required) → `[{id, name, faculty_id}]`: groups with an activity in a planning unit of the faculty.
  - `GET /api/professors?faculty_id=UUID` (required) → `[{name}]`: professors named on the faculty's activities (a joint listing is split).
  - `GET /api/classrooms?faculty_id=UUID|campus` (optional) → `[{id, name, faculty_id, capacity, is_bookable, is_field_verified}]`. `campus` means no owning faculty.
  - `GET /api/classrooms/free?faculty_id&date=YYYY-MM-DD&start_time=HH:MM&end_time=HH:MM&min_capacity&has_projector=true&only_verified=true` → `[{id, name, faculty_id, faculty_name, capacity, has_projector, has_outlets, is_field_verified, free_until}]`. Only bookable rooms. Bookings are whole modules (08:00-09:30, 09:40-11:10, ... 19:40-21:10, see backend/app/planning.py MODULES): with `start_time` only, the module that contains that time (or the next one during a break) is searched, so an exact local time gives its module; with `end_time` too, `start_time` must be a module start and `end_time` a module end, and `end_time` after `start_time`. Without `start_time`, the current time in Europe/Bucharest is used. On the current day nothing is bookable after 21:10; later days are bookable by module, and a start-only search on a later day after 21:10 returns no rooms. `free_until` is the next start that day, or 21:10 when nothing follows. Sorted: verified first, then the latest `free_until`, then name.
  - `GET /api/schedule` with exactly one of `group_id=UUID`, `professor=NAME`, `room_id=UUID`, plus optional `date=YYYY-MM-DD` and optional `faculty_id=UUID` → `{week_start, week_end, week_number, parity, entity_type, entity_label, items}`. The week is Monday to Sunday. Only one planning unit is drawn: the faculty's unit that covers the week when `faculty_id` is given (a faculty with no unit for the week shows no recurring activities and null week number); without it, the unit most of the entity's recurring activities use in weeks covering this one. One-off rows (no unit) are always included. `week_number` and `parity` are null when there is no unit. Each item: `{id, title, activity_type, priority, day_of_week, date, start_time, end_time, parity, room_id, room_name, professor, groups, is_recurring}`.
- **Rules:** `day_of_week` is ISO (1 = Monday, D-008). Parity follows the week of each activity's own planning unit (D-014). `id` values are UUIDs; times are `HH:MM`. Errors: 400 for a missing or repeated entity, a bad `faculty_id`, a time that is not a module boundary, or a search on the current day at or after 21:10 (no module left); 401 when signed out; 404 for an unknown group or room; 422 for an invalid parameter (FastAPI).
- **Evidence:** backend/app/routers/classrooms.py, backend/app/routers/lookups.py, backend/app/routers/schedule.py, backend/app/planning.py, backend/tests/test_timetable_api.py, infra/nginx/default.conf (`location ^~ /api/`)
- **Change 2026-11-22:** `faculty_id` added to `/api/schedule`; the timetable shows one planning unit (user request). Consumer: `frontend/js/pages/timetable.js` sends it.
- **Source:** user (asked for the endpoints and their gating, 2026-11-22) · code · confidence high
- **Change 2026-11-22 (2):** free-room search uses whole modules; `free_until` is never null (21:10 when nothing follows); `/api/classrooms/free` refuses times that are not module boundaries and any search after 21:10. Consumers: `frontend/js/pages/free.js`, `frontend/js/modules.js`. (user request)
- **Change 2026-11-24 (5), issue #23:** `GET /api/bookings/my` and the booking responses now carry `decided_at` and `decision_message` (C-006). Consumer: `frontend/js/pages/bookings.js` (the note on a decided request).
- **Change 2026-11-24 (4):** with `room_id`, `GET /api/schedule` also returns the room's APPROVED bookings of the week (C-005) as items with `activity_type` `BOOKING`, `priority` null, `is_recurring` false, `groups` [] and `professor` null. Pending and cancelled bookings are not shown, and a group or professor timetable never gets them. Consumers: `frontend/js/pages/timetable.js` (details: priority "Not specified"), `frontend/js/grid.js` (block `tt-block--booking`, legend).
- **Change 2026-11-24 (3), Q-017:** the timetable (`GET /api/schedule`) no longer shows a CANCELLED activity or an occurrence cancelled by an exception, and shows a moved occurrence on its new date and at its new time, with `day_of_week` = its new weekday. The free-room search and the booking check use the same rules. Consumers: `frontend/js/pages/timetable.js`, `frontend/js/grid.js` (places by `day_of_week`). Moves to another room are not handled yet (Q-018).
- **Change 2026-11-24:** approved bookings (C-005) hide a room from the free-room search, and each result gains `start_time` and `end_time` (the searched window). `free_until` is unchanged and also counts approved booking starts. Consumer: `frontend/js/pages/free.js` (no change needed; the new fields are additive).
- **Change 2026-11-24 (6), approved proposal P2:** `GET /api/classrooms` rows carry `has_projector` (nullable: NULL = unspecified), `board_type`, `access_notes` and `equipment_notes`. `GET /api/classrooms/free` keeps `has_projector` nullable (NULL is not "has a projector") and carries `board_type`, `access_notes` and `equipment_notes`. Consumers: `frontend/js/pages/timetable.js` (the room description, access notes only), `frontend/js/pages/admin-rooms.js`. Free Now (`frontend/js/pages/free.js`) no longer sends `only_verified` from the page; the parameter stays in the API. Access notes are not shown on the Free Now card.
- **Confirmed:** 2026-11-24

### C-004 · PUT /api/me/study-profile
- **Status:** approved
- **Interface:** HTTP `PUT /api/me/study-profile` on the backend, through nginx at `/api/` (signed in only). Body: `{"faculty_id": UUID, "study_formation_id": UUID}`.
- **Consumers:** `frontend/js/api.js` (`saveStudyProfile`); `frontend/components/onboarding.js` (the first-sign-in dialog).
- **Shape:** 200 with the user shape of C-002 (`needs_onboarding` false once saved). 401 when signed out. 403 `{"detail": "Only students choose a faculty and a study formation."}` for a non-student. 422 `{"detail": "That study formation is not in the chosen faculty."}` when the formation is not in the faculty's list (`GET /api/groups?faculty_id=`, C-003).
- **Rules:** only a STUDENT may save; the formation must belong to the faculty. A later sign-in keeps the saved choice. Nothing else on the user changes.
- **Evidence:** backend/app/routers/study_profile.py, backend/app/routers/lookups.py (faculty_groups), backend/tests/test_study_profile.py
- **Source:** user (plan approved, 2026-11-23; decision D-022) · code · confidence high
- **Confirmed:** 2026-11-23

### C-005 · Room bookings API (/api/bookings)
- **Status:** approved
- **Interface:** HTTP JSON on the backend, same origin, through nginx at `/api/`. Signed in only (401 otherwise).
- **Consumers:** `frontend/js/api.js` (the wrappers); `frontend/js/pages/bookings.js` (the Bookings page, `frontend/pages/shared/bookings.html`); `frontend/js/bookings.js` (the link format); `frontend/js/pages/timetable.js` and `frontend/js/grid.js` (room view: free modules link to the page); `frontend/js/pages/free.js` (each card's Book action).
- **Shape:**
  - `POST /api/bookings` with `{classroom_id, specific_date, start_time, end_time, title}` → 201 with the booking. Any signed-in role can book. An ADMIN's booking is `approved` at once; any other role's is `pending`. `title` is trimmed, 1 to 255 characters.
  - `GET /api/bookings/my` → `[{id, classroom_id, room_name, faculty_name, specific_date, start_time, end_time, title, status, created_at}]`. Upcoming first (date and start ascending, newest created on a tie), then past ones, most recent first. `faculty_name` is the room's faculty name, or `null` when the room has none (the frontend shows "Campus", D-012).
  - `DELETE /api/bookings/{id}` → 200 with the booking, status `cancelled`. Only the owner, and only while `pending`; the row is kept.
- **Rules:** Times are `HH:MM` and must be whole ULBS modules (planning.MODULES), start before end. A start earlier than now (Europe/Bucharest) is refused. A room that is not bookable is 400; an unknown room is 404. A clash with a recurring activity (on its weeks and parity) or with an `approved` booking is 409 with the clashing times in `detail`; cancelled activities and occurrences cancelled by an exception do not clash (Q-017). `pending` bookings never clash. Errors: 400 bad input, 401 signed out, 403 another user's booking, 404 unknown id, 409 state or clash.
- **Evidence:** backend/app/routers/bookings.py, backend/app/models/booking.py, backend/tests/test_bookings_api.py
- **Source:** user (2026-11-24: any signed-in user books; admins auto-approve; the defaults for errors, cancel, ordering and fields) · code · confidence high
- **Link:** the Bookings page reads `/bookings/?faculty_id=UUID|campus&room=UUID&date=YYYY-MM-DD&start=HH:MM&end=HH:MM` (values optional, malformed ones dropped; `frontend/js/bookings.js`).
- **Change 2026-11-24 (2):** `faculty_name` is `null` for a room with no faculty (user request, D-012), not the text "Campus".
- **Confirmed:** 2026-11-24

### C-006 · Admin booking review API (/api/admin/bookings)
- **Status:** approved
- **Interface:** HTTP JSON, signed in as ADMIN only (403 for any other role, 401 when signed out).
- **Consumers:** `frontend/js/pages/admin-bookings.js` (Pending requests tab), `frontend/js/pages/admin-history.js` (Booking history tab, 15 a page), `frontend/js/api.js`; the admin page `frontend/pages/admin/index.html` (designs: docs/design/mocks/DS-unispace-admin-bookings.html, DS-unispace-admin-history.html).
- **Shape:**
  - `GET /api/admin/bookings/pending` → `[{id, classroom_id, room_name, faculty_name, specific_date, start_time, end_time, title, status, created_at, decided_at, decision_message, requester: {name, email, role}}]`, oldest first. `faculty_name` is null for a room with no faculty.
  - `GET /api/admin/bookings?faculty_id=UUID|campus&classroom_id=UUID&status=pending|approved|rejected|cancelled&limit=1..200 (default 50)&offset=0` → `{items, total, limit, offset}`. Every booking, newest first (date, start time, then when it was made). `faculty_id=campus` is the rooms with no faculty. Items: `{id, classroom_id, classroom_name, faculty_id, faculty_name, specific_date, start_time, end_time, title, status, created_at, user_id, user_email, user_role}`. `total` counts all matches. Bad filter → 400 (faculty_id) or 422.
  - `POST /api/admin/bookings/{id}/cancel` with optional `{message}` (up to 100 characters; blank means none) → 200 with the booking, status `rejected`, `decision_message` and `decided_by_id`/`decided_at` set. Any user's booking that is `approved` and has not started yet (409 otherwise). 403 for non-admins. The admin's cancel is a rejection, so the requester sees the status and the message on `GET /api/bookings/my`.

  - `POST /api/admin/bookings/{id}/decision` with `{decision: "approve" | "reject", message?: string}` (message up to 100 characters; blank means none) → 200 with the booking. Only a `pending` booking can be decided (409 otherwise). An approval is checked for clashes again (409 with the clashing times). The decision keeps who decided (`decided_by_id`), when (`decided_at`) and the message (`decision_message`).
- **Rules:** the requester sees the final status and `decision_message` on `GET /api/bookings/my` (C-005).
- **Evidence:** backend/app/routers/admin_bookings.py, backend/app/models/booking.py, backend/alembic/versions/20261124_3b4860b5bd9c_booking_decisions.py, backend/tests/test_admin_bookings.py
- **Source:** issue #23 (Add an admin page to review booking requests), user request · code · confidence high

### C-007 · Admin room attributes API (/api/admin/classrooms)
- **Status:** approved
- **Interface:** HTTP JSON on the backend, same origin, through nginx at `/api/`. Signed in as ADMIN only (403 for any other role, 401 signed out).
- **Consumers:** `frontend/js/pages/admin-rooms.js` (the Rooms tab on the admin page), `frontend/js/api.js` (`adminClassrooms`, `patchAdminClassroom`), `frontend/pages/admin/index.html`.
- **Shape:**
  - `GET /api/admin/classrooms?faculty_id=UUID|campus` (optional) → `[{id, name, faculty_id, capacity, is_bookable, has_projector, board_type, access_notes, equipment_notes}]`, by name. `faculty_id=campus` is the rooms with no faculty; a bad id is 400.
  - `PATCH /api/admin/classrooms/{id}` with any of `is_bookable` (boolean, not null), `has_projector`, `board_type` (`whiteboard`, `blackboard`, `smartboard`, `none`), `access_notes` (up to 255 characters), `equipment_notes` (up to 500). Only the fields sent change. A null clears the field to unspecified; blank notes are stored as null; notes are trimmed. → 200 with the room. 404 for an unknown room, 422 for a bad value.
- **Rules:** set by an admin only; the classroom ETL never writes these fields (D-024).
- **Evidence:** backend/app/routers/classroom_attributes.py, backend/tests/test_classroom_attributes.py, backend/alembic/versions/20261124_f3a9c2d71e05_classroom_attributes.py
- **Source:** user (approved proposal P2, 2026-11-24) · code · confidence high
- **Confirmed:** 2026-11-24

## Consumed

None yet.

## External

### PostgreSQL 16 · database
- **Interface:** the `postgres:16-alpine` image; SQL over the psycopg 3 driver.
- **We rely on:** a database at host `db`, port 5432, with the name, user and password from `.env`.
- **Known quirks:** none recorded.
- **Evidence:** docker-compose.yml (service `db`), backend/app/db.py:7

### nginx 1.27 · frontend server
- **Interface:** the `nginx:1.27-alpine` image serving files from `/usr/share/nginx/html`.
- **We rely on:** static file serving of `frontend/` on port 80 inside the container.
- **Known quirks:** none recorded.
- **Evidence:** docker-compose.yml (service `frontend`)
