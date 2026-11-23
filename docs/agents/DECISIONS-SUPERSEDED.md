# Decisions superseded — UniSpace

<!-- graffino-agentic:begin v1 -->
> Decisions that no longer apply. **Never obeyed**; read only to explain old code or a
> past choice. Each points to the entry that replaced it. `ledger-lint.py --fix`
> keeps this file in sync: superseded entries move here from `DECISIONS.md`, and
> their index lines move here from its index.
<!-- graffino-agentic:end -->

## Index
- D-013 · Sign-in is Google only; the app stores no passwords · _superseded-by D-021_

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
