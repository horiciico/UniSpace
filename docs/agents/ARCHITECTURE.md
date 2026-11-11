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
| Frontend | `frontend/` | static HTML, CSS, JS | backend API (not built yet) |
| Stack | `docker-compose.yml` | runs db, backend, frontend | Docker |

## Data flow
1. Browser requests a page → nginx serves `frontend/` files.
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
- The API has no authentication yet (C-001 is public). Auth is not decided.
- Contracts: docs/agents/CONTRACTS.md.
