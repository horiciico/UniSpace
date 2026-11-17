# UniSpace

UniSpace is a faculty timetable and room-booking platform for students, teaching staff, student organizations, and administrators. It is designed around the real academic schedule: recurring activities, odd/even weeks, one-off changes, room availability, approvals, notifications, and priority-based booking conflicts.

> **Project status:** active foundation / work in progress. The repository currently contains the Docker Compose stack, Google sign-in flow, database models and migrations, role-gated frontend pages, bilingual UI, and initial timetable/room/booking screens. The full import, scheduling, approval, notification, iCal, and bump workflows are being built incrementally.

## What UniSpace is intended to provide

- Import the real faculty timetable into a normalized model for activities, disciplines, teachers, groups, rooms, days, time ranges, and week parity.
- Browse the timetable by group, teacher, or room, including the correct current week.
- Find rooms that are free now or free in a selected interval, with capacity and equipment filters.
- Request a room for a student activity, detect conflicts, and route the request through admin approval.
- Represent recurring activities as a rule plus exceptions rather than copied rows for every week.
- Record one-off moves, room changes, and cancellations with history and notifications.
- Export a stable iCal subscription per group for Google Calendar, Apple Calendar, and compatible clients.
- Apply booking priorities: course > exam > official faculty activity > student organization > student.
- Notify and offer an equivalent alternative room when a higher-priority activity bumps a reservation.
- Support configurable semester structure, including breaks, sessions, and inverted-parity weeks.

## Current foundation

- **Backend:** FastAPI, SQLAlchemy, Alembic, and PostgreSQL 16.
- **Frontend:** static HTML, CSS, and JavaScript served by nginx; no frontend build step.
- **Authentication:** Google OAuth with signed, HttpOnly sessions and nginx access gating.
- **Roles:** student, teaching staff, student organization, and admin are represented in the data model; admin-only pages are protected.
- **Internationalization:** Romanian and English dictionaries with automated key coverage checks.
- **UI:** responsive light/dark themes, shared components, clean routes, room/timetable/booking screens, and accessible interaction patterns.
- **Database:** normalized activity, room, group, user, invitation, and recurring-event-exception models with Alembic migrations.

Some visible pages still contain sample or placeholder data until the corresponding Backend workflows are connected.

## Architecture

```text
browser
   │
   ▼
Frontend (nginx :8080)
   │  same-origin proxy for /auth, /health, and /api
   ▼
Backend (FastAPI :8000)
   │
   ▼
PostgreSQL 16
   │
   └── Alembic migrations
```

### Repository layout

```text
backend/
  app/                 FastAPI application, models, configuration, and routers
  alembic/             Database migration history
  tests/               Backend and i18n tests
  Dockerfile
frontend/
  pages/               Shared, student, professor, and admin pages
  components/          Shared head, header, footer, theme, language, and UI helpers
  styles/              Design tokens, base styles, component styles, and utilities
  js/                  Authentication and page scripts
  i18n/                Romanian and English dictionaries
infra/nginx/            Clean URL routing, auth gates, and Backend proxy
docs/agents/             Architecture, contracts, decisions, patterns, and open questions
docs/design/             UI guardrails, registry, mocks, and screenshots
docker-compose.yml       Local PostgreSQL, Backend, Frontend, and pgAdmin stack
.env.example             Required local configuration template
```

## Run locally

### Prerequisites

- Docker and Docker Compose
- A Google OAuth web application configured for the local callback URL

### Setup

```bash
cp .env.example .env
```

Set at least these values in `.env`:

```dotenv
POSTGRES_PASSWORD=choose-a-local-password
PGADMIN_DEFAULT_PASSWORD=choose-a-local-password
GOOGLE_WEB_CLIENT_ID=your-google-client-id
GOOGLE_WEB_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8080/auth/callback
SESSION_SECRET_KEY=generate-a-long-random-secret
```

Start the stack:

```bash
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080). The Backend health endpoint is available at [http://localhost:8080/health](http://localhost:8080/health), and pgAdmin is available at [http://localhost:8090](http://localhost:8090).

The default local ports are:

| Service | Port | Purpose |
|---|---:|---|
| Frontend | `8080` | UniSpace web pages |
| Backend | `8000` | FastAPI service |
| PostgreSQL | `5433` | Host access to the database |
| pgAdmin | `8090` | Local database administration |

Change these mappings in `.env` if they conflict with another service.

## Development commands

Run commands through Docker Compose so the development environment matches the repository setup:

```bash
# Run the test suite
docker compose run --rm backend pytest

# Validate the Compose file
docker compose config

# Apply migrations manually (normally run at Backend startup)
docker compose run --rm backend alembic upgrade head

# Create a migration after changing models
docker compose run --rm backend alembic revision --autogenerate -m "describe the change"
```

Database schema changes must be delivered as new Alembic revisions. Do not edit an applied Migration.

## Authentication and access

Google OAuth starts at `/auth/login`. After a successful sign-in, the Backend creates a signed session cookie. nginx checks that session before serving protected pages; `/admin/` additionally requires the admin role.

The current development role flow is documented in `docs/agents/OPEN-QUESTIONS.md`. Do not put credentials, `.env`, or production secrets in the repository.

## Scheduling model

Recurring activities are represented by a base activity and optional event exceptions. Activities include the day, time range, room, group, priority, status, and week parity. Room records include capacity and equipment such as projectors and outlets.

The scheduling design is intended to preserve these invariants:

- recurring rules are not duplicated into one row per week;
- one-off moves, relocations, and cancellations are explicit exceptions;
- conflict detection must handle partial overlaps and different week parities;
- room alternatives must meet or exceed the requested capacity and equipment;
- priority bumps must notify the affected booking and provide a response deadline.

## Documentation

- `CONTEXT.md` — approved UniSpace vocabulary and the product brief.
- `AGENTS.md` — repository workflow, commands, constraints, and definition of done.
- `docs/agents/ARCHITECTURE.md` — system boundaries and data flow.
- `docs/agents/CONTRACTS.md` — cross-component contracts.
- `docs/agents/DECISIONS.md` — approved technical decisions.
- `docs/agents/PATTERNS.md` — reusable repository patterns.
- `docs/agents/OPEN-QUESTIONS.md` — product and operational questions still awaiting confirmation.
- `docs/design/DESIGN.md` — design guardrails and accessibility requirements.

## Roadmap

1. Connect the timetable import pipeline and produce an explicit report of unparsed lines.
2. Add normalized timetable browsing by group, teacher, and room with current-week parity expansion.
3. Implement free-room queries, booking requests, conflict detection, and admin approvals.
4. Add change history, announcements, email delivery, and group calendar subscriptions.
5. Implement configurable semester structure and tested priority bumping with equivalent alternatives.
6. Validate the live timetable and room inventory against real faculty data and verify iCal imports in Google Calendar and Apple Calendar.

## Contributing

Keep changes small and aligned with the approved entries in `docs/agents/`. For frontend changes, add all new visible text to both `frontend/i18n/ro.js` and `frontend/i18n/en.js`. Add or update focused tests, then run the repository test suite before reporting a feature complete.
