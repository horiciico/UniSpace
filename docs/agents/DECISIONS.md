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

---

## D-001 · Backend is Python 3.12 with FastAPI
- **Status:** approved
- **Date:** 2026-11-11
- **Rule:** The backend is a FastAPI application in `backend/app/`. HTTP endpoints are FastAPI routes.
- **Why:** The user chose Python with FastAPI for the backend.
- **Rejected:** none stated
- **Evidence:** backend/app/main.py:5, backend/requirements.txt
- **Source:** user · confidence high

## D-002 · Database is PostgreSQL; schema changes go through Alembic migrations
- **Status:** approved
- **Date:** 2026-11-11
- **Rule:** The database is PostgreSQL. Every schema change is an Alembic revision in `backend/alembic/versions/`. The app never creates tables at runtime.
- **Why:** The user chose PostgreSQL with Alembic. Revisions keep schema changes reviewable and reproducible.
- **Rejected:** none stated
- **Evidence:** backend/alembic.ini, backend/alembic/env.py, backend/app/db.py:9
- **Source:** user · confidence high

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

## D-005 · Configuration comes from the environment; .env is never committed
- **Status:** approved
- **Date:** 2026-11-11
- **Rule:** Settings are read from environment variables. `DATABASE_URL` is read in `backend/app/config.py`. Local values and secrets live in `.env`, which git ignores. `.env.example` lists the names.
- **Why:** Credentials must stay out of the repository. Compose reads them from `.env`.
- **Rejected:** none stated
- **Evidence:** backend/app/config.py:4, docker-compose.yml (env_file), .env.example, .gitignore
- **Source:** code · confidence high
