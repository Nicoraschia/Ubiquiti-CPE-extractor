# Design System — CPE Scanner

## Product Context
- **What this is:** internal web inventory of Ubiquiti airOS antennas (APs and CPEs), with AP -> CPE links, signal and the LAN routers behind each CPE.
- **Who it's for:** ISP support and NOC technicians. UI in Rioplatense Spanish.
- **Space:** network monitoring tools (UISP, LibreNMS, Grafana).
- **Project type:** data-dense internal tool. 500-3000 devices.
- **Memorable thing:** "you find the problem in seconds".

## Aesthetic Direction
- **Direction:** industrial / utilitarian. A measuring instrument, not a website.
- **Decoration:** minimal. Typography and state color do all the work.
- **Mood:** calm, precise, dense. The screen stays quiet until something fails.

## Typography
- **Display / headings / table headers / big numbers:** IBM Plex Sans Condensed 500-600. Condensed lets more columns fit.
- **Body / UI:** IBM Plex Sans 400-600.
- **Data (MAC, IP, dBm, durations):** IBM Plex Mono 400-500, `font-variant-numeric: tabular-nums`.
- **Loading:** `next/font/google` (self-hosted at build time; no requests to Google from the browser).
- **Scale:** 32 (page h1) · 20 (section title) · 16 (panel title) · 14 (base) · 13 (secondary UI) · 12.5 (mono in tables) · 11.5 (headers, caps +0.06em).

## Color
- **Approach:** restrained. **No brand color: on screen, color only means state.** A red row is always a problem.

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg` | #0C0E10 | #F6F7F8 | background, inputs |
| `--surface` | #13161A | #FFFFFF | panels, tables |
| `--raised` | #1A1E23 | #EEF0F2 | hover, secondary buttons |
| `--border` | #262B31 | #D9DDE1 | dividers |
| `--border-strong` | #343A42 | #C3C9CF | input and button borders |
| `--text` | #E6E8EA | #14171A | text; primary button background |
| `--muted` | #8A9199 | #5D6670 | labels, secondary data |
| `--faint` | #5B626B | #8A929B | placeholders, vendor |
| `--ok` | #3FB97A | #1F8A55 | signal >= -65 dBm, success |
| `--warn` | #E5A50A | #A86E00 | signal -65 to -75, warning |
| `--crit` | #F0524F | #C93432 | signal < -75, error, destructive |
| `--nodata` | #5B626B | #8A929B | no signal / not seen |
| `--accent` | #5AC8E6 | #0B7FA3 | focus, selection, links (never state) |

- **Signal thresholds (airOS dBm):** ok >= -65, warn -65..-75, crit < -75. They live in one place in the code (`lib/signal.ts`).
- **Never color alone:** the signal meter combines 4 bars (lit count = shape), color, and the number.
- **Primary button:** inverted (`--text` background, `--bg` text). No gradients.

## Spacing
- **Base:** 4px. **Density:** compact. Table rows 32px, headers 30px, controls 32px (chips 28px).
- **Scale:** 2 · 4 · 8 · 12 · 16 · 20 · 24 · 32 · 48.

## Layout
- **Shell:** 52px icon rail (Equipos, APs, Routers LAN, Escaneos, Subnets, Usuarios, Auditoria) + 52px top bar with global search (`/` or Cmd+K) and the user/role.
- **Global search is the main navigation:** a MAC, IP, client or router name jumps to the detail.
- **Tables:** sticky header, the sorted column in `--text`, critical row with a 2px `--crit` inner edge on the left, selected row with `--accent-bg` and a cyan edge.
- **Radius:** sm 4 (chips, kbd) · md 6 (buttons, inputs) · lg 8 (panels). Nothing rounder.
- **Responsive:** primary use is desktop. On mobile the tables keep their key columns (name, signal, AP) with no page-level horizontal scroll.

## Motion
- **Approach:** minimal-functional. 120-180ms ease-out on hover/focus/state.
- The only continuous motion: a soft pulse on the dot of a running scan.
- `prefers-reduced-motion: reduce` turns all of it off.

## Accessibility
- Visible focus everywhere: 2px `--accent` outline, offset 2.
- Body text contrast >= 4.5:1 in both themes.
- Real labels on every input; errors with `aria-invalid` and text, not just a red border.
- Tables with `<th scope>`; the signal meter carries `aria-label="Senal -74 dBm, atencion"`.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-22 | Initial system created | /design-consultation. Memorable: "find the problem in seconds". |
| 2026-11-22 | No brand color | Color reserved for state so problems stand out with nothing to compete against. |
| 2026-11-22 | IBM Plex (Sans/Condensed/Mono) | Network-gear feel, excellent tabular digits, condensed fits more columns. Inter rejected for being generic. |
| 2026-11-22 | Signal = bars + color + number | Readable for colorblind users and at a glance. |
