# AI log

A record of the prompts that changed this repo: which tool was used, what was asked,
what came back, and what was done with it. Newest first.

Only prompts that did something are logged. Questions and clarification requests are not.
Each entry follows the same shape:

```

## 2026-11-24 · Student room booking, step 2: booking endpoints and conflict check
Tool: Claude Code (Haiku 5.5), /plan then build
What I asked: after the defaults were confirmed, build POST /api/bookings (conflict check against recurring activities and approved bookings, 409 on a clash), GET /api/bookings/my, DELETE /api/bookings/{id} (owner only, pending only, soft cancel), and Free Now fields. Decisions from the user: any signed-in role books; admin bookings are approved at once; professors wait for approval.
What I got:
- New router `backend/app/routers/bookings.py`, registered in `backend/app/main.py`.
- `backend/app/routers/classrooms.py`: the free-room search counts approved bookings and returns `start_time` and `end_time`; `free_until` is unchanged.
- Tests: `backend/tests/test_bookings_api.py` (30 new).
- Contract C-005 added; C-003 change note added; Q-017 opened for cancelled and moved occurrences, which the shared helper ignores.
What I did with it: on branch `feature/student-room-booking`. Backend 142 passed, ETL 113, frontend 252. `docker compose config` and `docker compose build backend` pass. Not committed or pushed. The Bookings page move to `pages/shared` is not done in this step.

## 2026-11-24 · Booking block outlined in the timetable
Tool: Claude Code (Haiku 5.5), build
What I asked: an approved booking's right edge was lost in the grid lines; add highlighting so the card reads as its own block.
What I got: `.tt-block--booking` in timetable.css now has a full 1px accent outline (4px on the left, as other blocks) and the tinted hover token as its background.
What I did with it: CSS only, no test change. Checked in light and dark headless Chrome; screenshots refreshed in docs/design/screens. Not committed or pushed.

## 2026-11-24 · Free-slot polish in the room view
Tool: Claude Code (Haiku 5.5), build
What I asked: make the room-view free slots clean and modern: no border or text at rest (a faint plus), a 150ms hover with a tint, border and a + Book label; past slots blank and dimmed; a muted helper line above the grid for a bookable room.
What I got:
- Tokens: `--color-slot-hover-bg`, `--color-slot-hover-border`, `--color-slot-icon` in tokens.css (all three theme blocks). The hover values are your rgba values, now tokens (DESIGN.md: no raw colours in components).
- `frontend/styles/components/timetable.css`: resting, hover and focus, past, and hint styles. `grid.js`: plus and label spans; past slots blank. `timetable.js`: label "+ Book", past name "Past", helper line `#tt-hint` shown for a bookable room.
- i18n: bookings.bookSlotShort, timetable.bookHint; bookings.bookSlot removed (unused).
- Tests updated for the new structure (grid-free-slots, timetable-free-slots) and the helper line checked.
- Screenshots refreshed: docs/design/screens/DS-unispace-timetable-grid.{light,dark}.png (resting state only; hover not captured).
What I did with it: on branch `feature/student-room-booking`. All suites pass: 565 (backend 152, ETL 113, frontend 300). Not committed or pushed.

## 2026-11-24 · Approved bookings shown in the room timetable
Tool: Claude Code (Haiku 5.5), build
What I asked: once approved, a booking should appear in the timetable.
What I got:
- `backend/app/routers/schedule.py`: with room_id, approved bookings of the week are added as BOOKING items (pending and cancelled ones are not).
- Frontend: BOOKING kind in `grid.js` and `timetable.js` (label Booking / Rezervare, block `tt-block--booking`, legend swatch), details show priority "Not specified" when null.
- Tests: 2 backend tests in `test_bookings_api.py`; `frontend/tests/unit/timetable-bookings.test.js` (2).
- Contract C-003 change note (4).
What I did with it: on branch `feature/student-room-booking`. Backend 152, ETL 113, frontend 300 (565 total). Not committed or pushed. The timetable screenshots in docs/design/screens predate this change and are not refreshed.

## 2026-11-24 · Q-017 confirmed: cancelled and moved occurrences in the shared helper
Tool: Claude Code (Haiku 5.5), build
What I asked: the user confirmed the proposed answer to Q-017 (a cancelled occurrence does not block; a moved one blocks its new time).
What I got:
- `backend/app/planning.py`: `occurrences()` drops CANCELLED activities and cancelled occurrences, applies moves (new date and time, found from either date), and returns each occurrence with its own `start_time`, `end_time` and `day`.
- `backend/app/routers/schedule.py`, `classrooms.py`, `bookings.py`: use the occurrence's day and times; the booking check's own cancel handling is removed (the helper does it).
- Tests: `backend/tests/test_occurrences.py` (new, 6); `test_bookings_api.py` gets a moved-course test; `test_free_now_reports_the_searched_window` now expects `free_until` 21:10 (intended by Q-017).
- Ledger: Q-017 answered; Q-018 opened for a move to another room; C-003 change note.
What I did with it: on branch `feature/student-room-booking`. Backend 150, ETL 113, frontend 298. Timetable behaviour changed too (it uses the same helper): cancelled classes no longer show; moved ones show at their new time. Not committed or pushed.

## 2026-11-24 · Student room booking, steps 3 and 4: Bookings page, room view and Free Now actions
Tool: Claude Code (Haiku 5.5), build
What I asked: after the mocks were confirmed and Q-003 closed, build the Bookings page (moved to pages/shared, real data) and the two entry points: free slots in the room view of a bookable room, and a Book action on each Free Now card. Screenshots in light and dark.
What I got:
- Bookings page: `frontend/pages/shared/bookings.html` (moved from pages/student/bookings), script `frontend/js/pages/bookings.js`, nginx route updated.
- Room view: `frontend/js/grid.js` draws free modules as buttons; `frontend/js/pages/timetable.js` builds them for bookable rooms only; past modules disabled.
- Free Now: `frontend/js/pages/free.js` adds a Book action per card.
- Styles: `.tt-free` (timetable.css), `.room-card-wrap` (room-card.css), `.booking-list`, `.booking-meta` (tables-and-lists.css).
- i18n: bookings.* keys rewritten in ro.js and en.js; unused status.requested removed; bookings.projector and bookings.outlets kept for the room pages.
- Tests: bookings-page.test.js, bookings-page-without-list.test.js, grid-free-slots.test.js, timetable-free-slots.test.js; free.test.js and bookings.test.js extended.
- Bug found by the tests and fixed: changing the faculty kept the room chosen from the link.
- Screenshots (headless Chrome, PATTERN-007, temporary student and bookings, removed afterwards): docs/design/screens/DS-unispace-{bookings,timetable-grid,free-rooms}.{light,dark}.png. Registry entries are implemented.
What I did with it: on branch `feature/student-room-booking`. Frontend 298 tests with the 100% gate, backend 143, ETL 113. Not committed or pushed.

## 2026-11-24 · Student room booking, step 2 follow-up: campus null, D-023, booking data layer and UI drafts
Tool: Claude Code (Haiku 5.5), build and /plan
What I asked: return null (not the text Campus) for a room with no faculty (D-012); record D-023 (approved); build the data layer for steps 3 and 4 and draw the UI mocks.
What I got:
- Backend: `faculty_name` is null for a campus room; test added; C-005 updated.
- D-023 added as approved; the ledger index updated.
- `frontend/js/api.js`: myBookings, createBooking, cancelBooking (send helper now shared with PUT); tests in `api.test.js`.
- `frontend/js/bookings.js` (new, pure helpers): the Bookings link and its reading, status labels; tests in `frontend/tests/unit/bookings.test.js`.
- i18n: `bookings.statusPending` and `bookings.statusRejected` in ro.js and en.js.
- Mocks (draft, not built): `docs/design/mocks/DS-unispace-bookings.html`, `DS-unispace-timetable-grid.html`, `DS-unispace-free-rooms.html`; registry entries set to draft.
What I did with it: on branch `feature/student-room-booking`. The screens (steps 3 and 4) are not built: DESIGN.md requires a confirmed mock first. All suites pass (backend 143, ETL 113, frontend 259). Not committed or pushed.

## 2026-11-24 · Student room booking, step 1: bookings table
Tool: Claude Code (Haiku 5.5), /plan then build
What I asked: after the plan was approved, add the `bookings` table (UUID id, user and classroom foreign keys, date, start and end time, title VARCHAR(255), native `booking_status` enum, created_at) with an Alembic revision; update the Activity docstring and D-015 so bookings are not activities.
What I got:
- New model `backend/app/models/booking.py`; `BookingStatus` in `enums.py`; exports in `models/__init__.py`.
- Revision `backend/alembic/versions/20261123_58cba83b6174_bookings_table.py`. Downgrade also drops the enum type, which autogenerate left out.
- Tests in `backend/tests/test_models.py` (5 new; the table-set assertion now includes `bookings`).
- D-015 now says student bookings live in `bookings`; its Confirmed date is 2026-11-24.
What I did with it: on branch `feature/student-room-booking`. Upgrade, downgrade and re-upgrade checked against the compose database; `alembic check` reports no differences. All suites pass (backend 112, ETL 113, frontend 252). Nothing is committed or pushed.

## 2026-11-24 · CI workflow split into 3 parallel test suites
Tool: Antigravity, free prompt
What I asked: modify GitHub workflows to run on push and PR; divide the test suite into the 3 configured test suites (backend, ETL, frontend) and run all 3.
What I got:
- Updated `.github/workflows/tests.yml` to run on `push` and `pull_request` (plus `workflow_dispatch`).
- Split the test execution into 3 parallel jobs (`Backend Tests`, `ETL Tests`, `Frontend Tests`) using a matrix with `fail-fast: false`.
- Updated `scripts/test-all.mjs` to support an optional suite argument (`node scripts/test-all.mjs [backend | etl | frontend]`) while preserving full run behavior when invoked without arguments.
- Updated artifact uploads to save separate reports (`test-report-backend`, `test-report-etl`, `test-report-frontend`).
What I did with it: On branch `fix/header-row-swap`. Tested argument handling and workflow configuration.

## 2026-11-24 · Header listener cleanup and Google picture removal synchronization
Tool: Antigravity, free prompt
What I asked: clean up document-level click and keydown listeners across header rebuilds to prevent detached DOM retention and duplicate handling; update Google sign-in to assign the picture claim unconditionally on every login so omitting the picture claim clears any previous avatar URL.
What I got:
- In `backend/app/auth.py`: updated `resolve_user` to unconditionally set `user.picture = picture`, correctly clearing the avatar when Google omits the claim on subsequent logins. Added regression test `test_google_login_clears_picture_when_claim_is_omitted` in `backend/tests/test_auth.py`.
- In `frontend/components/header.js`: maintained references to the active document-level `click` and `keydown` handlers (`activeCloseMenu`, `activeKeyDown`) and added `teardownMenuListeners()` called at the start of `UI.buildHeader` and exposed on `UI.teardownHeader`.
- In `frontend/tests/unit/header.test.js`: added unit test asserting listener removal across header rebuilds. 100% frontend coverage maintained.
What I did with it: On branch `fix/header-row-swap`. Tests passing across backend and frontend suites.

## 2026-11-24 · Header profile dropdown and user picture
Tool: Antigravity, free prompt
What I asked: remove the menu button; add the user profile picture obtained through Google OAuth in the top right corner; move the theme and logout buttons from the header into a dropdown unfolding under the profile picture on click, along with routing to a placeholder settings page. Keep button functionalities intact.
What I got:
- Added `picture` column to `users` (String 1024, nullable) with Alembic migration `e5c1a7d890b2`.
- Updated `resolve_user` and `UserOut` to store and expose Google OAuth `picture` claim.
- Updated `CONTRACTS.md` (C-002).
- Removed `.nav-toggle` and "Menu" button, keeping navigation directly accessible on the second row.
- Replaced header theme toggle and logout in the header bar with an interactive profile menu trigger and dropdown displaying the user's avatar (or initial placeholder), containing the theme button, a placeholder `/settings` route, and the logout button.
- Added `/settings` route in `infra/nginx/default.conf` and `frontend/pages/shared/settings.html`.
- Added required keys to `ro.js` and `en.js` (`header.profileMenu`, `header.settings`, `settings.title`, `settings.heading`, `settings.lead`).
- Updated unit tests in `header.test.js` to cover dropdown unfolding, outside clicks, and keyboard Escape behavior.
What I did with it: On branch `fix/header-row-swap`. Tests pass across suites.

## 2026-11-23 · Student onboarding: faculty and study formation on first sign-in
Tool: Claude Code (Haiku 5.5), /plan then /build, free prompt for the approval
What I asked: on a student's first sign-in, a blocking dialog asks for the faculty (a dropdown of all faculties), then for the study formation of that faculty; both are stored on the user row in nullable columns that are filled only for students. Branch feat/student-onboarding. The user approved the plan and skipped the design mock.
What I got: migration b0f9c8035187 (two nullable columns, FKs with ON DELETE SET NULL; autogenerated, reviewed); `User.needs_onboarding`; `GET /auth/me` and the sign-in responses carry the fields; `PUT /api/me/study-profile` (student only, the formation must belong to the faculty, 403 and 422 otherwise); the formation query moved into `faculty_groups` and shared with `/api/groups`; `frontend/components/onboarding.js` and its CSS; `api.js` gained a PUT helper; 14 onboarding keys in ro.js and en.js; api.js added to the shared head (found in a browser check: the dialog failed silently without it). Tests: backend 105, ETL 113, frontend 246, 464 in all; frontend coverage 100%. Browser check (headless Chrome, Q-003 still open, ad-hoc): light, dark and the formation step looked right; a PUT through nginx saved, /auth/me showed the choice, another faculty's formation returned 422, a signed-out PUT 401. A throwaway student row was used for the check and deleted afterwards.
What I did with it: ledger: D-022 added (approved, confirmed 2026-11-23); C-004 added; C-002 changed (/auth/me fields); ARCHITECTURE updated; lint passes. The seeder scripts/seeders/seed_demo_course.py now takes --professor-email, so the address is no longer in the file. Test-key prefix "onboarding" added to backend/tests/test_i18n.py. Committed on feat/student-onboarding; not pushed.

## <YYYY-MM-DD> · <short title>
Tool: <assistant, model, and /command or free prompt>
What I asked: <one or two lines>
What I got: <what the assistant produced>
What I did with it: <kept, changed, rejected, merged; where it went>
```

---

## 2026-11-23 · Professors ETL, step 1: professors table and professor_id columns
Tool: Claude Code (Haiku 5.5), free prompt, with the user's answers to the plan questions
What I asked: step 1 of the professors pipeline. A professors reference table (id from the ULBS API, name, normalized unique email), a nullable indexed `activities.professor_id` filled by the schedule loader from `professorId` (no foreign key), and a nullable `users.professor_id`. The user's answers: the professor list comes from an API in step 2; merged rows take the professor only when all entries agree; the smaller choices are accepted. The user also said the professor list will drive an automatic PROFESSOR role, Google sign-in stays, and the admin gets a separate sign-in with hardcoded credentials (not built; see the open proposal).
What I got: `backend/app/models/professor.py`; the two columns; migration `fb4b7e6ca5da` (autogenerated, reviewed, additive); loader change that reads `professorId` and sets `professor_id` only when every merged entry agrees; tests first in backend and ETL. `node scripts/test-all.mjs`: backend 77 passed, ETL 70 passed, frontend 207 passed. `docker compose config` and `docker compose build backend` pass. Alembic is at the new head and existing user rows are kept.
What I did with it: on branch `feat/professors-etl`, not committed or pushed. Q-015 added as answered (email source from an API, step 2). Pending a PROPOSAL, not built: the automatic PROFESSOR role from the list (changes Q-009 and C-002), and the admin hardcoded-credentials sign-in (conflicts with D-013 and the rule against writing secrets into files).

## 2026-11-23 · ETL refactor: one folder per pipeline
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: put each ETL pipeline in its own folder under etl/ with its scripts and tests (etl/schedule/, etl/professors/), not in one shared layout.
What I got: the schedule pipeline (downloader.py, loader.py and their tests) moved with git mv into etl/schedule/; etl/professors/ created with a placeholder __init__.py (its code comes with Step 2). Imports, the Dockerfile entrypoint (python -m etl.schedule.downloader), the test-all path (etl) and ARCHITECTURE.md updated. No assertions changed. node scripts/test-all.mjs: backend 77, ETL 70, frontend 207 passed; the ETL image builds and its entrypoint runs.
What I did with it: not committed or pushed.

## 2026-11-23 · Demo seeder: "Demo Course" in IE102 on Friday for the ing faculty
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: a seeder under scripts/seeders that adds "Demo Course" (Curs Demo) for the ing faculty on Friday in an open slot of room IE102, group "test", with the professor address the user gave, so the app can be checked end to end.
What I got: scripts/seeders/seed_demo_course.py. It picks a random module that no activity of the room overlaps, reuses or creates the group "test" and the professor row, links the activity to the current planning unit, and is safe to re-run. Run once: added Friday 16:20-17:50 in IE102 (parity ALL, type COURSE, priority 5, status APPROVED). A second run added nothing. An SQL check found no other IE102 activity overlapping that slot.
What I did with it: the data is in the local database only. The seeder is not in test-all. The professor address is written in the seeder file as the user asked, which is personal data in a file: move it to an argument or .env before committing that file. Not committed or pushed.

## 2026-11-23 · Coverage of the new code: tests for the professors pipeline and the sign-in race
Tool: Claude Code (Haiku 5.5), free prompt asking whether the work is complete
What I asked: whether anything else is left, and whether the work can be called complete.
What I got: measured coverage with pytest-cov. The new code had gaps: the sign-in path for a refused write (auth.py lines 99-102), read_documents, load_professors, the professors CLI and the extract error paths. Added tests for each: backend/tests/test_auth_race.py, etl/professors/tests/test_professors_extract_errors.py, test_professors_load_files.py, test_professors_load_run.py, test_professors_cli_run.py. Result: app/auth.py 100%; professors pipeline 100% except the __main__ guard. node scripts/test-all.mjs: backend 95, ETL 113, frontend 223 passed, 431 in total.
What I did with it: not committed or pushed. The schedule pipeline (loader, sync, download, cli) and a few backend lines (planning.py, schedule router, db.py) were already under 100% before this session and are not covered by this change; they are listed for a decision, not fixed here.

## 2026-11-23 · Step 4: admin login modal built (mock confirmed)
Tool: Claude Code (Haiku 5.5), free prompt with the confirmed mock DS-unispace-admin-login
What I asked: the discreet "Acces administrator" link on the login page and the modal with username and password, posting to /auth/admin-login, with an inline error on 401 and entry to the admin state on success.
What I got: frontend/components/admin-login.js (modal, focus trap, Escape, busy state, 401 and failure messages, re-translation on language change), frontend/styles/components/admin-login.css (tokens only), the modal and link in frontend/pages/shared/login.html, eight admin.* keys in ro.js and en.js, frontend/tests/unit/admin-login.test.js (16 tests). Coverage for admin-login.js is 100% on all four measures. Screenshots (light and dark) of the link page and of the open modal, saved as docs/design/screens/DS-unispace-admin-login.* and DS-unispace-login.* (the login screen changed); the registry entry is implemented.
Tests: node scripts/test-all.mjs: backend 94, ETL 99, frontend 223 passed, 416 in total. The first frontend run had one failure (the opener was taken from the focused element, which a click does not set); fixed by recording the link itself.
What I did with it: the endpoint is /auth/admin-login, as approved in Step 3 (nginx gates /api/). Not committed or pushed. Not checked: a real sign-in with the admin credentials in a browser, because .env has no ADMIN_USERNAME or ADMIN_PASSWORD set.

## 2026-11-23 · Step 4: admin login mock (waiting for confirmation)
Tool: Claude Code (Haiku 5.5), free prompt with the Step 4 brief
What I asked: a discreet "Acces administrator" link on the login page that opens a modal with username and password, posts to the admin sign-in, shows an inline error on 401, and enters the admin state on success.
What I got: docs/design/mocks/DS-unispace-admin-login.html (draft, three states: link, modal, 401 error) and a registry entry DS-unispace-admin-login with status draft. The brief's path /api/auth/admin-login is replaced by /auth/admin-login, as approved for Step 3, because nginx gates /api/ for signed-out visitors.
What I did with it: no frontend code yet. DESIGN.md requires the user to confirm a new screen element before it is built. Not committed or pushed.

## 2026-11-23 · Step 3: role on every sign-in and the admin sign-in (D-020, D-021)
Tool: Claude Code (Haiku 5.5), free prompt with the Step 3 brief and the user's answers and approvals
What I asked: the role chain on Google sign-in (professor list on any domain, then a student association hook, then @ulbsibiu.ro as student, otherwise 403), and a POST admin sign-in with the ADMIN_USERNAME and ADMIN_PASSWORD pair from .env, returning the same session cookie.
What I got: D-013 superseded by D-021; D-020 and D-021 added; C-002 rewritten; Q-007 and Q-009 marked superseded by D-020. backend/app/auth.py rewritten (resolve_user, decide_role, is_student_association hook, admin_credentials_match with secrets.compare_digest, ensure_admin_user); POST /auth/admin-login in backend/app/routers/auth.py; ADMIN_USERNAME and ADMIN_PASSWORD in config and .env.example (empty = admin sign-in off). Invitations are no longer read for sign-in. Login page text in ro.js and en.js now says that sign-in is limited to @ulbsibiu.ro accounts or registered faculty members.
Existing tests whose assertions changed, by name: test_university_email_without_hd_is_rejected (renamed; asserted the invitation wording, now the new rule); test_existing_university_row_is_linked_and_role_resolved (role PROFESSOR became STUDENT: not in the list); test_known_external_sub_is_rejected_unless_listed_as_professor (303 became 403: an external address needs the professor list); test_invitation_no_longer_admits_an_external_address (303 became 403; invitations removed); the sign_in helper in test_auth.py now uses a university address (the admin and role tests still assert the same things). DENIED text updated. No assertion was weakened.
Tests: 17 new backend tests (roles, professor tiers, admin login). node scripts/test-all.mjs: backend 94, ETL 99, frontend 207 passed. Smoke test: POST /auth/admin-login answers 401 directly and through nginx while no admin credentials are set.
What I did with it: not committed or pushed. Consequence to know: an external account that is not a listed professor, including a student-organization account created earlier, can no longer sign in until the student association tier is built. The .env needs ADMIN_USERNAME and ADMIN_PASSWORD set to turn the admin sign-in on.

## 2026-11-23 · D-019 approved; the stored id is kept when the API changes it
Tool: Claude Code (Haiku 5.5), free prompt with the user's approval of the proposal and the answer on the edge case
What I asked: approve the decision "one email is one professor" (D-019), and handle the case where the API drops a stored id and gives the same email a new id.
What I got: D-019 written as approved and confirmed. `plan_rekeys` and `rekey_professor`: on a full run the stored row takes the new id and users.professor_id and activities.professor_id move from the old id to the new one; a partial run only reports the refusal. Tests first: 5 new ETL tests (3 pure, 2 against PostgreSQL). `node scripts/test-all.mjs`: backend 77, ETL 99, frontend 207 passed. Live reload from the local files: 206 stored, 0 moved, 0 refused, table still 206 rows.
What I did with it: the re-key is my design choice (the decision text says so): it moves references instead of deleting anything. Not committed or pushed.

## 2026-11-23 · Professors load: one person per email (Q-016 answer)
Tool: Claude Code (Haiku 5.5), free prompt with the user's answer to Q-016
What I asked: treat records with the same normalized email as one person; keep one id (the one stored, else one used by an activity, else the smallest) and warn with the dropped id.
What I got: `merge_records` groups by normalized email and returns the kept records, the repeated ids and the (dropped, kept) pairs; `build_preferences` reads the stored ids and activity professor ids. Warnings are printed by the CLI. Tests first: 94 ETL tests pass; `node scripts/test-all.mjs`: backend 77, ETL 94, frontend 207 passed. Live reload from the local files: 206 distinct professors stored, 2 duplicates warned, 0 refused, table still 206 rows.
What I did with it: Q-016 marked answered. Not committed or pushed. Proposed a decision (below) for the rule "one email, one professor id"; not written to DECISIONS.md until approved.

## 2026-11-23 · Professors ETL, step 2: extract to files, load into the professors table
Tool: Claude Code (Haiku 5.5), free prompt with the step 2 brief
What I asked: a standalone professors pipeline, run on demand by an admin: extract every faculty's professors (all pages, 500 per page) to local files, normalize (id, name, email; email stripped and lower-cased; null or blank email skipped), deduplicate by id across faculties, and load with an idempotent upsert that never truncates or deletes.
What I got: `etl/professors/` with `extract.py`, `load.py`, `cli.py` and four test files (extract, load, load against PostgreSQL, CLI). `write_json_atomic` moved to `etl/common.py` so both pipelines share it. Tests first; `node scripts/test-all.mjs`: backend 77, ETL 89, frontend 207 passed. Live run against the ULBS API: 9 faculties, 208 distinct professors, 206 stored, 2 left out because their email belongs to another id, 4 repeats across faculties, 3 skipped for a missing or invalid email or id. A second load gave the same counts with no new rows.
What I did with it: the duplicate-email case is recorded as open question Q-016 and needs your decision. Not committed or pushed. Local data files (data/professors) and the local database now hold personal data from the live run; both are outside git.

## 2026-11-23 · ETL: split the schedule downloader into one module per step
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: split the schedule downloader so that each step has its own script and tests.
What I got: `etl/schedule/sync.py` (steps 1-2: faculties and planning units), `download.py` (step 3: weekly schedule files), `loader.py` (step 4, unchanged), `cli.py` (the command line that replaces `downloader.py`), and `common.py` (the timeout and the table formatter). The tests follow their modules; `test_downloader.py` became `test_faculties_fetch.py`. Function bodies moved unchanged; only imports changed. The Dockerfile entrypoint is now `python -m etl.schedule.cli`. node scripts/test-all.mjs: backend 77, ETL 70, frontend 207 passed. The ETL image runs its CLI, and pyflakes is clean on the new modules.
What I did with it: not committed or pushed.

## 2026-11-23 · AGENTS.md: run and update all tests after every change
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: an instruction, in the agent instruction file, to verify all existing tests after every code change and update them where needed.
What I got: AGENTS.md hard rules: after every code change run `node scripts/test-all.mjs`; fix what the change broke; update a test only when the new behaviour is intended, and name each updated test in the report; never delete a test to get green or weaken an assertion silently; ask the user when unsure which side is wrong. Also added to the definition of done and the commands list.
What I did with it: not committed.

## 2026-11-23 · GitHub Actions: the three suites on every push and pull request
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: a GitHub Action that runs the three test suites on every commit, push or PR.
What I got: `.github/workflows/tests.yml`, triggered by push (all branches), pull_request and manual dispatch. On ubuntu-latest it creates `.env` from `.env.example` with placeholder values only (no secrets), runs `node scripts/test-all.mjs`, and uploads `output/test-report.md` as an artifact even when a suite fails. YAML checked; not yet run on GitHub.
What I did with it: not committed or pushed. The first run on GitHub is the real check.

## 2026-11-23 · Live colour progress bars in scripts/test-all.mjs
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: visual status with colours and a real-time progress bar per suite.
What I got: before each suite, a count of its tests (pytest --collect-only, vitest list --json) gives the bar a total. In a terminal the three bars redraw in colour (green, red on failure, yellow while running); with a pipe or in CI one plain line per suite is printed. NO_COLOR turns colour off; TEST_ALL_LIVE=1 forces the live display. Checked by forcing the live display and reading the frames: counts climb to 75/75, 66/66 and 207/207. The failing-test display was not exercised.
What I did with it: not committed.

## 2026-11-23 · One command for all tests: scripts/test-all.mjs
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: a single command that runs all tests and writes a report; whether a terminal runner like the one in the exams project is overengineered.
What I got: that runner is a 1,645-line terminal UI with its own Postgres and Cypress handling; not used. `scripts/test-all.mjs` (about 130 lines) runs the backend, ETL and frontend suites in Docker in turn, and writes output/test-report.md (totals, a table, the tail of any failing suite). Exit code 0 when all pass. Ran once: 348 tests passed (75 backend, 66 ETL, 207 frontend). output/ added to .gitignore. The failure path was not exercised.
What I did with it: not committed.

## 2026-11-23 · Decision D-018: frontend unit tests use Vitest and jsdom (approved)
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: approval of D-018, the dev-only test tooling, recorded in the decisions ledger.
What I got: D-018 added to DECISIONS.md (approved, confirmed 2026-11-23) with its index line. The app stays plain HTML, CSS and JavaScript (D-003 unchanged). Ledger lint passes.
What I did with it: not committed.

## 2026-11-23 · Frontend unit tests extended to every browser script
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: add the remaining frontend scripts to the unit tests (the decision to extend the scope).
What I got: tests for the i18n runtime, the shared components (ui, footer, header, language and theme toggles, toast, app), the session script (auth.js) and the login page. The coverage gate now covers every browser script: 207 tests, 100% statements, branches, functions and lines. No source change in this step. Backend tests pass.
What I did with it: not committed. The second decision (recording the test tooling as a ledger decision) was not written: it needs approval first.

## 2026-11-23 · Frontend unit tests with Vitest (100% coverage of the new scripts)
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: complete unit tests, with full coverage, for the frontend components and functions that are no longer placeholders, using Vite.
What I got: Vitest (Vite's test runner) in jsdom: `frontend/package.json` (dev-only), `frontend/vitest.config.js` (coverage gate 100% for api, grid, modules, free and timetable), `frontend/tests/` (setup, helpers, and five test files, 110 tests). Tests load the real page markup and dictionaries. A compose service `frontend-test` (profile `test`) runs them in a container. The app is unchanged in how it is served. Small source simplifications so that every branch can be reached: free.js (`roomHref` always gets a date, `setStatus` without fallbacks, unused `locale()` removed), timetable.js (`fill`, `drawGrid`, dialog and close guards that the markup makes unnecessary, and an address lookup that is skipped when no entity list loaded). Result: 110 passed; coverage 100% statements, branches, functions and lines. Backend tests 75 passed. ledger candidate PATTERN-009 added; architecture doc updated.
What I did with it: not committed. Not covered: the other scripts (auth, header, footer, app, components, login) were not in scope.

## 2026-11-22 · Header brand shows the logo mark
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: the green square next to the UniSpace text should contain the logo.
What I got: `frontend/public/brand-mark.png` (the logo mark on the light tile, 128 px); `header.js` shows it as an image in place of the gradient placeholder; `header.css` keeps the size and adds a thin border so the tile shows on a white header. Checked in the browser on the login page in both themes. Backend tests 75 passed.
What I did with it: not committed.

## 2026-11-22 · Favicon from the logo; colour scheme from the logo (light and dark)
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: add the logo in frontend/public as the favicon; update the colour scheme to match it, good in both light and dark themes.
What I got: colours sampled from the logo: navy #0e243c, teal #08a896. Light: navy text and primary, darker teal for links and focus (bright teal is too faint on white). Dark: brightened teal for primary and links on navy. Every text pair is at least 5.3:1 (AA). `tokens.css` and `DESIGN.md` updated; `theme-color` meta is the navy. Icons made from the mark on a light rounded tile (readable on light and dark browser tabs): `frontend/public/favicon.ico`, `favicon-32.png`, `apple-touch-icon.png`; linked from `head.html`. nginx serves `/public/` and `/favicon.ico` without a session. Checks: icon URLs answer 200 signed out; login page screenshot in both schemes. Backend tests pass.
What I did with it: not committed. Open: the header brand mark is still the gradient placeholder, not the logo.

## 2026-11-22 · Free now lists the rooms free for the current module
Tool: Claude Code (Haiku 5.5), free prompt
What I asked: on load, with no time frame chosen, the free now page lists the faculty's rooms free in the current 1.5-hour module, and shows until when each is free.
What I got: free now sends the current module's start and end (the next module during a break); the status line names it ("In module 14:40–16:10"); the list refreshes every 30 seconds when the module changes; the card shows the free-until time (next booking, or 21:10). `free.checkedAt` replaced by `free.inModule`. No backend change. Backend tests 75 passed. Browser check with the clock fixed at 15:00: 7 rooms for 14:40–16:10, sorted with 21:10 first, no console errors.
What I did with it: not committed.

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
