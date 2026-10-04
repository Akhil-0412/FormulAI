# FormulAI — 2026 Intelligence Center
### Design brief for Stitch (Google AI UI design tool)

Paste this whole document into Stitch as your project brief, then generate screen-by-screen using the prompts in Section 5.

---

## 1. What this product is

FormulAI is a Formula 1 prediction and analytics dashboard for the 2026 season. It shows the next race countdown, a Monte-Carlo podium prediction (10k simulations), season standings, driver/team/track libraries, a race-by-race results archive, and an AI chat agent ("ParcFermé AI") for asking questions about drivers, regulations, and telemetry.

Tone: serious motorsport broadcast graphics — think F1TV / Sky Sports F1 data overlays — not a generic SaaS dashboard. Confident, dark, data-dense but uncluttered. No glassmorphism, no gradient mesh backgrounds, no bouncy micro-animations. Depth comes from flat elevation steps, not blur or glow.

---

## 2. Visual system

### Color — true black ground, one red accent
Surfaces are near-black and stepped by *elevation*, not opacity/blur:

| Token | Hex | Use |
|---|---|---|
| ink-0 | `#000000` | outermost page plane |
| ink-1 | `#070708` | app frame background |
| ink-2 | `#0e0e10` | card |
| ink-3 | `#16161a` | raised card / chip |
| ink-4 | `#1e1e24` | hover / active chip |
| fg | `#ffffff` | primary text |
| fg-muted | `#9b9ba4` | secondary text |
| fg-subtle | `#5f5f68` | tertiary / labels |
| accent | `#e80020` | F1 red — reserved for emphasis only, never a background wash |
| accent-hot | `#ff2038` | hover/active state of accent |
| accent-dim | `#7a0616` | accent border on dark fills |
| live | `#ff2038` | live/pulsing status dot |
| good | `#35d07f` | positive delta, completed state |
| warn | `#ffb020` | caution, star/favorite marker |
| neutral | `#6f7480` | inactive/default badge |
| hairline | `rgba(255,255,255,0.07)` | default border |
| hairline-strong | `rgba(255,255,255,0.14)` | emphasized border, focus state |

Rule: the accent red is used for one hero glow, active nav states, live badges, and the top-1 podium highlight — never as a repeated decorative color across many elements.

Team colors (used as thin identity accents — a 2px top hairline on a card, a rail dot — never a full card background):
Mercedes `#00D2BE`, Ferrari `#E80020`, Red Bull `#3671C6`, McLaren `#FF8000`, Aston Martin `#229971`, Alpine `#0093CC`, Williams `#64C4FF`, Racing Bulls `#6692FF`, Haas `#B6BABD`, Audi `#00E701`, Cadillac `#B59A6A`.

### Typography
One grotesque sans (Geist, or Inter/Söhne Mono-adjacent as substitute) used at two extremes — no display/script face:
- **Display heading**: clamp 30–46px, line-height 1.02, letter-spacing -0.03em, weight 700. Page hero titles (race name, "Circuits", "Standings").
- **Section heading**: clamp 22–30px, line-height 1.1, letter-spacing -0.022em, weight 700. Card/section titles.
- **Card heading**: 15px, weight 650, letter-spacing -0.01em.
- **Micro label**: 10px, uppercase, letter-spacing 0.14em, weight 600, color fg-subtle. Used constantly for eyebrow labels ("PREVIOUS", "P1", "MONTE CARLO · 10K SIMS").
- All numeric values (points, lap times, countdown digits, percentages) use tabular/monospaced figures so columns align.

### Shape & elevation
- Radii: chip 12px, card 18px, outer app frame 28px.
- Cards: flat fill (ink-2) + 1px hairline border. No shadow, no gradient fill.
- Hover state = surface lightens one step (ink-2 → ink-3) + border brightens. Cards never translate/lift/scale on hover (scale is reserved for a couple of deliberate motion moments, see below) — "moving on hover" is explicitly the thing this design avoids because it reads as templated.
- One exception: a single soft radial red bloom (16% opacity, red → transparent, positioned top-right) behind the hero title on the home page — the only glow in the whole system.

### Motion
- Nav active-state indicator slides between icons with a spring (stiffness 380, damping 32), not a fade.
- Track/team cards expand in place with a FLIP-style layout animation (grid span change animates smoothly rather than snapping).
- A floating bottom dock recedes to 62% opacity + slight downward drift when idle/scrolling, and snaps to 100% opacity + blur on hover/focus/pointer contact.
- Respect `prefers-reduced-motion`: collapse all of the above to instant/near-instant.

---

## 3. App shell & navigation

**Frame**: the whole app is a single rounded card (radius 28px, ink-1 fill, hairline border) inset ~12–16px from a pure-black page plane, filling the viewport height. Content scrolls inside this frame, not the window.

**Top bar** (inside the frame, not sticky): left-to-right —
1. Wordmark "formul" in white + "AI" in accent red, tight tracking, no logomark/icon.
2. A circular search icon button (ink-2 fill, hairline border).
3. A pill showing a 4-avatar overlapping cluster + "20 of 20 on the grid" (real roster status, not decoration).
4. A pill showing "10 teams".
5. Right-aligned: a "Live" pill with a pulsing red dot, and a two-line right-aligned label ("2026 Season" / "Intelligence Center" in accent).

**Primary navigation**: a floating pill-shaped dock, fixed to bottom-center, icon-only (Home, Schedule, Results, Standings, Tracks, Teams, Predictions, ParcFermé AI, How It Works, plus a trailing Settings icon after a divider). Active item gets a soft red-wash rounded highlight behind the icon. Hovering an icon reveals a small tooltip label above it. The dock is translucent/blurred and low-contrast at rest, sharpens on hover/focus, and dims further while the page is actively scrolling.

---

## 4. Core components (reuse across screens)

- **Section heading**: title in Section-heading style + baseline-aligned small uppercase meta label to its right (e.g. "Season form" / "Finishing position · 24 rounds") + an optional right-aligned link ("All results →").
- **Stat tile**: card with a micro label, then a huge (34px) bold number, then an optional muted subtext. Has an "accent" variant that fills solid red with white text, used for one hero metric per page (e.g. "Season accuracy").
- **Chip row**: horizontal scrolling row of pill buttons, each showing a bold top value ("04") and a smaller muted bottom value ("Tue"); active chip fills solid accent red. Used for round/date pickers.
- **Badge**: small pill, tabular-numeric text. Tones: neutral (gray fill), accent (solid red), good (green tint), warn (amber tint), live (red tint + pulsing dot).
- **Driver avatar**: circular crop of a full-body driver cutout, optional colored ring in the driver's team color.
- **Avatar cluster**: 3–4 overlapping circular avatars with a "+N" overflow badge.
- **Podium prediction card**: a card per predicted finishing position (P1/P2/P3). Thin 2px team-color hairline across the top edge (not a full-height rail). Header row = avatar + driver name + team name (colored) + probability badge. Below a hairline divider: a "Monte Carlo · 10k sims" label and a dot-grid visualization (a grid of small dots, a portion of them lit in accent red proportional to the win probability — think a 10×10 dot matrix as a more literal, countable alternative to a progress bar).
- **Position trace chart**: a line chart, one line per driver in their team color, X axis = race rounds, Y axis = finishing position (inverted, P1 at top), with a dashed projection segment extending to the next (not-yet-run) race.
- **Race filmstrip** (home hero): a three-panel row — left panel (20% width, dimmed) = previous race summary with a result checkmark; center panel (60% width, full-bright, red glow behind title) = next race name, date, circuit, and a live countdown ("Lights out in" DD:HH:MM:SS, seconds digit in accent red); right panel (20%, dimmed) = upcoming race summary. On narrow viewports only the center panel shows.
- **Expandable team card**: collapsed = team name, chassis code, car cutout image, row of small driver code chips. Click expands the card (spanning 2 grid columns) to reveal a stats block (total wins, championships, track record) and a driver lineup list with avatars, animating the grid smoothly rather than snapping.
- **Track card**: card with circuit-layout artwork, locality name, and a status badge (gold star = on this year's calendar, red check + ring = already raced). Clicking opens an expanded detail view (shared-element transition from the grid card).
- **Standings row**: rank number, avatar, name + team (team-colored subtext), points — right-aligned bold number. Rows use the "raised" card surface (one step lighter than the page card that contains them) and lighten further on hover.

---

## 5. Screens to generate in Stitch

Generate these as separate screens/frames, all sharing the shell, nav dock, and token system above.

**1. Home / Intelligence Center** (`/`)
Top bar, then the three-panel race filmstrip hero. Below: a two-column body — left column (flexible width) has a "Season form" card containing the position-trace chart, then a "Predicted podium" section with three podium prediction cards side by side. Right column (fixed ~320px rail) stacks: a "Standings" card (top-3 driver rows, expandable to full list), a "Constructors" card (top-3 team rows with logo + points), and one accent Stat Tile for season prediction accuracy.

**2. Schedule** (`/schedule`)
Full 2026 calendar as a vertical list or grid of race cards — round number, name, circuit, date, and a status indicator (completed/upcoming). Page hero uses the Display-heading style ("Schedule").

**3. Results** (`/results`)
Display heading "Results". A toggle for historical seasons. Below, one expandable block per completed race showing final classification.

**4. Standings** (`/standings`)
Display heading "Standings". Two Section-heading blocks side by side or stacked: full Drivers standings list and full Constructors standings list, using the standings-row component, each with an entry-count meta label.

**5. Tracks** (`/tracks`)
Display heading "Circuits". A responsive grid (1/2/3 columns) of track cards as described above. Clicking a card opens a large detail overlay with the circuit name as a Display heading and expanded circuit art.

**6. Teams** (`/teams`)
Display heading "Constructors". A responsive grid of the expandable team cards described above.

**7. Predictions** (`/predictions`)
The most data-dense screen — a scroll-driven narrative ("scrollytelling") rather than a static dashboard:
- A "cinematic pipeline" strip showing simulation stages running live (e.g. "Loading grid…", "Running 10,000 Monte Carlo simulations…", "Resolving DNF risk…") with status states (pending/running/done/error).
- A weather + circuit info strip (temperature, rain probability, wind, humidity icons; circuit type, lap count, overtake difficulty).
- A full-grid probability table: every driver's position, podium/P1/P2/P3 probability, DNF risk, expected lap time, and constructor — sortable/scannable rows.
- A "Podium Stage" visual — three driver avatars on a literal podium riser (P2/P1/P3 heights), P1 in the center and tallest.
- Scrolling chapters that narrate the model's reasoning per driver (feature attribution / SHAP-style: which factors pushed a driver's probability up or down), presented as full-viewport chapter sections with a heading + supporting visual per chapter.

**8. ParcFermé AI** (`/parcferme`)
A chat interface: centered column (max ~5xl width), header "ParcFermé AI" with a subtitle "Autonomous Strategic Intelligence Engine". Suggested-prompt chip row shown before the first message. Message list — assistant messages have a bot-icon avatar on the left, user messages align right with a user-icon avatar; assistant bubbles can inline render a line/bar chart, a data table, or a small track-map with driver markers, plus an "Entities" chip row under long responses. Sticky bottom input bar with a chevron prompt icon, text field, and a send button.
> Design note: bring this screen's palette onto the ink/red token system above — the current build still uses a leftover teal accent, italic script logotype, and glassy `bg-black/40` panels from an earlier design pass, which reads as a second product bolted onto the rest of the app. Recreate it in ink-2/ink-3 cards, accent red for the active/live indicator, and the same Geist type scale as every other screen.

**9. How It Works** (`/how-it-works`)
An explainer/marketing-style scrollytelling page: hero chapter with the "FORMULAI" wordmark at Display-heading scale, followed by chapters (Data Ingestion → Model → Monte Carlo → Podium) each pairing a heading/copy block with a supporting visual — including a rotating 3D wireframe car rendered on canvas as a recurring motif across chapters, plus a scanline/data-stream decorative treatment reinforcing the "telemetry" feel.

---

## 6. What to avoid

- No glassmorphism / frosted panels as a default surface (the one exception is the floating bottom nav dock, which is *allowed* to blur because it floats over content).
- No colored gradient backgrounds or ambient glow blobs beyond the single hero bloom described above.
- No card lift/translate/shadow-bloom on hover.
- No icon-in-a-circle before every section title — hierarchy comes from type, not ornament.
- No decorative color: team colors and status colors (good/warn/live) always mean something specific; never used as arbitrary UI decoration.
