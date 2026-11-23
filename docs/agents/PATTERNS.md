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
- PATTERN-006 · Mock the identity provider at the authlib client, keep the database real · candidate
- PATTERN-007 · Check the signed-in UI in headless Chrome over the DevTools protocol · candidate
- PATTERN-009 · Frontend unit tests load the real page markup, dictionaries and scripts in jsdom · candidate
- PATTERN-008 · Keep the translation dictionaries complete with a test that reads the pages · candidate

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

## PATTERN-006 · Mock the identity provider at the authlib client, keep the database real
- **Status:** candidate
- **Use when:** testing a login or callback route.
- **How:** `monkeypatch.setattr(oauth.google, "authorize_access_token", fake)` returning `{"userinfo": claims}`; override `get_db` with the rollback `db` fixture; use an `https://` TestClient base URL so the session cookie is sent whatever `COOKIE_SECURE` is. Commit seed rows with `db.commit()` before the request so a route-level rollback keeps them.
- **Example:** backend/tests/test_auth.py
- **Why:** The bouncer rules run against real constraints, with no network call to Google.
- **Source:** code · confidence medium

## PATTERN-007 · Check the signed-in UI in headless Chrome over the DevTools protocol
- **Status:** candidate
- **Use when:** a UI change depends on the session (header, role label, redirects, logout) and Q-003 has no tooling yet.
- **How:** Create temporary users and signed session cookies inside the backend container (`itsdangerous.TimestampSigner` over base64 JSON, same secret), start Chrome with `--headless=new --remote-debugging-port`, set the cookie with `Network.setCookie`, drive pages with Node's built-in `WebSocket`, assert on `location.pathname` and header text, and screenshot with `Page.captureScreenshot`. Delete the users and cookies afterwards. A dark system theme makes "no flag" render dark; `--blink-settings=preferredColorScheme=1` renders light.
- **Example:** none in the repo (the script was a throwaway in the temp folder)
- **Why:** Real browser, real cookies, no new dependency.
- **Source:** code · confidence low

## PATTERN-009 · Frontend unit tests load the real page markup, dictionaries and scripts in jsdom
- **Status:** candidate
- **Use when:** a browser script (an IIFE on `window`) needs unit tests with full coverage.
- **How:** Vitest (Vite's test runner) in jsdom, config in `frontend/vitest.config.js`, helpers in `frontend/tests/helpers.js`. Each test mounts the page's `<body>` from its HTML file, loads the i18n runtime and dictionaries, then imports the script after `vi.resetModules()`. `fetch` is stubbed by route; time is faked with `vi.useFakeTimers({ toFake: ["Date", ...] })`. A setup file removes the listeners a script adds to `document` and `window`. Coverage gate: 100% of lines, branches, functions and statements for the listed scripts. Run with `docker compose --profile test run --rm frontend-test`.
- **Example:** frontend/tests/unit/free.test.js, frontend/tests/unit/timetable.test.js
- **Why:** The tests check what the user sees (text, classes, requests), in the same markup and language the pages use, and nothing needs a bundler or a browser.
- **Source:** code · confidence medium

## PATTERN-008 · Keep the translation dictionaries complete with a test that reads the pages
- **Status:** candidate
- **Use when:** a dictionary is kept per language and pages or scripts refer to keys by name.
- **How:** A pytest reads the HTML and JS files (mounted read-only into the test container) and checks that every key used exists in every dictionary, that the dictionaries have the same keys, and that no key is unused. Dictionaries are plain `register("lang", {...})` calls whose body is JSON, so the test can parse them without running JavaScript. Keys built at run time are listed explicitly.
- **Example:** backend/tests/test_i18n.py
- **Why:** A key missing in one language is caught before it reaches the browser, without a browser.
- **Source:** code · confidence medium
