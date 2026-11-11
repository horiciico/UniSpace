# AGENTS.md — UniSpace

<!-- graffino-agentic:begin v1 -->
## How we work here

**Before any work:** `git fetch --all --prune`, then `git pull --ff-only`. Stop on a
non-fast-forward or on uncommitted changes you did not make.

**Always load** (indexes; open the entry, or its topic file, before you rely on it):
`docs/agents/DECISIONS.md`, `docs/agents/PATTERNS.md`,
`docs/agents/CONTRACTS.md`, `docs/agents/OPEN-QUESTIONS.md`, `CONTEXT.md`.

**Load on demand:**

| When | Load |
|---|---|
| You rely on an entry | the entry, or its topic file under `docs/agents/<kind>/` |
| Structural work | `docs/agents/ARCHITECTURE.md` |
| Old code or a past decision needs explaining | `docs/agents/DECISIONS-SUPERSEDED.md`, `PATTERNS-SUPERSEDED.md` (never obeyed) |
| UI work | `docs/design/DESIGN.md`, `docs/design/registry.yaml` |
| Database schema change | D-002 · `backend/alembic/` |
| Container or environment change | D-004, D-005 · `docker-compose.yml`, `.env.example` |

**Flow:** a change to more than a few lines, or one with a design choice, starts with
`/plan`. The approved plan runs with `/build`. Small fixes go straight to build, with
tests first where tests exist.

### The gate
Ask yourself: **does this change something already approved?**
- **Do, then report:** add a `candidate` pattern; add or answer an open question
  (only with an answer the user gave); write a `Proposed answer` the evidence
  supports (the question stays `investigating` until the user confirms it); fix a
  typo, link or moved path; code that follows the approved entries.
- **Propose and wait:** change, supersede or delete an `approved` pattern or
  decision; promote `candidate → approved`; add a decision; code that contradicts an
  entry. Use this shape, then stop:

```text
PROPOSAL: <add-decision | change | supersede | promote | delete>
- Existing: <ID and what it says, or "none">
- Proposed: <the new rule>
- Why now: <what changed>
- Impact: <files that follow the old rule>
- If approved: <old ID> → superseded-by <new ID> (kept, not deleted)
```
Before you propose, check `docs/agents/REJECTED.md`: never re-propose a rejected item
without new evidence. A rejected proposal is added there with the reason.

### Hard rules
- Build only from `approved` entries. Unanswered means out of scope: record a Q-,
  never invent a value, a requirement or a behaviour.
- Add nothing nobody asked for. Note it as a suggestion instead.
- Build the smallest change that meets the approved criteria, reusing existing code.
  A new abstraction, dependency, configuration option, extension point or broad
  refactor needs a concrete reason today. Never at the cost of tests or error handling.
- Tests first where the repo has tests. Never change what an existing test asserts
  to make code pass; an assertion you think is wrong goes to the user.
- Never write a secret, token, password or personal data into a file, commit or log.
- Never push, tag, release, or deploy without the user's go for that action.
- When you cite past work, label the intent: **replicate** (only for an `approved`
  pattern) or **for awareness only**. History is not a template.
- The code wins over any document. When they disagree, say so and fix the document.
- Report honestly: a failed check is reported with its output; a skipped step is
  named with its reason.

### Ledger rules
- IDs are one sequence per kind in this repo: `D-`, `PATTERN-`, `C-`, `Q-`. Never renumber.
- A provided contract (C-) lives here only; consumers link to it. Changing one is a
  PROPOSAL, and the plan names the consumer files too.
- Superseded entries stay (`status: superseded-by <ID>`) so old code stays explainable.
  Their index lines live in `DECISIONS-SUPERSEDED.md` / `PATTERNS-SUPERSEDED.md`, not
  in the always-loaded indexes; the lint (`--fix`) moves them.
- After any ledger change: `python3 docs/agents/tools/ledger-lint.py --fix` (next free
  ID: `--next D`). It must pass.
- **Confirmed:** when the user confirms an entry in a plan, set `- **Confirmed:** <date>`
  on it. Any edit to an entry removes its Confirmed line.
- A new reusable practice becomes a `candidate` pattern in the same session.
- A settled constraint becomes a decision PROPOSAL in the same session.
<!-- graffino-agentic:end -->

## 1. What this repo is
UniSpace: a web platform. A FastAPI backend, a plain HTML/CSS/JS frontend, and a
PostgreSQL database, all run with Docker Compose. Who uses it and what it does is not
defined yet (Q-001).

## 2. Stack and commands
Python 3.12 + FastAPI · HTML/CSS/JS · PostgreSQL 16 + Alembic · Docker Compose.

```bash
cp .env.example .env                                  # first time only; then set the values
docker compose up --build                             # db, backend (:8000), frontend (:8080)
docker compose run --rm backend pytest                # tests
docker compose run --rm backend alembic upgrade head  # apply migrations
docker compose run --rm backend alembic revision --autogenerate -m "describe the change"
docker compose config                                 # validate the compose file
```
Not set up yet: lint and type-check (Q-006); screenshots (Q-003).

## 3. Layout
- `backend/` — FastAPI app (`app/`), Alembic migrations (`alembic/`), tests (`tests/`), Dockerfile.
- `frontend/` — static HTML, CSS and JS, served by nginx. Pages are plain files: `timetable.html`, `rooms/index.html`, and so on. Shared chrome in `js/layout.js`; tokens in `css/tokens.css`.
- `infra/nginx/` — nginx routing for the frontend (clean URLs, 404, backend proxy).
- `docker-compose.yml`, `.env.example` — the local stack.
- `docs/agents/` — the ledger, this setup's guide and tools. `docs/design/` — UI guardrails.
- `.claude/` — the plan and build skills, and the planner and builder agents.

## 4. Rules for this repo
- Copy `.env.example` to `.env` before the first run. Never commit `.env`.
- Change the schema only with an Alembic revision. Review the generated file before you
  apply it. Never edit a revision that has been applied.
- New endpoints go in `backend/app/routers/`, registered in `backend/app/main.py`.
- Run the tools through `docker compose`, not on the host.

## 5. Release
Not decided: branches, version source, changelog, tags, deploy (Q-002, Q-005). Until
decided: no tags, no releases, no deploys, and only with the user's go.

## 6. Definition of done
- `docker compose run --rm backend pytest` passes.
- `docker compose config` and `docker compose build backend` pass.
- UI changes: until Q-003 is answered, check the page in a browser and name the check in the report.
- New practices recorded as candidate patterns; open points recorded as Q- entries.
