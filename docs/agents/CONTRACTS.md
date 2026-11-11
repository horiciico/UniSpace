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

---

## Provided

### C-001 · GET /health
- **Status:** approved
- **Interface:** HTTP `GET /health` on the backend (port 8000 locally).
- **Consumers:** none yet. The frontend placeholder links to it for people only.
- **Shape:** 200 with `{"status": "ok"}`. No other fields.
- **Rules:** No auth. Any change to the shape is a PROPOSAL.
- **Evidence:** backend/app/routers/health.py:7; consumer link in frontend/index.html
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
