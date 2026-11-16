# Open questions — UniSpace

<!-- graffino-agentic:begin v1 -->
> Unknowns. Work that depends on an open question is out of scope until it is
> answered. Only the user answers; an agent never answers by guessing. An agent may
> write a `Proposed answer` the evidence supports; the question stays
> `investigating` until the user confirms it.
> Answered entries stay, with the answer and date, and usually become a D- or PATTERN-.
<!-- graffino-agentic:end -->

## Index
- Q-001 · What does UniSpace do, and who uses it? · _investigating_
- Q-002 · Which branches and version scheme does the release use?
- Q-003 · How are UI screenshots taken for review?
- Q-004 · Is there a design board (Claude Design) or Figma for the UI?
- Q-005 · Where and how is the platform deployed?
- Q-007 · How do users sign in (university account, password, or both)? · _investigating_
- Q-006 · Which lint and type-check tools should run?
- Q-008 · How is the semester customized (holidays, breaks, inverted-parity weeks)?
- Q-009 · How does a university (@ulbsibiu.ro) user get a role above STUDENT?

---

## Q-001 · What does UniSpace do, and who uses it?
- **Status:** investigating
- **Blocks:** the domain models and the first feature, the terms in CONTEXT.md, and any user-facing screen.
- **Who answers:** the user (product owner)
- **Proposed answer:** A faculty timetable and room-booking platform with priority-based bumping (course > exam > official faculty > student org > student), per the product brief of 2026-11-11. Not confirmed.

## Q-002 · Which branches and version scheme does the release use?
- **Status:** open
- **Blocks:** AGENTS.md section 5 (release), the base branch in /build, and the version source.
- **Who answers:** the user

## Q-003 · How are UI screenshots taken for review?
- **Status:** open
- **Blocks:** the screenshot step of /build and the visual check in the definition of done.
- **Who answers:** the user
- **Proposed answer:** A headless browser (for example Playwright) run in a container against the nginx frontend. Not confirmed: no tool is set up yet.

## Q-004 · Is there a design board (Claude Design) or Figma for the UI?
- **Status:** open
- **Blocks:** the design source in docs/design/DESIGN.md and confirmation of new screens.
- **Who answers:** the user

## Q-005 · Where and how is the platform deployed?
- **Status:** open
- **Blocks:** a production compose setup, secrets handling in production, and the deploy steps in AGENTS.md section 5.
- **Who answers:** the user

## Q-007 · How do users sign in (university account, password, or both)?
- **Status:** investigating
- **Blocks:** confirming the sign-in method. Google sign-in and the nginx page gate are built (C-002, D-009, D-010); the old dummy login is gone.
- **Who answers:** the user
- **Proposed answer:** Google OAuth only: `@ulbsibiu.ro` accounts are auto-provisioned as STUDENT; other accounts need an invitation (built in this change, C-002). No passwords. Not confirmed.

## Q-006 · Which lint and type-check tools should run?
- **Status:** open
- **Blocks:** the lint and type-check lines in AGENTS.md sections 2 and 6.
- **Who answers:** the user

## Q-008 · How is the semester customized (holidays, breaks, inverted-parity weeks)?
- **Status:** open
- **Blocks:** `CUSTOM` parity (a CHECK keeps it unusable), a weeks list on `activity`, and any `valid_from` / `valid_to` or semester table.
- **Who answers:** the user (decided once there is a concrete customization flow)

## Q-009 · How does a university (@ulbsibiu.ro) user get a role above STUDENT?
- **Status:** open
- **Blocks:** professors and student-organization leaders with a university address getting their role without an admin changing the `user.role` column by hand. An unused invitation for a university email is ignored today.
- **Who answers:** the user
- **Proposed answer:** For now (decided 2026-11-16): everyone is STUDENT, an admin elevates. Later, perhaps read roles from the imported timetable (teachers appear there). Alternatives: an invitation sets the role at first login, or also later.
