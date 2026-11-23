# Architecture — UniSpace

<!-- graffino-agentic:begin v1 -->
> How this repo is built, generated from the code at backfill and kept current by
> whoever changes the structure. The code wins: when this page is wrong, fix it.
<!-- graffino-agentic:end -->

## Overview
UniSpace runs as three containers from `docker-compose.yml`: the frontend (nginx
serving static files), the backend (FastAPI), and the database (PostgreSQL). The
browser loads the frontend, and the frontend calls the backend's API. The backend
reads and writes PostgreSQL. Alembic applies the schema.

```text
browser ──> frontend (nginx :8080) ──> backend (FastAPI :8000) ──> db (PostgreSQL :5432)
                                          │
                                          └── Alembic migrations (backend/alembic) ──> db
```

## Parts
| Part | Path | Responsibility | Talks to |
|---|---|---|---|
| Backend | `backend/app/` | API routes, database access | db (SQLAlchemy), browser via HTTP |
| Routers | `backend/app/routers/` | one module per endpoint group | `main.py` |
| Database layer | `backend/app/db.py` | engine, session, base model | PostgreSQL |
| Migrations | `backend/alembic/` | schema revisions | PostgreSQL |
| Frontend pages | `frontend/pages/<role>/` | one HTML file per screen, grouped by role | nginx (clean URLs), `components/`, `styles/` |
| Frontend components | `frontend/components/` | page template and the shared chrome (header, footer, toggles, toast) | the pages |
| Frontend styles | `frontend/styles/` | design tokens, base, one CSS file per component | the pages and components |
| Frontend scripts | `frontend/js/`, `frontend/i18n/` | session service, single-page scripts, i18n runtime and dictionaries | the pages and components |
| Web routing | `infra/nginx/default.conf` | clean URLs, 404 page, proxy of `/health` (public) and `/api/` (signed in) to the backend | nginx, backend |
| ETL pipelines | `etl/professors/` (on demand, `professors` table), `etl/schedule/` (`cli.py`, `sync.py` steps 1-2, `download.py` step 3, `loader.py` step 4, `common.py`, `tests/`), `etl/professors/` (step 2 of the professors plan, not built yet) | imports the ULBS schedule API into PostgreSQL in four steps | ULBS API (HTTP), `data/schedules/`, PostgreSQL (backend models) |
| Stack | `docker-compose.yml` | runs db, backend, frontend | Docker |

## Frontend structure
Static HTML, CSS and JS, served by nginx from `frontend/`. Nothing is compiled: pages
pull the shared head in with an nginx server-side include (SSI). This section is the map.

```text
frontend/
  pages/
    shared/        home (index.html), login.html, 404.html: every role sees them
    student/       timetable, calendar, changes, rooms/ (index, detail, free), bookings/
    professor/     announcements.html
    admin/         index.html: the approval queue (ADMIN only)
  components/      reusable parts, loaded by every page
    head.html      the page template's <head>: styles and scripts, in order (SSI)
    app.js         entry point: waits for the session, builds header and footer
    ui.js          shared helpers (escape HTML, normalise a path)
    header.js      site header, navigation, user chip, log out, greeting
    language-toggle.js   the RO | EN switch
    theme-toggle.js      the auto / light / dark button
    footer.js      site footer
    toast.js       toast messages and the placeholder actions of the pages
  styles/
    tokens.css     design tokens: the only source of colours, sizes and spaces
    base.css       reset, typography, page layout, skip link
    components/    one CSS file per component (buttons, cards, pills, forms, ...)
    utilities.css  spacing and alignment helpers (my-5, mt-3, justify-center, ...)
    motion.css     reduced-motion overrides, loaded last
  js/
    auth.js        session service: reads /auth/me for the header; not a security check
    api.js         fetch wrappers for /api/* (faculties, groups, professors, classrooms, schedule)
    grid.js        weekly timetable grid (CSS Grid): 10-minute rows 08:00-21:00, overlap lanes
    pages/         scripts of single pages (login.js, timetable.js: Orar, free.js: Liber acum)
  i18n/            i18n.js runtime; ro.js and en.js dictionaries (D-011)
```

**Access.** Everything under `pages/` is gated by nginx (`auth_request`, C-002, D-010).
Public: `pages/shared/login.html`, `styles/`, `components/`, `js/`, `i18n/`. The URL →
file mapping is in `infra/nginx/default.conf`: each clean URL has its own gated location.

**Load order.** `components/head.html` loads the styles in cascade order (tokens, base,
components, utilities, motion) and the scripts in dependency order (i18n, session, UI
helpers, components, `app.js` last). A page adds only its own `<title>` and its page
script, after the include.

**Adding a page.**
1. Create `pages/<role>/<name>.html`: `<!--#include virtual="/components/head.html" -->` in
   the `<head>`, a `data-i18n` title, the body, and any page script under `js/pages/`.
2. Add a gated clean-URL location to `infra/nginx/default.conf` (copy an existing one).
3. Add its keys to `i18n/ro.js` and `i18n/en.js` (the key test in `backend/tests/test_i18n.py` fails otherwise).
4. Add a `DS-` entry in `docs/design/registry.yaml`.

**Adding a component.**
1. The behaviour goes in `components/<name>.js`, registered on `window.UniSpaceUI`. If the
   header or footer uses it, call it from `header.js`, `footer.js` or `app.js`.
2. Its styles go in `styles/components/<name>.css`, using tokens only.
3. Add the `<script>` and `<link>` to `components/head.html`, in order.
4. Add a `DS-` entry in `docs/design/registry.yaml`.

**Unit tests.** The scripts that are not placeholders (`api.js`, `grid.js`, `modules.js`, `pages/free.js`,
`pages/timetable.js`) have tests in `frontend/tests/unit/`, run by Vitest in jsdom with a 100% coverage gate
(`frontend/vitest.config.js`). The app itself is still plain files served by nginx; the test tooling is a
dev-only compose service (`frontend-test`, profile `test`). Run: `docker compose --profile test run --rm frontend-test`.

**Styling rules.** No `style=""` attributes in pages (a test enforces it). Use a component
class, or a utility when the change is only spacing or alignment. The timetable sets grid
positions from JavaScript, the one allowed exception.

## ETL pipeline
Standalone: not wired into FastAPI. Runs as the compose service `etl` (profile `etl`, so a plain
`docker compose up` does not start it). Source: the ULBS schedule API.

| Step | What it does | Writes |
|---|---|---|
| 1 faculties | `GET /api/faculties` | `faculties` |
| 2 sync | active semester or module per faculty (`isCurrent`, date fallback) | `planning_time_units` |
| 3 schedules | `GET /api/faculties/{code}/schedule/weekly` per current unit | `data/schedules/*.json` (file, not the database) |
| 4 load | reads the files; rooms from `/api/faculties/{code}/rooms` (`?faculty=` filter, paginated) | `classrooms`, `student_groups`, `activities` |

Run it: `docker compose --profile etl run --rm etl` (all four steps). Options: `--faculty <code>`,
`--step sync|schedules|load`.

### Professors pipeline (`etl/professors/`)
A separate pipeline, run by an admin on demand (not on a schedule). Source: the ULBS professors API.
It does not depend on the schedule pipeline; it reads the faculty codes from `faculties`.

| Step | What it does | Writes |
|---|---|---|
| extract | `GET /api/faculties/{code}/professors` per faculty, all pages (500 per page) | `data/professors/<code>.json` (normalized records and the skipped ones) |
| load | reads the files; upserts by `id`; deletes nothing | `professors` |

Run it (migrations first):
`docker compose --profile etl run --rm --entrypoint sh etl -c "alembic upgrade head && python -m etl.professors.cli"`.
Options: `--step extract|load`, `--faculty <code>`.

Rules (D-019): the email is stripped and lower-cased; a null, empty or blank email is skipped; the same
professor in several faculties is stored once. Records that share a normalized email are one person:
one id is kept (the id already stored for that email, else one used by an activity, else the smallest)
and each other id is logged as a warning. If the API replaces a stored id with a new id for the same
email, the row takes the new id and the users and activities that pointed at the old one are moved (full
runs only). Emails are not printed or logged.

Rules the loader applies (decisions D-014 to D-017 and the ETL answers in OPEN-QUESTIONS):
- one `activities` row per (room, day, parity, start, end); every entry in that slot is merged into it.
- every study group of a merged slot is linked in `activity_groups`; `activities.group_id` keeps the lowest group id.
- stored rows are named "Didactic Activity", priority 5; the type comes from the ULBS name (see `ACTIVITY_TYPE_BY_NAME`).
- entries with no room, or an online room, are not stored. Entries with no time are reported as unparsed.
- an entry with no study group is stored with no group; an entry with no type is stored as Course and reported as a warning.
- rooms without a capacity store NULL ("unknown capacity").
- rows edited by an admin (`is_manually_modified`) are never changed.
- a row that leaves the feed is deleted, unless an exception or a change request points at it.
- a second run on the same data inserts and deletes nothing.

## Data flow
1. Browser requests a page → nginx checks the session, then serves the page file. Clean URLs map to files explicitly in `infra/nginx/default.conf`: `/timetable` → `pages/student/timetable.html`, `/rooms/` → `pages/student/rooms/index.html`. Unknown paths → `pages/shared/404.html`.
2. Browser calls the API → FastAPI route → `get_db` session → PostgreSQL → JSON response.
3. Schema change → new Alembic revision → `alembic upgrade head` applies it to PostgreSQL.

## State and storage
| What | Where | Owner | Notes |
|---|---|---|---|
| Application data | PostgreSQL, named volume `pgdata` | backend | schema only via migrations |
| Migration history | `alembic_version` table in PostgreSQL | Alembic | created on first upgrade |

## Configuration
| Name | Where set | Used by | Notes |
|---|---|---|---|
| `DATABASE_URL` | docker-compose.yml, from `.env` | backend, Alembic | names only here; values in `.env` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` | `.env` | db, compose | |
| `BACKEND_PORT`, `FRONTEND_PORT` | `.env` | compose port mapping | |

## Build, deploy, runtime
Built from `backend/Dockerfile` (python:3.12-slim) and started by `docker-compose.yml`.
Local only so far. Deploy is not defined (Q-005). See AGENTS.md sections 2 and 5.

## Boundaries
- The database is reachable only inside the compose network by default; the host port
  mapping is for local tools. Guards: D-005 (credentials stay out of the repo).
- Sign-in is Google OAuth with a session cookie (C-002, D-009). The role is resolved on every sign-in:
  professor list, then the student association hook, then a university address, otherwise 403 (D-020).
  The admin signs in with the `.env` credentials at `POST /auth/admin-login` (D-021).
  A student picks a faculty and a study formation on first sign-in; the dialog is in
  `components/onboarding.js`, the choice is saved with `PUT /api/me/study-profile` (D-022, C-004).
- Pages are gated by nginx: `auth_request` asks the backend (`/auth/me`, `/auth/admin` for
  `/admin/`) before any page is served, so a typed URL does not get around it (D-010).
  Public: `/login` (its page `pages/shared/login.html`), `/styles/`, `/components/`, `/js/`,
  `/i18n/`, `/health`, `/auth/`. The API routes under `/api/` are signed in only: nginx asks `/auth/me` first and answers 401 when signed out (C-003).
- `frontend/js/auth.js` only reads the signed-in user for the header; it is not a security check.
- Contracts: docs/agents/CONTRACTS.md.
