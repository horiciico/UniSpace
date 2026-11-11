# Patterns — UniSpace

<!-- graffino-agentic:begin v1 -->
> How we build things here. Copy only `approved` entries. `candidate` = seen once or
> not yet confirmed; agents add these freely. Promotion needs the user's OK.
<!-- graffino-agentic:end -->

## Index
- PATTERN-001 · Database session per request through a dependency · candidate
- PATTERN-002 · One router module per resource, included in main.py · candidate
- PATTERN-003 · Endpoint tests with FastAPI TestClient · candidate
- PATTERN-004 · SQLAlchemy 2.0 typed models, one module per table · candidate
- PATTERN-005 · Database tests run the real migration and roll back · candidate

---

## PATTERN-001 · Database session per request through a dependency
- **Status:** candidate
- **Use when:** an endpoint reads or writes the database.
- **How:** Take `db: Session = Depends(get_db)` as a parameter. Do not create engines or sessions anywhere else.
- **Example:** backend/app/db.py:get_db
- **Why:** One session per request, always closed, so connections do not leak.
- **Source:** code · confidence medium

## PATTERN-002 · One router module per resource, included in main.py
- **Status:** candidate
- **Use when:** adding an endpoint group.
- **How:** Create `backend/app/routers/<name>.py` with an `APIRouter`. Register it in `backend/app/main.py` with `include_router`.
- **Example:** backend/app/routers/health.py, backend/app/main.py:7
- **Why:** Keeps route files small and the entry point readable.
- **Source:** code · confidence medium

## PATTERN-003 · Endpoint tests with FastAPI TestClient
- **Status:** candidate
- **Use when:** testing an endpoint.
- **How:** Build `TestClient(app)` from `app.main`, call the route, and assert the status and the JSON body. Run with `docker compose run --rm backend pytest`.
- **Example:** backend/tests/test_health.py
- **Why:** Tests the real routing and validation without starting a server.
- **Source:** code · confidence medium

## PATTERN-004 · SQLAlchemy 2.0 typed models, one module per table
- **Status:** candidate
- **Use when:** adding a table.
- **How:** `backend/app/models/<table>.py` with a `Base` subclass using `Mapped[]` / `mapped_column`, relationships with `back_populates`, named CHECK constraints and indexes in `__table_args__`. Export it in `models/__init__.py`.
- **Example:** backend/app/models/activity.py
- **Why:** Typed, reviewable, and Alembic sees every model through one import.
- **Source:** code · confidence medium

## PATTERN-005 · Database tests run the real migration and roll back
- **Status:** candidate
- **Use when:** testing models or queries that need PostgreSQL.
- **How:** A session fixture runs `alembic upgrade head`; a per-test fixture opens a connection and outer transaction, binds a `Session` with `join_transaction_mode="create_savepoint"`, and rolls back at the end. Run via compose, where `db` is available.
- **Example:** backend/tests/test_models.py (fixtures `migrated`, `db`)
- **Why:** Tests the schema as shipped, and leaves no rows behind.
- **Source:** code · confidence medium
