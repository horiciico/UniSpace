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
- **Shape:** `/auth/me` returns 200 `{"id", "email", "name", "role"}` or 401. `/auth/logout` returns 204. `/auth/admin-login` takes `{"username", "password"}`: 200 with the same user shape and the session cookie, or 401 `{"detail": "Invalid admin credentials."}`. Rejections are 403 `{"detail": ...}` with the text "Access denied. Login is restricted to @ulbsibiu.ro accounts or registered faculty members." Google failures are 400.
- **Rules:** the role is resolved on every sign-in as in D-020. An email in `professors` is a PROFESSOR on any domain; an `@ulbsibiu.ro` address with the matching `hd` claim is a STUDENT; anything else is a 403. Google accounts must have a verified email. Linking a seeded row with no Google id is allowed when the rule above admits it.
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
- **Confirmed:** 2026-11-22

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
