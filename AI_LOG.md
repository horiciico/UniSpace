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

## 2026-11-22 · Free rooms page: a faculty must be chosen first
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: on the free now page, no rooms until a faculty is selected, and prompt the user to select one.
What I got: the faculty list starts on a placeholder ("Alege o facultate") and the "All faculties" option is removed; without a faculty no request is made, the list is empty and the status line asks for a faculty (`free.pickFaculty`). The select gets the focus on load. Dictionaries updated (`free.allFaculties` replaced by `free.chooseFaculty` and `free.pickFaculty`). Backend unchanged (faculty stays optional in the API). Backend tests 75 passed. Browser check: no faculty gives no cards and the prompt; a faculty with a custom interval gives 18 rooms; no console errors.
What I did with it: not committed.

## 2026-11-22 · The after-21:10 closure applies to the current day only
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: clarify that no booking is closed after 21:10 for later days; only the free-now list for today is empty after 21:10.
What I got: the backend refused any start-only search after 21:10, whatever the date. Now only the current day is refused (400); a later day returns no rooms for a start-only search at that time, and module intervals on any day work. Test added. Backend tests 75 passed. The frontend needed no change.
What I did with it: not committed.

## 2026-11-22 · Free now uses the exact local time; bookings are whole modules; nothing after 21:10
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: free now calculates the exact local time on each visit; the last module ends at 21:10 and nothing is bookable after it; a room is booked for one or more whole 1.5-hour modules.
What I got: planning.py: MODULES table, `booking_window` (no times: the module containing now, or the next during a break; a start only: the same from that time; start and end: must be module boundaries; after 21:10: refused). The free endpoint uses that window; `free_until` is never null (21:10 when nothing follows). frontend/js/modules.js shares the table with the grid. Free-now sends the exact local time on load, on tab entry and when the page is shown again; after 21:10 it shows a message and does not search. Custom intervals are chosen by module. Messages added to ro/en; `free.freeRestOfDay` removed. Tests: backend 74 passed. Browser check at 21:27 (after the last module): the message, the module pickers, the range message, a custom search; no console errors. Daytime behaviour checked by the backend tests only. C-003 updated (user request).
What I did with it: not committed.

## 2026-11-22 · Timetable follows the module schedule (08:00 to 21:10)
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: the timetable follows the module convention: 90-minute modules with a 10-minute break, 08:00-09:30 up to 19:40-21:10.
What I got: grid.js: 79 ten-minute rows, 08:00 to 21:10; the time column shows each module's range; day lines fall at module starts (every 100 minutes). Activities keep their real times. Real data: 5,673 activities start and end on the module grid; 479 (about 8%) do not (45 to 60 minute slots such as 08:10-09:00), and they are shown at their recorded times. Browser check: one group timetable, 14 blocks, eight module rows, Sunday column; no console errors checked on this page.
What I did with it: not committed. The 479 off-grid activities are open: keep the recorded times or snap them to modules.

## 2026-11-22 · Sunday column on the timetable
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: add Sunday to the timetable.
What I got: grid.js draws seven day columns (Monday to Sunday); the timetable CSS has seven columns; `day.sun` added to ro.js ("Dum") and en.js ("Sun"). The API already returned Sunday items, so no backend change. Backend tests 71 passed; both scripts pass a syntax check.
What I did with it: not committed. Not re-checked in the browser.

## 2026-11-22 · Timetable shows one planning unit per week
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: the timetable page shows the schedule only for the corresponding planning unit.
What I got: `/api/schedule` takes an optional `faculty_id`; with it, only that faculty's unit covering the week is drawn; without it, the unit most of the entity's recurring activities use in weeks covering this one. One-off rows are always shown. The week number comes from that unit only; the old fallback to any faculty's unit is removed. `timetable.js` sends the selected faculty (not `campus`). Real data: a room with activities from two faculties now shows 18 (ing) or 21 (sti) activities instead of a mix. Tests: backend 71 passed (3 new). C-003 updated (user request).
What I did with it: not committed. Free rooms still consider every unit; not changed, as the request was about the timetable.

## 2026-11-22 · /api/* gated by nginx; endpoints recorded as C-003
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: record the endpoints, and gate the /api/* routes as well (signed in only).
What I got: infra/nginx/default.conf: `location ^~ /api/` now runs auth_request on /auth/me (signed out: plain 401); `/health` stays a public exact location. Checked with curl: signed out 401 on /api/faculties and /api/schedule, signed in 200, /health 200; the temporary user was removed. CONTRACTS.md: C-003 (approved, confirmed 2026-11-22) lists every route, its parameters, response shape and errors. ARCHITECTURE.md: the boundary note now says /api/ is signed in only. frontend/js/api.js: a 401 sends the visitor to /login. Ledger lint passes.
What I did with it: not committed. D-010 (proposed) already covers the gate; its promotion is left to the user.

## 2026-11-22 · Liber acum and Orar: schema, API, both pages (branch feat/liber-acum-timetable)
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: build the two pages, Liber acum (free rooms) and Orar (weekly timetable), with the endpoints from the spec, on a separate branch, with the i18n dictionaries.
What I got: migration d41f7c2a9e10: `activity_groups` (every group of a merged activity; backfilled from `activities.group_id`), `classrooms.is_bookable` (default true) and `classrooms.is_field_verified` (default false). Endpoints: `GET /api/classrooms/free`, `GET /api/classrooms`, `GET /api/schedule`, `GET /api/faculties`, `GET /api/groups`, `GET /api/professors`. Week parity is counted per planning unit (D-014). The ETL loader links every study group of a merged slot. Frontend: `pages/student/rooms/free.html`, `pages/student/timetable.html`, `js/api.js`, `js/grid.js`, `js/pages/free.js`, `js/pages/timetable.js`, `styles/components/room-card.css`; ro/en keys added, 3 unused keys removed. Full ETL run against the ULBS API: 6,145 activities, 7,242 group links, 655 activities with several groups. Tests: backend 68 passed (new `test_timetable_api.py`), ETL 66 passed (new merged-group test). Browser check on the running stack (headless Edge over DevTools, temporary signed-in user, removed afterwards): both pages, both languages, no console errors.
What I did with it: branch `feat/liber-acum-timetable` from `main`. Not committed. Open items are listed in the report: nginx does not gate `/api/`, and the iCal button is hidden.

## 2026-11-22 · Open questions answered (Q-002, Q-013, Q-014); Q-003, Q-006, Q-008 deferred
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: address the open questions.
What I got: Q-002: `main` is the release and deploy branch (version scheme still open). Q-013: the proposed answer confirmed (date 2026-11-22). Q-014: the admin selects the scope; the meaning of "whole duration" is still open. Q-003: after a frontend and an end-to-end flow exist. Q-006 and Q-008: to be configured later.
What I did with it: ledger updated; lint passes. Not committed.

## 2026-11-22 · ETL chapter closed: open items resolved
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: resolve every open item so the ETL chapter can close.
What I got: (1) fresh-database run: a new empty database, the full pipeline (migrations and all four steps), 6,152 activities inserted, the same unparsed and warning cases; the test database was dropped afterwards. (2) The 2 rows that changed on the first load are explained: one merged an unlinked entry (professor names joined), one merged a missing-type entry (type LAB to COURSE, by the precedence rule). (3) test_auth: the count covered every user in the table, so it failed whenever a real account existed; it now counts only the test's own account. (4) test_models: table names and the renamed class updated. (5) data/ added to .gitignore (generated, re-creatable). (6) ARCHITECTURE.md: ETL section added. Backend 48 passed; ETL 64 passed. Ledger lint passes.
What I did with it: scheduling is not set up; it depends on the deploy plan (Q-005) and is left open. Local commit on feat/etl-faculties, not pushed.

## 2026-11-22 · Loader decisions: unlinked entries, Optional as Course, missing type warned
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: entries with no study group are stored with no group; `Optional` and entries with no type map to Course, and the missing-type entry gets a warning; entries with no time stay unparsed with the exact reason.
What I got: loader updated; tests 64 passed. Full load: 14 activities inserted (entries with no group), 2 updated (existing rows changed; cause not yet checked), 6,152 unchanged on the second run. Unparsed: 21 (13 empty time slots, 8 with no time slots). Warnings: 1 entry with no type, stored as Course.
What I did with it: not committed. Open: the cause of the 2 updated rows is unchecked.

## 2026-11-22 · ETL step 4: loader writes schedules to the database
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: step 4: load the schedule files into classrooms, student groups and activities, idempotently, with the rules from the answers: one row per (room, day, parity, start, end); name "Didactic Activity"; priority 5; capacity null when unknown; entries without a room (and online entries) not stored; admin-edited rows never changed.
What I got: migration bc1469b9b255 (classrooms.capacity nullable; classrooms.external_id unique on its own; student_groups.external_id unique). Models updated. `etl/loader.py`: parse, merge contiguous time slots, group, room fetch (unfiltered list plus `?faculty=` per faculty, paginated: 565 rooms), upserts, stale-row removal (kept if an exception or change request points at the row), report. Wired into the downloader as `--step load`; `--step all` now runs steps 1 to 4.
What I did with it: ETL tests 60 passed (loader rules and database behaviour). Full load: 9 files, 6,917 entries, 6,138 activities stored (all priority 5, none admin-edited), 374 classrooms (113 with unknown capacity, 7 rooms taken from the schedule because the rooms list does not have them), 855 student groups. A second run inserted and deleted nothing (6,138 unchanged). Unparsed: 42 entries with no study formation id, 21 with no usable time, 8 with an activity type outside the mapping. Backend: 42 passed; test_auth fails as before; test_models does not import. Not committed.

## 2026-11-21 · One command runs the whole ETL pipeline
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: a single command that starts the pipeline for all faculties.
What I got: the default `--step` is now `all`, which runs steps 1 to 3. `--step sync` and `--step schedules` remain for partial runs, and `--faculty` works for all steps. The docstring shows the commands.
What I did with it: ETL tests pass (28, including a test for the defaults). The command `docker compose --profile etl run --rm etl` ran all three steps for the 9 faculties in about 16 s: 9 planning units stored, 9 schedule files written. Not committed.

## 2026-11-19 · ETL step 3: weekly schedule files in data/schedules
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: step 3: read the current planning units from the database, download `GET /api/faculties/{code}/schedule/weekly?planning_time_unit_id=...` with the given timeouts and a semaphore of 2, save each as `data/schedules/{name}_{code}.json` in an envelope (faculty, planning unit, fetched_at, raw schedule), with per-faculty error handling, a CLI filter and a summary. No parser, no endpoints.
What I got: `download_schedules` with `load_current_units`, `build_envelope`, `fetch_weekly_schedule`, `write_json_atomic` (temporary file, then rename), and a CLI flag `--step schedules` (default `--step sync` keeps steps 1 and 2). The compose `etl` service mounts `./data` at `/app/data`.
What I did with it: the probe for sti: HTTP 200, 0.9 s, 666 KB compact. The schedule payload is `{success, message, data}`, with `data` keyed by day name (Luni, Marti, Miercuri, Joi, Vineri), 510 items for sti. The live run saved all 9 faculties in 0.6 to 3.7 s each; sizes 506 KB to 3.6 MB pretty-printed (`indent=2`, under the 5 MB limit). Tests: ETL 26 passed. Not committed. `data/` is untracked and not in `.gitignore` (flagged to the user).

## 2026-11-19 · ETL step 2: active planning unit per faculty
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: Step 2 of the ETL: model and migration for `planning_time_units` (UUID id, faculty FK with cascade, integer external_id, year, name, display_name, type, dates, is_current, unique (faculty, external_id)); fetch the active semester or module per faculty (semester first, then module; isCurrent, date fallback); upsert with a semaphore of 3 and per-faculty error handling; a summary table; a `--faculty` CLI flag.
What I got: migration `a9cda1e005be` (autogenerated, then fixed: USING cast for text to integer, named FK for the downgrade). Model updated. ETL: `fetch_planning_units`, `pick_current`, `fetch_active_planning_unit`, `upsert_planning_unit`, `sync_planning_units`, `format_summary`, and a CLI with `--faculty` and `--year`. Live check: `active_only=true` returned Modul 2 (isCurrent false) and dropped Modul 1 (isCurrent true), so the code sends `active_only=false` and selects by isCurrent locally. Expected result for sti: external_id 12, Modul 1, module, confirmed.
What I did with it: the live run stored one current unit for each of the 9 faculties; a second run left 9 rows. Tests: ETL 17 passed (selection, fetch order, upsert idempotence, one current per faculty). Backend 42 passed; `test_auth::test_second_login_does_not_duplicate` still fails, as before. Fixed my own backend tests, which used the code "dre" (a real row now). Not committed.

## 2026-11-19 · ETL stores faculties in the database
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: make sure the faculties GET in the ETL populates the faculties table.
What I got: `etl/downloader.py` maps each API faculty (`id` -> `code`, `name`) and upserts into `faculties` by code (`upsert_faculties`). The ETL image now builds from the repo root with the backend code and requirements, runs `alembic upgrade head`, then the pipeline. The compose `etl` service gets `.env` and `DATABASE_URL`, and waits for `db`.
What I did with it: tests in `etl/tests/test_faculties_db.py` (3 DB tests rolled back, plus the mapping test) and the 4 fetch tests: 7 pass in the etl image. The live run stored 9 faculties; a second run left 9 rows. Not committed. Note: `docker compose run` does not rebuild the image, so run `docker compose --profile etl build etl` after ETL changes.

## 2026-11-19 · Schema for planning units, ETL binding, exceptions and change requests
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: the user approved the four decisions (D-014 to D-017) with "ok".
What I got: decisions added to DECISIONS.md (approved, confirmed 2026-11-19). Alembic revision 6a3817a9edb2: tables `faculties`, `planning_time_units`, `rule_change_requests`; `classrooms` gets `faculty_id`, `external_id`; `activities` gets `planning_time_unit_id`, `external_id`, `is_manually_modified`, `specific_date`, `professor_name`, with a unique (unit, external_id) and a weekday CHECK; `event_exceptions` renamed to `activity_exceptions` and given new times, reason and author. Models updated, `event_exception.py` removed, `activity_exception.py` added. New tests in `backend/tests/test_planning.py` (11 tests).
What I did with it: `off_limits` is NOT built (Q-014 open). `test_models.py` is not updated, so it fails at import (the old `EventException` name) and its table-set assertion is stale. Needs the user's OK. Checks: new tests pass; the migration downgrades and re-upgrades. `test_auth.py::test_second_login_does_not_duplicate` was already failing and is not investigated. Not committed.

## 2026-11-19 · Open questions answered in detail; index rebuilt
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: the user answered the open questions in detail (parity mapping, API format, id types, off-limits marks, faculty scope, permanent changes, sign-in, roles, design board).
What I got: `OPEN-QUESTIONS.md` updated. Answered: Q-001, Q-004, Q-007, Q-009, Q-010, Q-011, Q-012. Parity mapping recorded in Q-013 (0 = ALL, 1 = ODD, 2 = EVEN). New open questions: Q-013 (ULBS JSON format, to be discovered together), Q-014 (scope of a day-level off-limits mark). Q-002 has a rephrased version because the user did not understand it. Lint passes.
What I did with it: ledger only. The decision proposals (parity, ETL sync, one-off and permanent changes, off-limits table) wait for the user's OK. Not committed.

## 2026-11-19 · Schema questions answered; ledger updated
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: (answers to the schema questions) keep `activities`, add planning unit link, external_id, is_manually_modified, specific_date; rename `event_exceptions` to `activity_exceptions`; keep day_of_week 1-7 and the status names; parity explained by week (ODD/EVEN/ALL); the API returns room capacity; add a faculties table; one-off changes by the professor, permanent ones by an admin request; the API gives the active period, and the admin can mark days or rooms off limits.
What I got: `OPEN-QUESTIONS.md`: Q-008 has the answer (partly: the active period and parity; holidays and inverted weeks still open); new Q-010 (off-limits model), Q-011 (all nine faculties or only dre), Q-012 (request table or direct edit). Ledger lint passes.
What I did with it: ledger only, no code or migration yet. Decision PROPOSALS for parity, ETL sync and one-off or permanent changes are waiting for the user's OK. Not committed.

## 2026-11-19 · ETL runs as an opt-in container (profile etl)
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: a way to start the ETL pipeline, for now only the faculties part, without it starting on every `docker compose up`.
What I got: `etl/Dockerfile` (python:3.12-slim, httpx, runs `python -m etl.downloader`) and an `etl` service in `docker-compose.yml` with `profiles: ["etl"]`. Run with `docker compose --profile etl run --rm etl`.
What I did with it: `docker compose config` passes. The default service list is unchanged (db, backend, frontend, pgadmin). The container run printed 9 faculties. Not committed.

## 2026-11-19 · ETL step 1: fetch and check the faculties endpoint
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: create branch for the ETL downloader; add etl/downloader.py with an async fetch_faculties() (httpx, 30s timeout, raise_for_status) and a __main__ block that prints the top-level keys, the count and the first faculty; show the list of faculties with their ids.
What I got: GET https://schedule.ulbsibiu.ro/api/faculties returns {"success", "message", "data"} with 9 faculties; each has id (e.g. "dre"), name, connection ("faculty_dre"), dean, dean_email. httpx is already in backend/requirements.txt (>=0.27), so no dependency was added.
What I did with it: branch feat/etl-faculties (from main). Added etl/__init__.py, etl/downloader.py and etl/tests/test_downloader.py (4 tests with httpx.MockTransport; pass in a python:3.12-slim container). The ETL is not in the backend image, so it is not covered by `docker compose run --rm backend pytest`. Not committed.

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
