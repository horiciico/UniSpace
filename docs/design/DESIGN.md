# DESIGN — UniSpace

<!-- graffino-agentic:begin v1 -->
> The design guardrails for this app. Every UI change follows them. A change to a
> token or a rule here is a PROPOSAL (AGENTS.md → The gate).

## Where designs live
**Designs change only in this repo.** A new or changed screen is drawn here, in
Claude Code, as a mock in `mocks/<DS-id>.html` (using the tokens below), and
confirmed before it is built. The places:

| Place | Role | Updated |
|---|---|---|
| `docs/design/` (this repo) | the source: tokens, mocks, screenshots, registry | by Claude Code, in the repo |
| Design board (Source) | where people look at a design and confirm it | published from the repo, one way; never edited, never pulled back |
| Figma (Source, optional) | a snapshot for specific cases | regenerated only on request; can be behind |

When they disagree, the repo is right. A change made on the board or in Figma is lost
at the next publish. Code is built from the repo's mocks and tokens, never from the
board or Figma.

## Procedure for any UI change

1. **Find the design.** Resolve the screen's `DS-` ID in `registry.yaml` and open
   its mock (`mocks/`) and screenshots (`screens/`). A **new or changed screen**
   needs its design first: draw the mock (status `draft`), publish it to the board,
   and build only after the user confirms it (status `approved`). Never extrapolate a screen.
2. **Reuse first.** Use an existing component from `registry.yaml` (kind
   `component`). A new component needs a reason in the plan.
3. **Tokens only.** Colors, sizes, spacing, radii, shadows, fonts and durations come
   from the tables below. No raw hex, px or font name in component code.
4. **Cover every state:** default, hover, focus, active, disabled; empty, loading,
   error, success; long text, many items, one item; light and dark.
5. **Screenshot and compare** (command in AGENTS.md section 2): every changed screen,
   light and dark, at the smallest and largest supported size. Save as
   `screens/<DS-id>.<light|dark>.png`. Look at each one before you report.
6. **Record.** Update `registry.yaml` (new DS- ID, status `implemented`, source
   file). Republish the changed screens to the board. A reusable UI practice becomes
   a `candidate` pattern.

## Guardrails

**Color and contrast**
- Text contrast ≥ 4.5:1 (≥ 3:1 for text ≥ 18.66 px bold / 24 px). Icons, borders of
  inputs and focus rings ≥ 3:1 against their background. Check both themes.
- Color never carries meaning alone: pair it with an icon or text.
- Dark mode uses its own token values, not inverted light values.

**Layout and spacing**
- Spacing comes from the scale only. Align to the grid; equal gaps for equal
  relationships.
- No horizontal scroll at the smallest supported width. Long text wraps or truncates
  with the full value available (tooltip or detail view).

**Typography**
- Only the type scale below. One primary heading per screen. Sentence case for
  labels, buttons and headings.

**Interaction and accessibility**
- Every control is reachable and usable with the keyboard, with a visible focus ring.
- Hit targets ≥ 44 × 44 px on touch, ≥ 24 × 24 px with a pointer.
- Every icon-only control has an accessible name (`aria-label`).
- Motion respects `prefers-reduced-motion`; durations from the tokens.

**Copy**
- Plain, short, active voice. Buttons name the action ("Save", not "OK").
- Error text says what happened and what to do next. No raw error codes alone.
- Terms from `CONTEXT.md` only.

**States**
- Empty states explain what will appear and offer the next action.
- Loading shows within 100 ms of a wait; skeletons keep the final layout.
- Destructive actions ask for confirmation or offer undo.

## Publishing to the board
Not set up: no board exists yet (Q-004). Until it does, mocks stay in `mocks/` and
nothing is published.

DS- IDs are for the tools (registry, mocks, board, Figma frames).

<!-- graffino-agentic:end -->

## Source
- Design board: none yet (Q-004)
- Figma: none
- Token source in code: `frontend/styles/tokens.css`. The values below match that file; change both together.

## Tokens

Dark values apply when the OS is dark, or when `data-theme="dark"` is set on `<html>`
(the header toggle cycles auto, light, dark). Contrast was checked for every text pair:
the lowest is 6.1:1.

### Color
| Token | Light | Dark | Use |
|---|---|---|---|
| `--color-bg` | #f4f7f6 | #0b1a2b | page background |
| `--color-surface` | #ffffff | #12233a | cards, header, tables |
| `--color-text` | #0e243c | #e6eef6 | body text (14.6:1 / 15.0:1) |
| `--color-muted` | #4d5f70 | #9fb3c6 | secondary text (6.1:1 / 8.1:1) |
| `--color-border` | #d3dedb | #2a4059 | borders, table lines |
| `--color-primary` | #0e243c (logo navy) | #1cc3ac (logo teal, brightened) | primary buttons, active nav, brand. Light: 15.7:1 with white text; dark: 7.7:1 with `--color-on-primary` |
| `--color-link` | #066e62 | #5ed8c6 | text links. Light uses a darker teal: bright teal #08a896 is about 3:1 on white |
| `--color-on-primary` | #ffffff | #06201b | text on primary (15.7:1 / 7.7:1) |
| `--color-accent` | #08a896 (logo teal) | #08a896 | highlight, secondary call to action, the logo's accent |
| `--color-on-accent` | #0e243c | #06201b | text on accent (5.3:1 / 5.7:1) |
| `--color-focus` | #066e62 | #5ed8c6 | focus ring (same tint as links) |
| `--color-success-bg` / `-text` | #d4f2ea / #0a5c4e | #123f35 / #9be6d4 | free, approved, confirmed (6.7:1 / 8.2:1) |
| `--color-warning-bg` / `-text` | #fdebc8 / #7a4a00 | #4a3a14 / #ffd68a | soon, requested, pending, lab blocks (6.4:1 / 8.0:1) |
| `--color-danger-bg` / `-text` | #fbd9d4 / #8a2118 | #4a1f1c / #ffb8ae | busy, rejected, bumped, cancelled (6.9:1 / 8.5:1) |
| `--color-info-bg` / `-text` | #dbe7f2 / #1d3f63 | #1a3350 / #bcd9f2 | neutral info, course blocks (8.6:1 / 8.8:1) |
| `--color-shadow` | rgb(20 19 40 / 0.08) | rgb(0 0 0 / 0.4) | card shadows |

### Typography
| Token | Family | Size / line height | Weight | Use |
|---|---|---|---|---|
| `--font-sans` | system UI stack | — | 400 body · 600 controls · 700–800 headings | all text |
| `--font-mono` | ui-monospace stack | — | 400 | URLs, codes |
| `--text-sm` | sans | 0.875rem (14px) | — | labels, tags, table text |
| `--text-base` | sans | 1rem (16px) · `--leading-body` 1.55 | — | body |
| `--text-lg` | sans | 1.125rem (18px) | — | lead text, card titles |
| `--text-xl` | sans | 1.375rem (22px) · `--leading-tight` 1.2 | — | section headings |
| `--text-2xl` | sans | 1.75rem (28px) | — | page titles, stat values |
| `--text-3xl` | sans | 2.5rem (40px) | — | hero heading |

### Spacing
| Token | Value |
|---|---|
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-5` | 24px |
| `--space-6` | 32px |
| `--space-7` | 48px |
| `--space-8` | 64px |

### Radius, shadow, motion
| Token | Value | Use |
|---|---|---|
| `--radius-sm` | 6px | inputs, chips in tables, timetable blocks |
| `--radius-md` | 12px | list rows, stat tiles, grids |
| `--radius-lg` | 20px | cards |
| `--radius-pill` | 999px | buttons, pills, tabs |
| `--shadow-card` | 1px + 6–18px soft shadow (`--color-shadow`) | cards, stat tiles |
| `--duration-fast` | 150ms (0 with reduced motion) | hover, nav |
| `--duration-base` | 250ms (0 with reduced motion) | card lift, toast |
| `--container-max` | 1120px | page width |

### Breakpoints / window sizes
| Name | Min | Max |
|---|---|---|
| small | 0 | 639px (one column, menu button) |
| medium | 640px | 959px (two- and three-column grids) |
| large | 960px | fluid, max 1120px (inline navigation) |

Media queries cannot read custom properties, so these three values are written
literally in `base.css`. They are listed below as findings.

## Hard-coded values found (to migrate)
Found at the first UI scaffold (2026-11-11). Not fixed yet; each is a finding, not a
design decision. The media-query breakpoints above are expected and are not listed.

> The line numbers below are from `css/base.css` before the split on 2026-11-17. The
> rules now live in `styles/base.css` (lines 1–92), `styles/components/*.css` and
> `styles/motion.css` (lines 834 on), in the same order. Find a rule by its selector.
> The inline `style="…"` attributes are gone: they moved to classes in `styles/utilities.css`
> and the component files (done 2026-11-17).

| path:line | Value | Should be |
|---|---|---|
| frontend/css/base.css:54 | `text-underline-offset: 3px` | token `--space-1` (4px) or a new `--underline-offset` |
| frontend/css/base.css:59 | `outline-offset: 2px` | token (new `--focus-offset`) |
| frontend/css/base.css:81 | `top: -100px` (skip link, hidden) | none needed; reads as "off screen" |
| frontend/css/base.css:100 | `blur(8px)` (sticky header) | new token `--blur-header` |
| frontend/css/base.css:125–126 | `28px` brand mark | new size token |
| frontend/css/base.css:193 | `1px` borders | new `--border-width` |
| frontend/css/base.css:206, 396 | `translateY(-1px)`, `(-2px)` hover lift | new `--lift-sm` / `--lift-md` |
| frontend/css/base.css:420 | `min-height: 140px` placeholder card | new size token |
| frontend/css/base.css:426–427, 492–493 | `44px` room icon, `2.5rem` step badge | new icon-size token (same value; also a hit target check) |
| frontend/css/base.css:485 | `4.5rem`, `2.5rem 1fr` grid columns | layout token |
| frontend/css/base.css:582 | `max-width: 720px` form card | new `--container-form` |
| frontend/css/base.css:622 | `min-height: 96px` textarea | new size token |
| frontend/css/base.css:676–683 | timetable grid: `4.5rem`, `3.25rem` rows, `2px` gap, `620px` min width | timetable tokens (new) |
| frontend/css/base.css:709, 728, 759–763 | `2px` margin, `0.8125rem` text, `12px` legend swatch, `3px` radius, `-1px` offset | tokens or removal |
| frontend/css/base.css:784 | `5rem` error code | new `--text-display` |
| ~~41 `style="…"` attributes in 11 pages~~ | done 2026-11-17: classes in `styles/utilities.css` and the component files. The timetable still sets grid positions from JavaScript (the only remaining inline positions). | — |
