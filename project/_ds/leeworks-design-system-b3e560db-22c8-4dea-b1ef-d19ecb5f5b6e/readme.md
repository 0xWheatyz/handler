# Leeworks Design System

**Leeworks Systems** — a from-scratch design system built July 2026. No existing codebase, Figma, or brand assets were provided; everything here was authored fresh from the brief: *modern, bright whites, near-monochrome, explicitly avoiding common "AI" color themes (no bluish-purple gradients, no glassmorphism)*.

Personality: **crisp & professional**, with a **geometric & friendly** typographic voice. Softly rounded shapes (6–10px). Light-first with full dark tokens. Comfortable density.

## Sources
None provided. Fonts are Google Fonts substitutes (see Caveats). No logo was provided — the brand renders as plain type ("Leeworks") wherever a mark would go.

## CONTENT FUNDAMENTALS
- **Voice:** plain, confident, specific. Short sentences. Verbs first in CTAs ("Create a workspace", "Invite your team", "View report").
- **Casing:** Sentence case everywhere — headings, buttons, labels, nav. Never Title Case, never ALL CAPS except tiny overline labels (letter-spaced, e.g. "OVERVIEW").
- **Person:** "you/your" to the user; "we" only when Leeworks itself acts ("We'll email you a receipt"). Never "I".
- **Numbers & data:** tabular figures in mono (`--font-mono`) for metrics, IDs, timestamps. Units spelled tight: "12.4k", "3m ago".
- **Emoji:** never in product UI. None.
- **Microcopy vibe:** helpful, unhurried, no exclamation marks. Empty states state the fact + one action: "No reports yet. Create your first report."
- Examples: "Everything your team ships, in one place." / "Save changes" / "This can't be undone." / "Last synced 2m ago".

## VISUAL FOUNDATIONS
- **Color:** bright white pages (`--surface-page: #fff`), a warm-neutral ink ramp (`--ink-0…9`) doing nearly all the work. Primary interactive color is **ink black** (`--interactive: #141413`) — buttons, links, focus. One restrained non-neutral: a deep leaf green `--signal` (#1d6b45), used sparingly for positive signals and small moments of life. Status colors are muted (green/ochre/brick), always paired with a tint surface. No gradients anywhere.
- **Type:** Outfit for display/headings (geometric, friendly terminals), Figtree for body/UI, Spline Sans Mono for data & code. Headings tight (-0.02em, 1.1 leading); body 15px/1.55. Overlines are 12px Outfit semibold, +0.08em, uppercase.
- **Spacing:** 4px base scale (`--space-1…11`), comfortable density (~4/10). Controls: 32/40/48px heights. Page max 1200px, prose max 720px, 24px gutters.
- **Backgrounds:** flat bright white; sections separated by hairline borders (`--border-subtle`) or a faint sunken panel (`--surface-sunken: #f6f6f4`) — never gradients, textures, or imagery washes. Marketing hero = white with big ink type.
- **Borders:** 1px hairlines, `--border-subtle` (#ececea) inside cards/dividers, `--border-default` (#dcdcd8) on inputs. `--border-strong` (ink) marks selected states.
- **Shadows:** whisper-quiet. Cards: `--shadow-card` (1px). Popovers/menus: `--shadow-raised`. Dialogs: `--shadow-overlay`. No inner shadows, no colored shadows.
- **Radii:** 6px small (badges, inputs' inner bits), 8px controls, 10px cards, 16px dialogs/large panels, pill for tags & switches. Never fully-square, never blob-round on containers.
- **Cards:** white, 1px `--border-subtle`, 10px radius, `--shadow-card`, 20–24px padding. Sunken variant swaps white for `--ink-1` and drops the shadow.
- **Animation:** brief and functional — 120–180ms, `--ease-out`, opacity + small translate (4–8px). No bounces, no spring theatrics. Dialogs fade+scale from .98.
- **Hover:** ink surfaces lighten (`--interactive-hover`), quiet elements gain `--ink-1` wash. **Press:** darken to true black + no shrink transforms. **Focus:** 3px soft ring (`--shadow-focus`), visible on keyboard focus.
- **Transparency/blur:** essentially none. Scrims are flat `rgba(20,20,19,.4)`. No backdrop blur.
- **Imagery:** when photography appears (marketing), it is neutral-warm, high-key, plenty of white in frame; slight desaturation OK; no duotones or heavy grade.
- **Dark mode:** `[data-theme="dark"]` scope; warm near-black (#161615) pages, same geometry, inverted ink roles.

## ICONOGRAPHY
- No proprietary icon set was provided. The system uses **Lucide** (CDN, `lucide.dev`) as its icon language — 1.75px stroke weight at 16–20px sizes matches the geometric-friendly type. Load via `https://unpkg.com/lucide@latest` and `lucide.createIcons()`, or inline copied SVGs.
- Icons are always monochrome `currentColor`, never multicolor, never filled variants.
- No emoji, no unicode-glyph icons. **Substitution flag:** if Leeworks adopts a bespoke icon set later, drop the SVGs into `assets/icons/` and update this section.

## Index
- `styles.css` — global entry (imports everything under `tokens/`).
- `tokens/` — `fonts.css`, `colors.css`, `typography.css`, `spacing.css`, `effects.css`.
- `guidelines/` — foundation specimen cards (Design System tab).
- `components/forms/` — Button, IconButton, Input, Select, Checkbox, Radio, Switch.
- `components/display/` — Card, Badge, Tag, Icon.
- `components/navigation/` — Tabs.
- `components/feedback/` — Dialog, Toast, Tooltip.
- `ui_kits/dashboard/` — Leeworks web app (analytics/workspace dashboard).
- `ui_kits/website/` — marketing site (homepage).
- `ui_kits/mobile/` — mobile app screens.
- `SKILL.md` — agent-skill entry point.

## Intentional additions
Standard component set authored from scratch (no source inventory existed). Lucide adopted as icon set (flagged above). `Icon` component wraps an inlined Lucide subset so kits never hand-roll SVG.

## Caveats
- **Fonts are CDN-served Google Fonts** (Outfit, Figtree, Spline Sans Mono) — no binaries in-project. Provide licensed font files to ship offline.
- No logo exists; wordmark is plain Outfit type. Provide a real mark if one exists.
