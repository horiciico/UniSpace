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
- After every code change, run all the tests: `node scripts/test-all.mjs` (backend, ETL and
  frontend suites, with the report in `output/test-report.md`). Fix what the change broke.
  If an existing test fails because the new behaviour is intended, update that test to the
  new behaviour and name each updated test in the report. If the code is wrong, fix the code.
  If the test is wrong or you are unsure which side is wrong, stop and ask the user.
  Never delete a test to get green, and never weaken an assertion without saying so.
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

### Every feature (all agents, every time)
After each feature, before you report it done:
1. Add or update the tests the feature needs, then run every suite: `node scripts/test-all.mjs` (backend, ETL and frontend; the backend part includes the i18n key check in `backend/tests/test_i18n.py`). Report the results, including failures.
2. Every new visible text gets an entry in **both** `frontend/i18n/ro.js` and `frontend/i18n/en.js`, used through a `data-i18n`, `data-i18n-attr` or `UniSpaceI18n.t()` key. No text is left hard-coded in one language. Records that come from the backend are not added (D-012).
3. A feature is not done until steps 1 and 2 pass.
4. Log the prompt in `AI_LOG.md` (newest entry first, format at the top of the file): the tool and model, what was asked, what came back, and what was done with it. Only prompts that changed something are logged; questions and clarification requests are not.

## 1. What this repo is
UniSpace: a web platform. A FastAPI backend, a plain HTML/CSS/JS frontend, and a
PostgreSQL database, all run with Docker Compose. Who uses it and what it does is not
defined yet (Q-001).

## 2. Stack and commands
Python 3.12 + FastAPI · HTML/CSS/JS · PostgreSQL 16 + Alembic · Docker Compose.

```bash
cp .env.example .env                                  # first time only; then set the values
docker compose up --build                             # db, backend (:8000), frontend (:8080)
node scripts/test-all.mjs                             # all tests: backend, ETL, frontend (report in output/)
docker compose run --rm backend pytest                # backend tests only
docker compose run --rm backend alembic upgrade head  # apply migrations
docker compose run --rm backend alembic revision --autogenerate -m "describe the change"
docker compose config                                 # validate the compose file
```
Not set up yet: lint and type-check (Q-006); screenshots (Q-003).

## 3. Layout
- `backend/` — FastAPI app (`app/`), Alembic migrations (`alembic/`), tests (`tests/`), Dockerfile.
- `frontend/` — static HTML, CSS and JS, served by nginx. `pages/<role>/` (shared, student, professor, admin), `components/` (page template and shared chrome), `styles/` (tokens, base, one CSS file per component, utilities), `js/` (session service, page scripts), `i18n/` (dictionaries). The full map and the steps to add a page or a component: `docs/agents/ARCHITECTURE.md` → Frontend structure.
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
- `node scripts/test-all.mjs` passes, with every existing test run after the last change.
- UI changes: until Q-003 is answered, check the page in a browser and name the check in the report.
- New practices recorded as candidate patterns; open points recorded as Q- entries.
