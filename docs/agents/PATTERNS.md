# Patterns — UniSpace

<!-- graffino-agentic:begin v1 -->
> How we build things here. Copy only `approved` entries. `candidate` = seen once or
> not yet confirmed; agents add these freely. Promotion needs the user's OK.
<!-- graffino-agentic:end -->

## Index
- PATTERN-001 · Database session per request through a dependency · candidate
- PATTERN-002 · One router module per resource, included in main.py · candidate
- PATTERN-003 · Endpoint tests with FastAPI TestClient · candidate

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
