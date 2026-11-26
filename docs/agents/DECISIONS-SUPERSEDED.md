# Decisions superseded — UniSpace

<!-- graffino-agentic:begin v1 -->
> Decisions that no longer apply. **Never obeyed**; read only to explain old code or a
> past choice. Each points to the entry that replaced it. `ledger-lint.py --fix`
> keeps this file in sync: superseded entries move here from `DECISIONS.md`, and
> their index lines move here from its index.
<!-- graffino-agentic:end -->

## Index
- D-013 · Sign-in is Google only; the app stores no passwords · _superseded-by D-021_
- D-027 · The academic calendar (`academic_periods`) decides the time grid and whether weekly courses run · _superseded-by D-028_

---

## D-013 · Sign-in is Google only; the app stores no passwords
- **Status:** superseded-by D-021
- **Date:** 2026-11-17
- **Rule:** Users sign in with their Google account (OAuth 2.0 through authlib). The backend stores no passwords and no password hashes. Access rules come from the verified Google claims and the invitation table (C-002).
- **Why:** The user decided this. A password store adds hashing, reset and lockout code, and a larger attack surface to secure. Google handles the credential and the second factor.
- **Rejected:** local accounts with bcrypt or argon2 hashes
- **Evidence:** backend/app/auth.py, backend/app/routers/auth.py, docs/agents/CONTRACTS.md (C-002)
- **Source:** user · confidence high
- **Confirmed:** 2026-11-17

## D-027 · The academic calendar (`academic_periods`) decides the time grid and whether weekly courses run
- **Status:** superseded-by D-028
- **Date:** 2026-11-26
- **Rule:** `academic_periods` rows (global, inclusive `start_date`..`end_date`, no overlaps) are set by an admin. For any date the type is the covering period's, or `TEACHING` when none covers it.
  - `TEACHING`: the 90-minute module grid; weekly recurring courses are active.
  - `EXAM_SESSION`: hourly grid 08:00 to 22:00, whole hours only, minimum 1 hour; weekly recurring courses are suppressed; exams and student bookings use the hourly grid.
  - `HOLIDAY`: weekly recurring courses are suppressed; new bookings are disabled.
  Overlap is enforced by the application helper; the database only checks `start_date <= end_date`. Changes to the grid, booking and free-room contracts (C-009 and others) are made task by task, each with its own PROPOSAL.
- **Why:** The user wants one source of truth for the timetable and for booking validation (spec "Academic Calendar", 2026-11-26).
- **Rejected:** per-faculty periods; a database exclusion constraint (user chose helper only).
- **Evidence:** backend/app/academic_calendar.py, backend/app/models/academic_period.py, backend/tests/test_academic_calendar.py (Task 1; later tasks add the grid and booking uses)
- **Source:** user (spec, answers and approval, 2026-11-26) · confidence high
