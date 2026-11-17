# AI log

A record of the prompts that changed this repo: which tool was used, what was asked,
what came back, and what was done with it. Newest first.

Only prompts that did something are logged. Questions and clarification requests are not.
Each entry follows the same shape:

```
## <YYYY-MM-DD> · <short title>
Tool: <assistant, model, and /command or free prompt>
What I asked: <one or two lines>
What I got: <what the assistant produced>
What I did with it: <kept, changed, rejected, merged; where it went>
```

---

## 2026-11-17 · Database password required; deploy moved to Oracle Cloud; project brief saved
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: make the Postgres password required in compose; change the deploy answer from Vercel to Oracle Cloud; save the course description in the context file.
What I got: `POSTGRES_PASSWORD` has no fallback in `docker-compose.yml` (compose stops with a message if .env does not set it, branch chore/require-db-password). Q-005 now says Oracle Cloud. The Romanian description is saved verbatim in `CONTEXT.md`.
What I did with it: the plan for the Oracle Cloud deploy (domain, HTTPS, production redirect URI, backups) is still to be written. DECISIONS.md was left as it is, as asked.

## 2026-11-17 · Default passwords removed, Google-only sign-in recorded
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: remove the pgAdmin password and the Postgres placeholder from the history and from .env.example; record that sign-in is Google only (no password hashing) and that deploy is on Vercel.
What I got: `.env.example` and the pgAdmin fallback in `docker-compose.yml` cleaned on branch chore/remove-default-passwords (1535bc9). The history was rewritten in a separate mirror clone with git-filter-repo; the secrets are gone from all branches and tags. Ledger: D-013 (Google-only sign-in, approved), Q-005 answered (Vercel).
What I did with it: the rewritten history is not pushed yet, because a force push needs the owner's go. The Vercel answer raises a plan item: the Compose stack, nginx gate and Python backend do not run on Vercel as they are now.

## 2026-11-17 · Frontend file tree refactor (issue #4)
Tool: Claude Code (Haiku 5.5), /plan then /build
What I asked: pages/ with role subfolders, components/ for reusable parts (page template, buttons, the toggle), styles/ for the design and component CSS.
What I got: pages/{shared,student,professor,admin}; components/ (SSI page head, header, language and theme toggles, footer, toast, app entry point); styles/ split per component plus utilities.css and motion.css; inline styles replaced with classes; nginx gate rewritten for the new paths; architecture docs and a Frontend structure section.
What I did with it: committed on refactor/frontend-structure (6e5570c, "Closes #4"). Checked that the 12 pages render byte-identical screenshots before and after. Not pushed; the push was blocked by the permission check.

## 2026-11-17 · RO | EN interface with a language toggle
Tool: Claude Code (Haiku 5.5), /plan then free prompt
What I asked: every visible text in Romanian and English, a RO | EN toggle top right, the language follows the browser, remembered in localStorage, no page reload on switch, and a project rule to run tests and add i18n keys after each feature.
What I got: frontend/i18n/ with a runtime and ro.js / en.js dictionaries (340 keys each); a key test in backend/tests/test_i18n.py; the toggle in the header; the AGENTS.md rule.
What I did with it: pushed and merged as PR #3. Decisions D-011 and D-012 recorded. The test for the 12 pages' text still needs review by a Romanian speaker.

## 2026-11-17 · Stack restarted after the containers stopped
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: "still not working" after a failed start.
What I got: diagnosis that the database was empty and `create_all` ran before the migrations; ran `alembic upgrade head` on the dev database.
What I did with it: no code change in this step. Led to the next entry.

## 2026-11-16 · Startup runs migrations, startup hook removed
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: make `docker compose up --build` rebuild the tables.
What I got: removed `create_all` from `backend/app/main.py` (it broke D-002); the backend command runs `alembic upgrade head` before uvicorn.
What I did with it: kept as uncommitted work; the owner committed it to main afterwards. The down -v path was not run in the session because the permission check blocked deleting the volume.

## 2026-11-16 · Backend crash fixed: typo, wrong import, table names
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: check the docker backend logs, there are errors; then keep the plural table names and fix the calls.
What I got: fixed `_tablename__` typo, the `app.database` import (now `app.db`), foreign keys pointing to the new plural names, and a new Alembic revision renaming six tables.
What I did with it: the owner committed the changes to main. One existing test still asserts the singular table names; it is waiting for approval to change.

## 2026-11-16 · Google sign-in with the invitation rule
Tool: Claude Code (Sonnet 5.5), /plan then /build
What I asked: Google OAuth login with the bouncer rules (university domain auto-provisioned as STUDENT, other accounts need an invitation); login page, logout, role label, admin link; nginx gate for every page.
What I got: `/auth/login`, `/auth/callback`, `/auth/me`, `/auth/admin`, `/auth/logout`; the `invitation` table and `user.google_sub`; an nginx gate using `auth_request`; the login page built from the approved mock.
What I did with it: merged as PR #2. D-009, D-010 and C-002 recorded; Q-007 answered by this work. The real Google round-trip worked on the owner's account.

## 2026-11-11 · Scheduling schema: models and migration
Tool: Claude Code (Sonnet 5.5), /plan then /build
What I asked: SQLAlchemy models and an Alembic migration for users, groups, classrooms, activities and exceptions; an overlap-check approach.
What I got: a plan with seven open questions, then the models, the migration (with a generated int4range column and a GiST index), and six tests.
What I did with it: merged as PR #1. Decisions D-006 to D-008 recorded; Q-008 opened for the semester setup.
