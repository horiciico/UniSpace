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
- C-002 · Auth routes (Google sign-in) · provided · _proposed_

---

## Provided

### C-001 · GET /health
- **Status:** approved
- **Interface:** HTTP `GET /health` on the backend (port 8000 locally).
- **Consumers:** the browser, through nginx on the same origin (`/health`, see `infra/nginx/default.conf`). The frontend does not call it from code yet.
- **Shape:** 200 with `{"status": "ok"}`. No other fields.
- **Rules:** No auth. Any change to the shape is a PROPOSAL.
- **Evidence:** backend/app/routers/health.py:7; consumer link in frontend/index.html
- **Source:** code · confidence high

### C-002 · Auth routes (Google sign-in)
- **Status:** proposed
- **Interface:** HTTP on the backend, no `/api` prefix, also proxied by nginx on the frontend origin (`:8080` locally): `GET /auth/login` (redirect to Google), `GET /auth/callback` (Google redirect URI; sets the session cookie, 303 to `POST_LOGIN_URL`), `GET /auth/me`, `GET /auth/admin` (204 for ADMIN, 403 otherwise, 401 signed out), `POST /auth/logout`.
- **Consumers:** nginx (`infra/nginx/default.conf`: `auth_request` on `/auth/me` and `/auth/admin`; turns `/auth/callback` 403 and 400 into `/login?error=denied|failed`); the frontend (`frontend/js/auth.js` reads `/auth/me` and posts `/auth/logout`; `frontend/login.html` links `/auth/login`).
- **Shape:** `/auth/me` returns 200 `{"id", "email", "name", "role"}` or 401. `/auth/logout` returns 204. Rejections are 403 `{"detail": ...}`; Rule C text: "Access denied. Please use your institutional @ulbsibiu.ro account or request an invitation." Google failures are 400.
- **Rules:** `@ulbsibiu.ro` (hd claim and email both) is auto-provisioned as STUDENT; other domains need an unused `invitation` row for the email. Any other role for a university user is an admin change (Q-009).
- **Evidence:** backend/app/routers/auth.py, backend/app/auth.py
- **Source:** code · confidence high

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
