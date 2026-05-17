# CLI Reference

Complete reference for the `spacetrack` CLI (10 commands). All commands run
from the project root in PowerShell.

## Setup

```powershell
cd "C:\Users\maldo\OneDrive\Desktop\Space Project"
```

Then either prefix every call with the venv path:

```powershell
.\.venv\Scripts\spacetrack.exe <command>
```

…or activate the venv once per session and drop the prefix:

```powershell
.\.venv\Scripts\Activate.ps1
spacetrack <command>
deactivate   # when done
```

If activation is blocked: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## Global options

```
spacetrack [--version] [--db-path PATH] [-v | --verbose] <command> ...
```

| Flag | Default | Notes |
|---|---|---|
| `--db-path PATH` | `data/spacetrack.db` | Override SQLite location |
| `-v`, `--verbose` | off | Debug logging |
| `--version` | — | Print version and exit |

---

## `update` — fetch latest TLEs

Pulls the Starlink catalog from CelesTrak and persists new snapshots
(idempotent — re-running without a fresh upstream is a no-op).

```powershell
spacetrack update
```

Run daily to build per-sat history for the trend-based detectors.

---

## `stats` — DB summary

Tracked sats, snapshot count, last update timestamp.

```powershell
spacetrack stats
```

---

## `where` — current position of one sat

```powershell
spacetrack where <IDENTIFIER> [--at ISO8601]
```

| Arg | Notes |
|---|---|
| `IDENTIFIER` | NORAD ID (e.g. `44713`) or name (e.g. `STARLINK-1007`) |
| `--at` | ISO-8601 UTC time. Default: now. Example: `2026-05-10T20:00:00Z` |

```powershell
spacetrack where STARLINK-1007
spacetrack where 44713 --at 2026-05-20T12:00:00Z
```

---

## `globe` — 3D globe of the whole constellation

Renders an interactive HTML globe (Plotly) with every tracked Starlink at the
chosen instant.

```powershell
spacetrack globe [-o PATH] [--at ISO8601] [--limit N]
                 [--color-by altitude|risk] [--pulse]
                 [--animate] [--frames N] [--step-min F] [--open]
```

| Flag | Default | Notes |
|---|---|---|
| `-o`, `--output` | `globe.html` | Output file |
| `--at` | now | Instant to plot |
| `--limit` | — | Plot only the first N sats (debug aid) |
| `--color-by` | `altitude` | `altitude` (Plasma colorbar) or `risk` (decay tiers) |
| `--pulse` | off | Pulse imminent markers (requires `--color-by risk`) |
| `--animate` | off | Add a time slider stepping through future positions |
| `--frames` | 9 | Number of slider frames when `--animate` is set |
| `--step-min` | 15 | Minutes between frames when `--animate` is set |
| `--thin` | 1 | Keep every Nth nominal sat (flagged always kept). Try 3-5 for smoother rotation. |
| `--open` | off | Auto-open in browser |

> **Performance tip.** Plotly's `Scattergeo` re-projects every marker on each
> rotation tick, so 10k+ sats can feel laggy. Use `--thin 4` (keeps every
> 4th nominal sat) to cut SVG load ~75% with no impact on flagged-sat
> visibility. For maximum smoothness, use `globe-deck` instead — it's
> GPU-accelerated.

```powershell
spacetrack globe --open
spacetrack globe --color-by risk --pulse --open
spacetrack globe --color-by risk --animate --frames 13 --step-min 10 --open
```

---

## `globe-deck` — GPU globe with NASA Blue Marble (deck.gl)

Renders a deck.gl ``GlobeView`` HTML page with a photorealistic Earth
backdrop (NASA Blue Marble bitmap) and GPU-accelerated marker rendering.
Smoother than Plotly's globe at full constellation scale.

```powershell
spacetrack globe-deck [-o PATH] [--at ISO8601] [--limit N]
                      [--color-by altitude|risk] [--open]
```

| Flag | Default | Notes |
|---|---|---|
| `-o`, `--output` | `globe-deck.html` | Output file |
| `--at` | now | Instant to plot |
| `--limit` | — | Plot only the first N sats |
| `--color-by` | `risk` | `risk` (decay tiers) — `altitude` not yet wired |
| `--open` | off | Auto-open in browser |

```powershell
spacetrack globe-deck --open
spacetrack globe-deck --limit 500 --open
```

---

## `track` — 2D ground track for one sat

Plots the satellite's sub-point over the next N orbits.

```powershell
spacetrack track <IDENTIFIER> [--orbits FLOAT] [--start ISO8601] [-o PATH] [--open]
```

| Flag | Default | Notes |
|---|---|---|
| `--orbits` | 2 | How many orbits forward to plot |
| `--start` | now | Start time, ISO-8601 UTC |
| `-o`, `--output` | `track-<NAME>.html` | Output file |
| `--open` | off | Auto-open in browser |

```powershell
spacetrack track STARLINK-1008 --orbits 3 --open
```

---

## `observe` — sky plot + elevation timeline for an observer

Default observer is Colorado Springs (lat 38.8339, lon -104.8214, alt 1839 m).

```powershell
spacetrack observe <IDENTIFIER> [--lat F] [--lon F] [--alt F] [--observer-name S]
                                [--hours F] [--step F] [--start ISO8601]
                                [-o PATH] [--open]
```

| Flag | Default | Notes |
|---|---|---|
| `--lat` / `--lon` / `--alt` | Colorado Springs | Observer location |
| `--observer-name` | — | Label shown on the chart |
| `--hours` | 6 | Time window |
| `--step` | 15 | Sample step (seconds) |
| `--start` | now | Window start, ISO-8601 UTC |
| `-o`, `--output` | `observe-<NAME>.html` | Output file |
| `--open` | off | Auto-open in browser |

```powershell
spacetrack observe STARLINK-1008 --open
spacetrack observe STARLINK-1008 --lat 40.7128 --lon -74.0060 --alt 10 `
                                 --observer-name "NYC" --hours 12 --open
```

---

## `live` — stream current position to the terminal

Reuses the most recent stored TLE; propagates every tick. No network calls.
Refresh TLEs in another window with `spacetrack update`.

```powershell
spacetrack live <IDENTIFIER> [--lat F] [--lon F] [--alt F] [--observer-name S]
                             [--interval F]
```

| Flag | Default | Notes |
|---|---|---|
| `--lat` / `--lon` / `--alt` | Colorado Springs | Observer location |
| `--observer-name` | — | Label in the header |
| `--interval` | 2.0 | Seconds between updates |

Ctrl+C to stop.

```powershell
spacetrack live STARLINK-1008 --interval 1
```

---

## `dashboard` — launch the Streamlit web UI

```powershell
spacetrack dashboard [--port INT] [--host STR]
```

| Flag | Default |
|---|---|
| `--port` | 8501 |
| `--host` | localhost |

```powershell
spacetrack dashboard
spacetrack dashboard --port 8600 --host 0.0.0.0
```

---

## `decay` — re-entry risk assessment (Phase 3)

Two modes: single-sat assessment or full-constellation scan.

```powershell
spacetrack decay <IDENTIFIER>                          # one sat
spacetrack decay --scan [--min-risk LEVEL] [--limit N] # whole constellation
```

| Flag | Default | Notes |
|---|---|---|
| `--scan` | off | Evaluate every tracked sat |
| `--min-risk` | `elevated` | One of `nominal`, `elevated`, `high`, `imminent` |
| `--limit` | — | Cap on `--scan` results |

Risk tiers (perigee-driven, with decay-rate overrides):
- `imminent` — perigee < 200 km
- `high` — perigee < 300 km, or decay rate < -5 km/day
- `elevated` — perigee < 450 km, or decay rate < -1 km/day
- `nominal` — otherwise

```powershell
spacetrack decay STARLINK-30237
spacetrack decay --scan --min-risk imminent
spacetrack decay --scan --min-risk elevated --limit 25
```

Output columns for `--scan`: RISK, NORAD, NAME, PERI(km), APO(km), dh/dt (km/day).
A `dh/dt` of `n/a` means only one snapshot exists for that sat.

---

## Common workflows

**Daily refresh + decay watch:**
```powershell
spacetrack update
spacetrack decay --scan --min-risk imminent
```

**One-sat deep look:**
```powershell
spacetrack where STARLINK-1008
spacetrack track STARLINK-1008 --open
spacetrack observe STARLINK-1008 --open
spacetrack decay STARLINK-1008
```

**Constellation snapshot:**
```powershell
spacetrack stats
spacetrack globe --open
```

---

## Paste-ready commands (no venv activation needed)

If you haven't activated the venv, prefix every command with `.\.venv\Scripts\`.
First navigate:

```powershell
cd "C:\Users\maldo\OneDrive\Desktop\Space Project"
```

### Help / global

```powershell
# All commands
.\.venv\Scripts\spacetrack.exe --help

# Help for any single command
.\.venv\Scripts\spacetrack.exe decay --help

# Version
.\.venv\Scripts\spacetrack.exe --version
```

### `update` — fetch latest TLEs

```powershell
.\.venv\Scripts\spacetrack.exe update
```

### `stats` — DB summary

```powershell
.\.venv\Scripts\spacetrack.exe stats
```

### `where` — current position of one sat

```powershell
.\.venv\Scripts\spacetrack.exe where STARLINK-1008
.\.venv\Scripts\spacetrack.exe where 44713
.\.venv\Scripts\spacetrack.exe where STARLINK-1008 --at 2026-05-20T12:00:00Z
```

### `globe` — 3D globe of the whole constellation

```powershell
# Altitude-colored (default)
.\.venv\Scripts\spacetrack.exe globe --open
.\.venv\Scripts\spacetrack.exe globe --limit 200 -o globe-sample.html --open
.\.venv\Scripts\spacetrack.exe globe --at 2026-05-20T12:00:00Z -o globe-future.html

# Decay-risk coloring (4 tiers)
.\.venv\Scripts\spacetrack.exe globe --color-by risk -o globe-decay.html --open

# Pulsing imminent-risk markers (thinned for smoother rotation)
.\.venv\Scripts\spacetrack.exe globe --color-by risk --pulse --thin 4 -o globe-decay-pulse.html --open

# Time slider: play through positions at successive instants
.\.venv\Scripts\spacetrack.exe globe --color-by risk --animate --frames 9 --step-min 15 --thin 4 -o globe-decay-animated.html --open
```

### `globe-deck` — GPU globe with NASA Blue Marble (deck.gl)

```powershell
# Default: risk coloring on a photorealistic Earth
.\.venv\Scripts\spacetrack.exe globe-deck --open
.\.venv\Scripts\spacetrack.exe globe-deck -o globe-deck.html --open
.\.venv\Scripts\spacetrack.exe globe-deck --limit 500 --open
```

### `track` — 2D ground track for one sat

```powershell
.\.venv\Scripts\spacetrack.exe track STARLINK-1008 --open
.\.venv\Scripts\spacetrack.exe track STARLINK-1008 --orbits 3 --open
.\.venv\Scripts\spacetrack.exe track 44713 --start 2026-05-20T00:00:00Z -o track-future.html
```

### `observe` — sky plot + elevation from observer location

```powershell
# Default observer (Colorado Springs)
.\.venv\Scripts\spacetrack.exe observe STARLINK-1008 --open

# Custom observer (NYC), 12-hour window
.\.venv\Scripts\spacetrack.exe observe STARLINK-1008 --lat 40.7128 --lon -74.0060 --alt 10 --observer-name "NYC" --hours 12 --open
```

### `live` — stream current position to the terminal (Ctrl+C to stop)

```powershell
.\.venv\Scripts\spacetrack.exe live STARLINK-1008
.\.venv\Scripts\spacetrack.exe live STARLINK-1008 --interval 1
.\.venv\Scripts\spacetrack.exe live STARLINK-1008 --lat 40.7128 --lon -74.0060 --alt 10 --observer-name "NYC"
```

### `dashboard` — launch Streamlit web UI

```powershell
.\.venv\Scripts\spacetrack.exe dashboard
.\.venv\Scripts\spacetrack.exe dashboard --port 8600
```

### `decay` — re-entry risk (Phase 3.1)

```powershell
# Top 25 flagged sats
.\.venv\Scripts\spacetrack.exe decay --scan --min-risk elevated --limit 25

# Only the most urgent (perigee < 200 km)
.\.venv\Scripts\spacetrack.exe decay --scan --min-risk imminent

# Drill into one satellite
.\.venv\Scripts\spacetrack.exe decay STARLINK-30237
.\.venv\Scripts\spacetrack.exe decay 57437
```
