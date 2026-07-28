# Handoff: Pulse FM — Music Player (Desktop + Mobile)

## Overview
A minimal, monospace-inflected music player in two viewports: a 1280×800 desktop
player and a 390×844 mobile player. Both share one visual language — bone-white
canvas, a black transport sheet pinned to the bottom, a full-width mirrored-bar
waveform visualizer, dot-matrix (Doto) micro-labels, and a single red accent.

The interactive core is small: one play/pause toggle per viewport that starts and
stops the waveform animation.

## About the Design Files
The files in this bundle are **design references created in HTML** — prototypes that
show intended look and behavior. They are **not production code to copy directly**.
The task is to **recreate these designs in your codebase's existing environment**
(React, Vue, Svelte, SwiftUI, native, etc.) using its established patterns, component
primitives, and styling conventions. If no environment exists yet, pick the framework
appropriate for the project and implement there.

Styling in this handoff is documented as **Tailwind CSS** utilities and theme tokens
(see *Design Tokens*). The prototype itself uses inline styles; the Tailwind mapping
below is the intended production representation.

## Fidelity
**High-fidelity.** Colors, typography, spacing, radii, and animation timings are final.
Recreate the UI pixel-accurately using your codebase's libraries and patterns.

---

## Design Tokens

### Tailwind theme extension
Add these to your Tailwind theme so the design reads as tokens, not magic numbers.
(v4 `@theme` shown first; v3 `tailwind.config.js` equivalent in `tailwind.tokens.css`.)

```css
@theme {
  /* Color */
  --color-canvas: #DEDDD8;   /* page / desk background behind the app frames */
  --color-bone:   #EDECE7;   /* app surface (both viewports) */
  --color-ink:    #111111;   /* text on bone; transport sheet background */
  --color-paper:  #F2F1EF;   /* text on ink; filled progress track */
  --color-accent: #D6252B;   /* play button, live dot, waveform playhead bar */

  /* Type */
  --font-sans: "Helvetica Neue", Helvetica, Arial, sans-serif;
  --font-mono: "Doto", ui-monospace, monospace;  /* dot-matrix micro-labels */

  /* Radius */
  --radius-app:    16px;  /* desktop window */
  --radius-device: 46px;  /* mobile device frame + sheet bottom corners */
  --radius-sheet:  34px;  /* mobile sheet top corners */

  /* Shadow */
  --shadow-frame: 0 40px 80px -30px rgb(0 0 0 / 0.35);

  /* Motion */
  --ease-viz: cubic-bezier(0.4, 0, 0.6, 1); /* ease-in-out */
}
```

Font: **Doto** (weights 400/600/800) from Google Fonts, used only for uppercase
micro-labels and numerals. **Helvetica Neue** for track titles and body.

### Alpha values on ink/paper
These recur; express them as Tailwind opacity modifiers.

| Use | Value | Tailwind |
|---|---|---|
| Unfilled progress track (on ink) | `rgba(242,241,239,.18)` | `bg-paper/[.18]` |
| Secondary label (on ink) | `opacity: .5`–`.6` | `text-paper/50`, `/60` |
| Secondary label (on bone) | `opacity: .45` | `text-ink/45` |
| Trailing (unplayed) waveform bars | `opacity: .22` | `opacity-[.22]` |
| Paused waveform bars | `opacity: .5` | `opacity-50` |

### Typography scale (exact)

| Role | Family | Size | Weight | Letter-spacing | Notes |
|---|---|---|---|---|---|
| Desktop track title | sans | 56px | 500 | -0.035em | `text-[56px] font-medium tracking-[-0.035em]` |
| Mobile track title | sans | 23px | 500 | -0.02em | truncates with ellipsis, `whitespace-nowrap` |
| Micro-label / nav | mono | 11px | 600 | 0.22em | uppercase |
| Sub-label (artist line) | mono | 12px | 500 | 0.20em–0.24em | uppercase |
| Timecode | mono | 11px | 400 | 0.16em | |

### Spacing
Frame padding is on a 2px-friendly scale; use arbitrary values where Tailwind's
scale doesn't land exactly.

| Token | Value | Tailwind |
|---|---|---|
| Desktop gutter | 44px | `px-11` |
| Desktop header top | 30px | `pt-[30px]` |
| Mobile gutter | 28–30px | `px-7` / `px-[30px]` |
| Mobile header top | 26px | `pt-[26px]` |
| Transport sheet height (desktop) | 126px | `h-[126px]` |
| Waveform bar gap | 3px | `gap-[3px]` |

---

## Screens / Views

### 1. Desktop Player — 1280 × 800

**Purpose:** Primary listening surface. Track identity centered, waveform as the
hero graphic, transport controls always docked at the bottom.

**Layout:** Vertical flex column inside a `1280×800` frame.
`rounded-[16px] bg-bone text-ink overflow-hidden relative shadow-frame`

1. **Header** — `flex justify-between items-center px-11 pt-[30px]`, mono 11px/600/0.22em.
   - Left: 6px red dot (`size-1.5 rounded-full bg-accent`) + `PULSE FM` at `text-ink/45`.
   - Right: a `flex items-center gap-[26px]` group — `HOW IT WORKS` at `text-ink/45`, then a
     `LOGOUT` link (anchor, `text-ink/45`, `no-underline`, `tracking-[0.22em]`, hover → full
     opacity) sitting at the far right edge. **These are the only nav items** — no Player /
     Search / Library.
2. **Stage** — `flex-1 flex flex-col justify-center items-center gap-[34px] pb-10`
   - Title block, centered: `Nightshift Drift` (56px/500/-0.035em) and below it,
     margin-top 14px, mono 12px/0.24em `text-ink/45`: `SABLE UNIT / WAVEFORM STEREO`.
   - Waveform, `w-full`, 60 bars, 260px tall, 60px horizontal padding. See *Waveform*.
3. **Spacer** — `h-[126px]` reserving room for the absolutely-positioned sheet.
4. **Transport sheet** — `absolute inset-x-0 bottom-0 h-[126px] bg-ink text-paper
   flex items-center gap-10 px-11`
   - Play button: `size-[66px] rounded-full bg-accent` grid-centered glyph,
     `cursor-pointer hover:scale-105`.
   - Progress row: `flex-1 flex items-center gap-4`
     - `03:02` timecode `text-paper/60`
     - Track: `flex-1 h-0.5 bg-paper/[.18] relative`; filled portion
       `absolute inset-y-0 left-0 right-[22%] bg-paper`; playhead
       `absolute -top-[3px] left-[78%] size-2 rounded-full bg-accent`.
     - `03:52` timecode `text-paper/60`

### 2. Mobile Player — 390 × 844

**Purpose:** Same player, one-handed. The transport becomes a black sheet that rises
from the bottom of the device and carries title + controls together.

**Layout:** Vertical flex column, `rounded-[46px] bg-bone text-ink overflow-hidden
relative shadow-frame`

1. **Header** — `flex justify-between items-center px-7 pt-[26px]`, mono 11px/600/0.22em.
   - Left: red dot + `PULSE FM` (`text-ink/45`). Right: `LOGOUT` link (`text-ink/45`,
     `no-underline`, `tracking-[0.22em]`, hover → full opacity). Mobile shows LOGOUT only —
     no `HOW IT WORKS`.
2. **Stage** — `flex-1 flex flex-col justify-center gap-6`
   - Mono 11px/0.22em label `WAVEFORM / STEREO` at `text-ink/45`, `px-[30px]`.
   - Waveform: 30 bars, 190px tall, 30px horizontal padding.
3. **Transport sheet** — `bg-ink text-paper rounded-t-[34px] rounded-b-[46px]
   px-[30px] pt-[30px] pb-10`
   - Top row: `flex items-center justify-between gap-5`
     - Left: title `Nightshift Drift` (23px/500/-0.02em, truncate) + `SABLE UNIT`
       (mono 12px/0.20em, `text-paper/50`, margin-top 7px).
     - Right: play button `size-16 rounded-full bg-accent`, `hover:scale-105`.
       ⚠️ 64px meets the 44px minimum hit target; keep it at or above 44px.
   - Progress row (margin-top 26px): `flex items-center gap-3.5` — `03:02`,
     track (`flex-1 h-0.5 bg-paper/[.18]`, filled `right-[22%] bg-paper`,
     **no playhead dot on mobile**), `03:52`.

---

## Components

### Waveform (mirrored bars)
The signature element. A horizontal row of vertically-centered bars whose heights
follow a fixed deterministic profile; playback animates each bar's `scaleY`.

**Geometry**
- Container: `flex items-center gap-[3px] w-full`, fixed height, horizontal padding.
- Each bar: `flex-1`, height set as a **percentage of container height**,
  `transform-origin: center` (bars grow up and down — hence "mirrored").

**Height profile** — deterministic, not random, so the shape is stable across renders:
```js
const amp = i => 0.28 + 0.72 * Math.abs(Math.sin(i * 1.7 + Math.cos(i * 0.6)));
// bar i height = `${amp(i * 1.3) * 100}%`
```

**Per-bar color and opacity** (n = total bars)
| Condition | Treatment |
|---|---|
| `i > n*0.62 && i < n*0.66` | `bg-accent` — the playhead bar(s) |
| `i > n*0.66` | `opacity-[.22]` — unplayed tail |
| otherwise, playing | `bg-ink`, full opacity |
| otherwise, paused | `bg-ink`, `opacity-50` |

**Animation**
```css
@keyframes mirrorPulse {
  0%, 100% { transform: scaleY(.18); }
  50%      { transform: scaleY(1); }
}
```
- Playing: `animation: mirrorPulse <dur> ease-in-out <delay> infinite`
  - `dur  = (1.2 + (i % 6) * 0.09) / speed` seconds — six interleaved tempos
  - `delay = i * 0.035` seconds — creates the left-to-right ripple
  - `speed` defaults to 1
- Paused: no animation, bars rest at `scaleY(1)` (full profile height) at 50% opacity.

Instance parameters:
| Viewport | Bars | Height | Padding |
|---|---|---|---|
| Desktop | 60 | 260px | 60px |
| Mobile | 30 | 190px | 30px |

**Note:** 60 animated DOM nodes per waveform is fine for a prototype. In production,
prefer a single `<canvas>` or CSS-only variant, and always gate the animation behind
`@media (prefers-reduced-motion: reduce)` → render the static paused state.

### Play / Pause glyph
Pure geometry, no icon font.
- **Playing** (shows pause): two bars, `flex gap-[5px]`, each `w-1 h-[18px]`,
  color `paper` — scaled 0.9× in both viewports (so ~3.6 × 16.2px, gap 4.5px).
- **Paused** (shows play): a right-pointing triangle via borders —
  `border-left: 16px solid paper; border-top/bottom: 10px solid transparent`,
  `margin-left: 4px` for optical centering. Also 0.9× scaled.

Recreate with an SVG or your icon set; keep the optical left-offset on the triangle.

### Progress track
`h-0.5` (2px) rail, `bg-paper/[.18]`; filled span absolutely positioned from the
left to `right: 22%` in `bg-paper` (i.e. **78% played**). Desktop adds an 8px
`bg-accent` playhead dot at `left: 78%`, `top: -3px`. Static in the prototype —
wire to real playback position.

---

## Interactions & Behavior
- **Play/pause** — clicking either play button toggles that viewport's playing state.
  Effect: glyph swaps pause↔play, and every waveform bar's animation is added/removed.
  Each viewport holds its own state in the prototype; in production this is one
  shared playback state.
- **Hover** — play buttons: `hover:scale-105`. Nothing else has a hover state.
- **Transitions** — the prototype has none on the scale (instant). Add
  `transition-transform duration-150` in production for polish.
- **Not built** (out of scope, but the layout anticipates them): seeking/scrubbing,
  prev/next, volume, queue, and the `HOW IT WORKS` / `LOGOUT` destinations (both are
  static links in the mock).
- **Responsive** — the two viewports are discrete targets, not a fluid range. The
  meaningful breakpoint behavior: below ~`md`, use the mobile composition (title
  moves *into* the black sheet, waveform bar count and height drop, playhead dot
  disappears); at `md` and above, the desktop composition (centered title above the
  waveform, full-width docked sheet).

## State Management
Minimal:
```ts
type PlayerState = {
  isPlaying: boolean;      // drives glyph + waveform animation
  positionMs: number;      // → progress fill % + timecodes (static 78% in prototype)
  durationMs: number;      // 03:52 in prototype
  track: { title: string; artist: string };
};
```
No data fetching in the prototype; all content is hard-coded. In production, drive
`isPlaying`/`positionMs` from the audio element or playback SDK, and derive the
waveform's per-bar heights from real analysis data (the `amp()` function is a
placeholder for that).

### Tunable parameters (exposed as controls in the prototype)
Worth keeping as props/config rather than constants:
- `accent` — accent color. Alternates tested: `#D6252B` (default), `#111111`,
  `#4A7DFF`, `#C8FF3D`.
- `speed` — waveform animation speed multiplier, 0.3–2.5, default 1 (divides duration).
- `density` — bar-count multiplier, 0.5–1.6, default 1 (multiplies base bar count,
  floored at 8).

## Content / Copy (exact)
- Brand: `PULSE FM`
- Nav (desktop): `HOW IT WORKS` + `LOGOUT` (logout far right)
- Nav (mobile): `LOGOUT` only
- Track: `Nightshift Drift` — artist `SABLE UNIT`
- Desktop sub-label: `SABLE UNIT / WAVEFORM STEREO`
- Mobile stage label: `WAVEFORM / STEREO`
- Timecodes: `03:02` elapsed, `03:52` total

## Assets
None. No images, no icon fonts, no SVG files — every graphic element (dots, bars,
play/pause glyph, progress rail) is built from divs/borders. The only external
dependency is the **Doto** webfont from Google Fonts:
`https://fonts.googleapis.com/css2?family=Doto:wght@400;600;800&display=swap`
Self-host it in production.

## Files
- `Music Player Final.dc.html` — the design reference. Open in a browser; both
  viewports render side by side and the play buttons work.
- `support.js` — runtime required by the reference file. Not part of the design;
  do not port it.
- `tailwind.tokens.css` — the theme tokens above, plus a v3 `tailwind.config.js`
  equivalent in comments, ready to paste.
