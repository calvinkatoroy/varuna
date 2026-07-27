# Design — Varuna

A locked design system for the Varuna VAPT console. Every page redesign reads this
file before emitting code. Do not regenerate per page — extend or amend this file
when the system needs to grow.

## Genre
modern-minimal (technical / instrument-panel register, not the SaaS-marketing side)

## Macrostructure family
- **Auth** (Login only): no macrostructure — a minimal centered gate card. Single
  purpose, no nav, no chrome.
- **Console** (all authenticated pages: New Scan, Active Scans, Approval Queue,
  Findings Review, Manual Input, Reports, Install Agent): macrostructure
  **Workbench** — task-focused, low-narrative, "the real data is the content."
  One shared persistent app-shell rail (not a Hallmark landing nav archetype —
  N1–N13 all model marketing navs; an authenticated route rail is its own thing,
  see § Navigation below). Density varies by role (see § Density knob), the
  macrostructure does not.

## Theme
Cobalt, dark execution — Cobalt is canonically light in the catalog; this app
already runs dark by established convention (security tooling stays dark, this
isn't an AI default), so the cool electric-blue accent register is kept but
applied to a dark paper per `color.md`'s dark-mode recipe (same anchor hue, only
lightness/chroma move).

- `--color-paper`       oklch(14% 0.012 250)
- `--color-paper-2`     oklch(18% 0.014 250)   /* card / elevated surface */
- `--color-paper-3`     oklch(22% 0.016 250)   /* hover state on paper-2 */
- `--color-ink`         oklch(94% 0.006 250)
- `--color-ink-muted`   oklch(72% 0.020 250)
- `--color-ink-faint`   oklch(50% 0.015 250)
- `--color-rule`        oklch(30% 0.010 250)
- `--color-accent`      oklch(62% 0.160 250)
- `--color-accent-ink`  oklch(14% 0.012 250)   /* text on filled accent */
- `--color-focus`       oklch(72% 0.170 250)

Severity is a **separate, domain-required signal system** — not the UI accent —
kept at conventional CVSS-style hue positions, retuned to OKLCH on the cobalt-dark
paper so it doesn't compete with the accent:

- `--color-crit`  oklch(64% 0.19  25)   /* red */
- `--color-high`  oklch(66% 0.18  45)   /* orange */
- `--color-med`   oklch(75% 0.15  75)   /* amber */
- `--color-low`   oklch(72% 0.15 145)   /* green */
- `--color-info`  oklch(70% 0.12 250)   /* blue, same hue family as accent on purpose */

## Typography
- Display: **Space Grotesk**, weight 600, style normal
- Body: **Geist**, weight 400 (350 on dark per the dark-mode weight-reduction rule)
- Outlier/mono: **JetBrains Mono**, weight 400 — exactly two roles: (1) job IDs /
  tool names / status tags, (2) evidence and code blocks (agent install command,
  raw finding evidence). Never a third role.
- Display tracking: -0.02em
- Type scale anchor: `--text-display: clamp(1.75rem, 2vw + 1.25rem, 2.5rem)` —
  console pages don't need marketing-scale display type; this is a page-title
  scale, not a hero scale.

## Spacing
4-point named scale, values in `tokens.css`. Pages use named tokens
(`var(--space-md)`), never raw Tailwind spacing utilities.

## Motion
- Easings: `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)` (the only easing in use)
- Reveal pattern: none — the console is composed, not animated in
- Reduced-motion fallback: opacity-only, ≤150ms
- One functional exception: a status-pulse (`opacity` keyframe, 1.6s loop) on
  "running" job indicators — informational, not decorative

## Microinteractions stance
- Silent success (no celebratory toasts); errors surface inline, same as today
- Hover delay 800ms / focus delay 0ms on any tooltip (none currently, reserved)
- Every async action (Launch, Approve, Reject, Add finding, Generate report ×2,
  Generate token) gets a real busy/disabled state — this was the single biggest
  gap in the pre-redesign app
- Optimistic-update + undo is not applicable here (server-authoritative job
  state) — inline error + retry instead

## CTA voice
- Primary: filled accent, 6px radius, `Launch` / `Approve` / `Add finding` —
  single verb, no filler
- Secondary/ghost: bordered, transparent, `Reject` / `Log out` / `Download`
- Danger: bordered in `--color-crit`, text in `--color-crit`, transparent fill —
  reserved for the aggressive-SQLMap toggle label and the Reject button, the two
  controls that need to visually cost more than a routine click

## Density variants (pilot)
Two pages (Dashboard, Findings Review) use a denser sub-variant of Workbench:
edge-to-edge panels instead of floating `.card` islands, a `.data-table` for
tabular/list data (job lists, findings), and a master-detail split (table +
detail pane) on Findings Review instead of stacked `<details>` accordions.
Rationale: this is a practitioner tool (peers: Burp Suite, Wireshark, Splunk),
not a marketing dashboard — simultaneous visibility of many rows beats
generous whitespace around one thing at a time. Same tokens, same macrostructure
family, same CTA voice — only the panel chrome and data density change.

Still on the card-based single-column layout (pending the same treatment,
not yet requested): New Scan, Active Scans, Approval Queue, Manual Input,
Reports, Install Agent.

## Density knob (standard vs pro)
Same shell, same tokens, same macrostructure. Standard-role screens show fewer
fields, plain-language labels, single-path forms. Pro-role screens show denser
field layout, technical labels (tool flags, CVSS, CWE). This is a per-field
`isPro` branch already present in the codebase — the redesign keeps that logic,
only the visual system changes.

## Navigation
Persistent left app-shell rail (`Layout.tsx`), not a Hallmark nav archetype —
none of N1–N13 model an authenticated route rail with role-gated destinations.
Active route: accent-left-border + accent text. Hover: paper-3. Focus-visible:
accent ring, instant. Collapses to a horizontal scrollable pill row below 768px
(rail becomes top bar, no hamburger — the destination count is small enough to
stay flat).

## Footer
None. A utility console has no sitemap to close — deliberate absence, not a miss.

## Per-page allowances
- Auth MAY use its own centered-card treatment, nothing else.
- Console pages MUST NOT use hero enrichment or illustration — function carries
  every page.
- Console pages MAY vary field density per the density knob above.

## What pages MUST share
- The wordmark (`Varuna`, Space Grotesk 600, small, in the rail).
- The accent colour and its placement (nav active state, primary CTA, focus
  rings, links — never a background fill).
- Display + body + outlier fonts.
- The CTA voice (radius, padding rhythm, verb-first labels).
- The severity palette, applied identically everywhere severity appears.

## What pages MAY differ on
- Field density (density knob).
- Whether a danger treatment is present (only on the two controls that need it).

## Exports

### tokens.css
```css
:root {
  --color-paper:       oklch(14% 0.012 250);
  --color-paper-2:      oklch(18% 0.014 250);
  --color-paper-3:      oklch(22% 0.016 250);
  --color-ink:          oklch(94% 0.006 250);
  --color-ink-muted:    oklch(72% 0.020 250);
  --color-ink-faint:    oklch(50% 0.015 250);
  --color-rule:         oklch(30% 0.010 250);
  --color-accent:       oklch(62% 0.160 250);
  --color-accent-ink:   oklch(14% 0.012 250);
  --color-focus:        oklch(72% 0.170 250);

  --color-crit: oklch(64% 0.19  25);
  --color-high: oklch(66% 0.18  45);
  --color-med:  oklch(75% 0.15  75);
  --color-low:  oklch(72% 0.15 145);
  --color-info: oklch(70% 0.12 250);

  --font-display: "Space Grotesk", ui-sans-serif, system-ui, sans-serif;
  --font-body:    "Geist", ui-sans-serif, system-ui, sans-serif;
  --font-mono:    "JetBrains Mono", ui-monospace, monospace;

  --space-3xs: 0.25rem;  --space-2xs: 0.5rem;  --space-xs: 0.75rem;
  --space-sm:  1rem;     --space-md:  1.5rem;  --space-lg: 2rem;
  --space-xl:  3rem;     --space-2xl: 4.5rem;

  --text-xs: 0.75rem;  --text-sm: 0.875rem; --text-md: 1rem;
  --text-lg: 1.125rem; --text-xl: 1.375rem; --text-display: clamp(1.75rem, 2vw + 1.25rem, 2.5rem);

  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --dur-short: 150ms;
  --dur-med: 220ms;

  --radius-input: 6px;
  --radius-card: 8px;
  --radius-pill: 999px;
}
```

See `export-formats.md` for Tailwind `@theme` / DTCG / shadcn mappings — not
generated here since this project consumes tokens directly via
`tailwind.config.js`, not one of those export targets.

## Pilot: warm/glass Dashboard variant
Dashboard (`frontend/src/pages/Dashboard.tsx`) opts into a second, warmer token
set via a `.dashboard-warm` wrapper class in `index.css` — **not yet
system-wide**. Every other page stays on Cobalt dark above.

- Light warm paper (`oklch(95% 0.014 65)`), soft warm ink, hairline rules at
  ~88% L — same structural roles as Cobalt, retuned for a light surface.
- Accent stays blue (`oklch(58% 0.12 235)`, calmer/softer than Cobalt's) —
  deliberate: Apple's own UI language keeps blue as the trust/action colour
  even in warm contexts, and this is still a security tool.
- Severity palette (`--color-crit/high/med/low/info`) is re-darkened for
  light-background contrast — the Cobalt values were tuned for a dark paper
  and would fail contrast here unchanged.
- `.glass`: translucent panel fill + `backdrop-filter: blur(20px)` + hairline
  border + soft shadow. Used for every panel instead of the flat `.card`.
  Restrained on purpose (Hallmark anti-pattern: glassmorphism-as-decoration) —
  it sits behind real, dense data (tables, lists, a real status-count bar),
  never as a decorative layer with nothing under it.
- Panels are spaced apart (`gap-sm`/`gap-md`) rather than edge-to-edge —
  density lives *inside* each panel (dense tables/lists), not in the gaps
  between them.
- `--radius-card` 20px / `--radius-input` 12px on this page only (vs 8px/6px
  elsewhere) — rounder, softer, more iOS-like.

This works because CSS custom properties cascade: every existing token-based
class (`.btn`, `.card`, `.data-table`, severity text colours) picks up the
warm values automatically inside `.dashboard-warm` — nothing else needed to
change to reskin the page.

**Open decision:** whether this becomes the system-wide direction (replacing
Cobalt dark everywhere) or stays a Dashboard-only variant. Until decided, do
not carry `.dashboard-warm` onto other pages without an explicit ask.

## Provenance
Produced by `hallmark redesign` (whole-app, multi-page flow) on request from the
project owner, replacing an unstyled default Tailwind build. No external DNA
source — catalog theme (Cobalt) adapted to dark per project convention. The
warm/glass Dashboard pilot above was added later, scoped, pending a decision
on whether it becomes the system default.
