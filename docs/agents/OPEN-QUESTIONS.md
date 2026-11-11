# Open questions — UniSpace

<!-- graffino-agentic:begin v1 -->
> Unknowns. Work that depends on an open question is out of scope until it is
> answered. Only the user answers; an agent never answers by guessing. An agent may
> write a `Proposed answer` the evidence supports; the question stays
> `investigating` until the user confirms it.
> Answered entries stay, with the answer and date, and usually become a D- or PATTERN-.
<!-- graffino-agentic:end -->

## Index
- Q-001 · What does UniSpace do, and who uses it?
- Q-002 · Which branches and version scheme does the release use?
- Q-003 · How are UI screenshots taken for review?
- Q-004 · Is there a design board (Claude Design) or Figma for the UI?
- Q-005 · Where and how is the platform deployed?
- Q-007 · How do users sign in (university account, password, or both)?
- Q-006 · Which lint and type-check tools should run?

---

## Q-001 · What does UniSpace do, and who uses it?
- **Status:** open
- **Blocks:** the domain models and the first feature, the terms in CONTEXT.md, and any user-facing screen.
- **Who answers:** the user (product owner)

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
- **Status:** open
- **Blocks:** the real login. The frontend has a dummy gate (`frontend/js/auth.js`) for now: any email and password work, and it is not security.
- **Who answers:** the user

## Q-006 · Which lint and type-check tools should run?
- **Status:** open
- **Blocks:** the lint and type-check lines in AGENTS.md sections 2 and 6.
- **Who answers:** the user
