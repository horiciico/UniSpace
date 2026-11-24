# Open questions — UniSpace

<!-- graffino-agentic:begin v1 -->
> Unknowns. Work that depends on an open question is out of scope until it is
> answered. Only the user answers; an agent never answers by guessing. An agent may
> write a `Proposed answer` the evidence supports; the question stays
> `investigating` until the user confirms it.
> Answered entries stay, with the answer and date, and usually become a D- or PATTERN-.
<!-- graffino-agentic:end -->

## Index
- Q-001 · What does UniSpace do, and who uses it? · _answered_
- Q-002 · Which branches and version scheme does the release use? · _answered_
- Q-003 · How are UI screenshots taken for review? · _answered_
- Q-004 · Is there a design board (Claude Design) or Figma for the UI? · _answered_
- Q-005 · Where and how is the platform deployed? · _answered_
- Q-006 · Which lint and type-check tools should run?
- Q-007 · How do users sign in (university account, password, or both)? · _answered_
- Q-008 · How is the semester customized (holidays, breaks, inverted-parity weeks)?
- Q-009 · How does a university (@ulbsibiu.ro) user get a role above STUDENT? · _answered_
- Q-010 · Which days and rooms can an admin mark as off limits, and how is that stored? · _answered_
- Q-011 · Does the app store all nine faculties, or only `dre`? · _answered_
- Q-012 · Does a permanent rule change go through a request table, or does the admin edit directly? · _answered_
- Q-013 · What does the ULBS schedule JSON look like (row per course or per occurrence, id types)? · _answered_
- Q-014 · Is a day-level off-limits mark for the whole university or for one faculty? · _answered_
- Q-015 · Where do the professors and their emails come from? · _answered_
- Q-016 · Two professor ids share one email: which record is kept? · _answered_
- Q-017 · Should a cancelled or moved occurrence still block a room in the free-room search and in booking? · _answered_
- Q-018 · Does a move of an occurrence to another room need to block that room? 

---

## Q-001 · What does UniSpace do, and who uses it?
- **Status:** answered
- **Answer (user, 2026-11-19):** The description in `CONTEXT.md` (the project brief, Romanian, verbatim from the course) is the definition. Its summary: a timetable and room-booking platform for the faculty, with priority-based bumping (course > exam > official faculty activity > student organization > student).
- **Blocks:** the domain models and the first feature, the terms in CONTEXT.md, and any user-facing screen.
- **Who answers:** the user (product owner)

## Q-002 · Which branches and version scheme does the release use?
- **Status:** answered (branch), open (version scheme)
- **Answer (user, 2026-11-22):** `main` is the default branch and the one used for releases and deploys.
- **Still open:** whether releases get version numbers (such as `1.0.0`) or dates. Not answered yet.
- **Blocks:** the version source and the changelog in AGENTS.md section 5.
- **Who answers:** the user

## Q-003 · How are UI screenshots taken for review?
- **Status:** answered
- **Answer (user, 2026-11-24):** browser screenshots are allowed for review now that there is a frontend and an end-to-end flow. The method (the proposal was a headless browser run against the nginx frontend, for example Playwright) is not confirmed; the tool is still to be chosen.
- **Blocks:** nothing now that the answer is in. The tool choice is open within the screenshot step.
- **Who answers:** the user

## Q-004 · Is there a design board (Claude Design) or Figma for the UI?
- **Status:** answered
- **Answer (user, 2026-11-19):** No design board and no Figma. The UI is designed freely (the user says "we are freestyling").
- **Blocks:** the design source in docs/design/DESIGN.md and confirmation of new screens.
- **Who answers:** the user

## Q-005 · Where and how is the platform deployed?
- **Status:** answered
- **Answer:** Oracle Cloud (the user, 2026-11-17; replaces the earlier Vercel answer). A VM there can run the Compose stack as it is. The deploy plan still needs a domain, HTTPS, the Google redirect URI for production, and backups.
- **Blocks:** a production compose setup, secrets handling in production, and the deploy steps in AGENTS.md section 5.
- **Who answers:** the user

## Q-006 · Which lint and type-check tools should run?
- **Status:** open
- **Blocks:** the lint and type-check lines in AGENTS.md sections 2 and 6.
- **Who answers:** the user
- **Note (user, 2026-11-19):** will be configured in the future. Stays open until then.
- **Note (user, 2026-11-22):** will be configured later. Stays open until then.

## Q-007 · How do users sign in (university account, password, or both)?
- **Status:** answered
- **Answer (user, 2026-11-19):** Google sign-in only, already implemented. Accounts on the `@ulbsibiu.ro` domain sign in and are created as STUDENT. Accounts outside that domain need an invitation (the `invitations` table). No passwords.
- **Blocks:** confirming the sign-in method. Google sign-in and the nginx page gate are built (C-002, D-009, D-010); the old dummy login is gone.
- **Who answers:** the user
- **Superseded by:** D-020 and D-021 (2026-11-23). The answer above is kept for history.

## Q-008 · How is the semester customized (holidays, breaks, inverted-parity weeks)?
- **Status:** open
- **Blocks:** `CUSTOM` parity (a CHECK keeps it unusable), a weeks list on `activity`, and any `valid_from` / `valid_to` or semester table.
- **Who answers:** the user (the user will answer later; the rest is still open)
- **Answer (user, 2026-11-19, partly):** The active period (start and end) comes from the ULBS API, per planning unit (`planning_time_units`). Parity works by week, and the mapping is in Q-013. Still open: holidays, breaks, and inverted-parity weeks; and whether the CUSTOM parity and a weeks list are needed.
- **Note (user, 2026-11-22):** will be configured later. Stays open until then.

## Q-009 · How does a university (@ulbsibiu.ro) user get a role above STUDENT?
- **Status:** answered
- **Answer (user, 2026-11-19):** Everyone starts as STUDENT. An admin raises the role by hand.
- **Blocks:** professors and student-organization leaders with a university address getting their role without an admin changing the `user.role` column by hand. An unused invitation for a university email is ignored today.
- **Who answers:** the user
- **Superseded by:** D-020 (2026-11-23). The answer above is kept for history.

## Q-010 · Which days and rooms can an admin mark as off limits, and how is that stored?
- **Status:** answered
- **Answer (user, 2026-11-19):** Days: an admin marks one or more days, for the whole duration or for a certain period. Rooms: an admin marks a room for one or more days, or for a time period within a day. Stored in an `off_limits` table.
- **Blocks:** the admin off-limits feature. The scope of a day-level mark is open in Q-014.
- **Who answers:** the user

## Q-011 · Does the app store all nine faculties, or only `dre`?
- **Status:** answered
- **Answer (user, 2026-11-19):** Build it at university level. The frontend lets the user choose the faculty whose schedule they want to see.
- **Blocks:** the `faculties` table, and the `faculty_code` on rows that belong to a faculty.
- **Who answers:** the user

## Q-012 · Does a permanent rule change go through a request table, or does the admin edit directly?
- **Status:** answered
- **Answer (user, 2026-11-19):** Build the table (`rule_change_requests`).
- **Blocks:** the request flow for permanent changes.
- **Who answers:** the user

## Q-013 · What does the ULBS schedule JSON look like (row per course or per occurrence, id types)?
- **Status:** answered
- **Parity mapping (user, 2026-11-19, confirmed):** `parity` 0 = ALL (every week), 1 = ODD (odd weeks only; week 1 of the academic year is odd), 2 = EVEN (even weeks only).
- **Blocks:** the parser, the unique constraint on `external_id`, and the types of `external_id`. The structure is to be discovered from the schedule JSON files in Step 2.
- **Who answers:** the user, together with the JSON files. The user said: "we will discover together."
- **Answer (user, 2026-11-22, confirmed the proposed answer):** one row per ULBS entry per study formation, with `timeSlots` as a list (0 to 6 slots; contiguous runs are merged, gaps stay open). The `id` is unique within a faculty file but not across files (560 ids repeat with different content), so the loader does not use it as a key. It keys each row on (room, day, parity, start, end), hashed to 40 characters, and keeps the ULBS id only in the report. Ids are integers; room `roomId` is a UUID; `studyFormation.id` is an integer. Parity values 0, 1, 2 as in D-014.
- **Confirmed:** 2026-11-22

## Q-014 · Is a day-level off-limits mark for the whole university or for one faculty?
- **Status:** answered (scope), open (duration wording)
- **Answer (user, 2026-11-22):** the admin selects the scope when setting the mark.
- **Still open:** whether "the whole duration" means the whole semester or the whole academic year.
- **Blocks:** the duration wording of the `off_limits` table; the scope column itself is no longer blocked.
- **Who answers:** the user

## Q-015 · Where do the professors and their emails come from?
- **Status:** answered
- **Answer (user, 2026-11-23):** A list of professors comes from an API and is loaded in Step 2 of the professors pipeline. The schedule files carry `professorId` and the name, but no email, so the email comes from that list.
- **Blocks:** the `professors` table contents (Step 2) and the automatic PROFESSOR role (the role rule is not decided yet; a PROPOSAL is pending).
- **Who answers:** the user

## Q-016 · Two professor ids share one email: which record is kept?
- **Status:** answered
- **Found (2026-11-23):** the live professors API has records with different ids and the same email (one faculty alone has 152 ids and 151 emails).
- **Answer (user, 2026-11-23):** one person with duplicate records in the ULBS system. Deduplicate by normalized email during the transform. Keep one id: prefer an id that appears in `activities` if that is easy, otherwise the lexicographically smallest id. Log a warning with the skipped duplicate id. This keeps `professors.email` unique without dropping the professor from login.
- **Implemented (2026-11-23):** an id already stored for the email is kept first, then an id used by an activity, then the smallest id. The stored id comes first so that a later run does not swap ids and trigger a refusal.
- **Blocks:** nothing now.
- **Who answers:** the user

## Q-017 · Should a cancelled or moved occurrence still block a room in the free-room search and in booking?
- **Status:** answered
- **Found (2026-11-24):** `planning.occurrences()` ignored `Activity.status` (CANCELLED) and the exceptions, so a cancelled course blocked its room and a moved occurrence blocked its old time.
- **Answer (user, 2026-11-24):** confirmed the proposed answer: a cancelled occurrence does not block; a moved occurrence blocks its new time instead of its old one.
- **Implemented (2026-11-24):** the shared helper (`planning.occurrences`) now drops CANCELLED activities and cancelled occurrences, and applies moves by new date and new time, found from either date. The timetable, the free-room search and the booking check all use it. Existing test `test_free_now_reports_the_searched_window` changed its expected `free_until` from 16:00 to 21:10 (the cancelled course no longer blocks); named in the AI log.
- **Still open:** a move to another room (`new_classroom_id`) is not handled: see Q-018.
- **Who answers:** the user

## Q-018 · Does a move of an occurrence to another room need to block that room?
- **Status:** open
- **Found (2026-11-24):** `ActivityException.new_classroom_id` exists, but `planning.occurrences()` ignores it. A course moved to another room still shows in its old room, and its new room is not blocked.
- **Blocks:** the room view, the free-room search and the booking check for a relocated occurrence.
- **Who answers:** the user
