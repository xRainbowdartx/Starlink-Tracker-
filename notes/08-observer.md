# Observer view — `spacetrack observe`

The observer feature turns "where is the satellite in space" into "where do I
look in the sky to see it from a specific location on Earth." Same problem
amateur astronomers and ground-station operators solve every day, and a
prerequisite for any future ground-station-side work (signal capture,
jamming detection, link analysis).

## Default observer

**Colorado Springs, CO** — chosen because the user lives there and it happens
to be the operational heart of US military space:

| Site | What happens there |
|---|---|
| Cheyenne Mountain Complex | NORAD, deep-state space situational awareness |
| Peterson SFB | US Space Force HQ |
| Schriever SFB | 2nd Space Operations Squadron — runs GPS |
| USSPACECOM | Combatant command for space |
| US Air Force Academy | Where future space cadre trains |

Real-world tie-in for a space-cybersecurity portfolio piece: hard to beat.

Coordinates used:
- **Latitude:** 38.8339° N
- **Longitude:** −104.8214° W
- **Altitude:** 1,839 m (slightly extends the geometric horizon vs. sea level)

Override on any invocation with `--lat`, `--lon`, `--alt`, `--observer-name`.

## What gets computed

For each step in a time window, three quantities relative to the observer:

| Quantity | Meaning | Unit |
|---|---|---|
| **Azimuth** | Compass bearing to the sat (0°=N, 90°=E, 180°=S, 270°=W) | degrees |
| **Elevation** | Angle above the horizon (0°=horizon, 90°=overhead) | degrees |
| **Range** | Straight-line distance from observer to satellite | km |

Math is delegated to Skyfield's topocentric frame: the library handles
ECI -> ECEF -> ENU rotations using IAU 2000A/2006 precession-nutation, so we
don't re-derive them by hand.

## Visibility thresholds

Two thresholds tracked and rendered separately:

| Threshold | Meaning | Why both? |
|---|---|---|
| **0° (horizon)** | Geometrically above the horizon | Theoretical visibility — what the math says |
| **10° (practical)** | Above typical obstructions | What you'd actually see — buildings, trees, atmosphere thicker at low angles |

Most amateur skywatchers and ham-radio satellite operators consider 10° the
realistic minimum.

## The rendered HTML

`spacetrack observe <sat> [opts]` writes a single HTML file with two
side-by-side panels:

### Left: polar sky plot
Fish-eye view of the sky. Center = **zenith** (straight up); outer ring = the
horizon. Compass directions on the edge. The colored path traces the
satellite's apparent motion across the sky during all time above the horizon.
Hover shows UTC time, az/el, range at each point.

### Right: elevation timeline
Elevation (°) vs. UTC time. Dotted reference lines at 0° and 10°. Each pass
window shaded:
- **Cyan band** — above 0° horizon
- **Orange band** — above 10° practical

Hover on the line reads elevation at each step.

## CLI examples

```powershell
# Default: Colorado Springs, next 6 hours
spacetrack observe STARLINK-1008

# Longer window to catch multiple passes
spacetrack observe STARLINK-1008 --hours 24

# A different observer — Cheyenne Mountain entrance
spacetrack observe STARLINK-1008 --lat 38.7440 --lon -104.8456 --alt 2154 --observer-name "Cheyenne Mountain"

# Start at a future UTC time
spacetrack observe STARLINK-1008 --start "2026-05-11T03:00:00Z"

# Open the result automatically when done
spacetrack observe STARLINK-1008 --open

# Finer sample step (default 15s) for sharper plots
spacetrack observe STARLINK-1008 --step 5
```

The terminal output also prints a pass summary:
```
Pass 1: rise 09:15:24 -> peak  16.1° (09:17:24) -> set 09:19:39
```
That reads: rises above 10° at 09:15 UTC, peaks at 16.1° elevation at 09:17,
drops back below 10° at 09:19. ~4 minutes of practical visibility for that pass.

## Why this matters for the broader project

1. **Validates the propagation pipeline.** If `observe` correctly predicts a
   pass that we can confirm against a public source like
   [satellitemap.space/sat/44714](https://satellitemap.space/sat/44714) or N2YO,
   the entire chain (TLE → SGP4 → ECI → topocentric) is working.

2. **Foundation for Phase 3 detection.** Conjunction analysis from a *specific
   observer's* perspective ("what's overhead our ground station right now that
   we didn't expect?") is a natural extension. The same topocentric math
   underpins it.

3. **Sets up future ground-station work.** If we ever add RF capture (SDR),
   `observe` output tells us *when* to capture — a satellite must be above
   our horizon for its downlink to reach us.

## Future enhancements

- **Multi-satellite mode** — all Starlink passes over Colorado Springs tonight,
  as an all-sky timeline rather than per-sat.
- **Sun position overlay** — mark whether the sat is sun-lit (the only time
  you can *see* it visually) vs. in Earth's shadow.
- **Doppler shift** — downlink frequency offset due to relative velocity,
  useful for radio-side analysis.
- **Linked ground-track + sky-plot** — hover on one highlights the other.
- **Pass ranking** — sort by peak elevation, duration, or daylight conditions
  so the best passes surface first.
