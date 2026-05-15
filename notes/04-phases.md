# Phased rollout

Each phase is shippable on its own — you can stop at any phase and still have
a demoable artifact. But the architecture (data schema, module boundaries) is
designed for all four upfront so we don't refactor later.

## Phase 1 — "Where is everything?" (foundation)

**Goal:** answer "where is Starlink-1234 right now?" and "what passes over my
location tonight?"

**Deliverables:**
- `spacetrack.tle.fetcher` pulling CelesTrak Starlink group on demand.
- `spacetrack.tle.parser` validating and normalizing TLE lines.
- `spacetrack.propagate.sgp4_engine` for position/velocity at arbitrary time.
- `spacetrack.storage` with full SQLite schema (Phase 3 needs this *now*).
- `spacetrack.observer.passes` for ground-station pass prediction.
- `spacetrack update`, `spacetrack where`, `spacetrack passes` CLI commands.

**Estimated effort:** weekend.

## Phase 2 — "Show me" (visualization)

**Goal:** turn the CLI output into pictures that make the project portfolio-friendly.

**Deliverables:**
- `spacetrack.viz.globe3d` — plotly 3D Earth with all Starlink positions.
- `spacetrack.viz.groundtrack` — ground track for a specific satellite.
- CLI flag `--render html` on relevant commands to spit out a self-contained HTML.

**Estimated effort:** a few evenings. No new data, just rendering.

## Phase 3 — "What's weird?" (the differentiator)

**Goal:** the cybersecurity layer. This is the hard part and the part that
makes the project unique.

**Deliverables:**
- `spacetrack.storage.snapshot` — periodic TLE history writer (cron / scheduler).
- `spacetrack.anomaly.conjunction` — close-approach detector.
- `spacetrack.anomaly.maneuver` — orbital element diff + ballistic-drag residual.
- `spacetrack.anomaly.inspector` — persistent proximity scoring.
- `spacetrack.anomaly.decay` — perigee descent rate detector.
- `spacetrack scan` and `spacetrack alerts` CLI commands.
- A writeup comparing detected maneuvers to SpaceX's published FCC list (validation).

**Estimated effort:** the bulk of the project. Several weeks if done well.

## Phase 4 — Polish

**Goal:** make it presentable and shareable.

**Deliverables:**
- Streamlit dashboard (`dashboard/app.py`) reading from the same SQLite DB.
- Webhook notifier (Discord or email) for new critical anomalies.
- Unit tests with synthetic TLEs (canned data, no network).
- README with screenshots of real detected events.
- Optional: deploy to a cheap VPS so the snapshot writer runs 24/7 and the
  alert history accumulates over time.

**Estimated effort:** a week or two depending on how polished you want it.

## Stretch goals (post-Phase 4)

- C/C++ vectorized SGP4 with Python bindings (resume flex).
- Expand from Starlink-only to OneWeb / Iridium / GPS — schema already supports it.
- ML maneuver classifier trained on SpaceX-labeled ground truth.
- Conjunction prediction confidence intervals using TLE uncertainty estimates.
