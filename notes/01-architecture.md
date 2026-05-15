# Architecture

## Module layout

```
Space Project/
├── spacetrack/                  # core library (importable)
│   ├── __init__.py
│   ├── tle/                     # Phase 1 — TLE fetching & parsing
│   │   ├── fetcher.py           #   pulls Starlink group from CelesTrak
│   │   ├── parser.py            #   wraps sgp4 lib, validates checksum
│   │   └── catalog.py           #   in-memory satellite catalog
│   ├── propagate/               # Phase 1 — orbit math
│   │   ├── sgp4_engine.py       #   position/velocity at time T (vectorized)
│   │   └── geometry.py          #   ECI ↔ ECEF ↔ geodetic conversions
│   ├── observer/                # Phase 1 — "what's overhead from lat/lon?"
│   │   ├── passes.py            #   pass prediction
│   │   └── visibility.py        #   elevation, azimuth, range
│   ├── viz/                     # Phase 2 — plotting (kept out of core)
│   │   ├── globe3d.py           #   plotly 3D globe
│   │   └── groundtrack.py       #   2D ground tracks
│   ├── storage/                 # Phase 3 — TLE history (load-bearing)
│   │   ├── db.py                #   SQLite schema + queries
│   │   └── snapshot.py          #   periodic TLE snapshot writer
│   ├── anomaly/                 # Phase 3 — the security/SDA layer
│   │   ├── conjunction.py       #   close-approach detector
│   │   ├── maneuver.py          #   diff TLEs, flag burns
│   │   ├── inspector.py         #   one sat closing on another
│   │   └── decay.py             #   re-entry / orbit decay
│   └── cli.py                   # main CLI entrypoint (click)
├── dashboard/                   # Phase 4 — Streamlit, optional
├── tests/
├── data/                        # local SQLite + cached TLEs (gitignored)
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Tech stack

| Concern | Choice | Why |
|---|---|---|
| Orbit propagation | `sgp4` (Python) | Industry-standard SGP4/SDP4. Same algorithm DoD uses. |
| Astrodynamics helpers | `skyfield` | High-level lookups (lat/lon, passes, sun position) |
| TLE source | CelesTrak HTTP feeds | Free, no API key, updated several times daily |
| Storage | SQLite | Zero-config, perfect for time-series TLE snapshots |
| CLI framework | `click` | Cleaner than argparse for nested commands |
| Visualization (Ph2) | `plotly` | 3D globe in HTML, no JS code needed |
| Dashboard (Ph4) | Streamlit | Fastest path to web UI; swap to Flask+React later if desired |
| Performance hot loops | C/C++ via `ctypes` or Cython | ONLY if profiling shows propagation is the bottleneck |

## Data schema

This is the load-bearing piece — Phase 3 anomaly detection depends on it,
so it gets designed up front.

```sql
-- Every TLE we've ever pulled, with timestamp
CREATE TABLE tle_snapshots (
    norad_id     INTEGER NOT NULL,
    epoch        REAL NOT NULL,        -- TLE epoch (Julian date)
    fetched_at   INTEGER NOT NULL,     -- unix ts of when WE fetched it
    line1        TEXT NOT NULL,
    line2        TEXT NOT NULL,
    -- denormalized orbital elements for fast queries:
    inclination     REAL,
    raan            REAL,
    eccentricity    REAL,
    arg_perigee     REAL,
    mean_anomaly    REAL,
    mean_motion     REAL,
    PRIMARY KEY (norad_id, epoch)
);
CREATE INDEX idx_tle_norad_epoch ON tle_snapshots(norad_id, epoch);

-- Satellite metadata (mostly stable)
CREATE TABLE satellites (
    norad_id    INTEGER PRIMARY KEY,
    name        TEXT,
    country     TEXT,
    launch_date TEXT,
    object_type TEXT,                  -- payload, debris, rocket body
    constellation TEXT                 -- 'starlink' for our targets
);

-- Detected anomalies (Phase 3 output)
CREATE TABLE anomalies (
    id           INTEGER PRIMARY KEY,
    detected_at  INTEGER NOT NULL,
    type         TEXT NOT NULL,        -- conjunction|maneuver|inspector|decay
    severity     TEXT NOT NULL,        -- info|warning|critical
    primary_id   INTEGER,              -- norad_id involved
    secondary_id INTEGER,              -- second norad_id (for conjunctions/inspector)
    details      TEXT                  -- JSON payload with specifics
);
```

## CLI surface (planned)

```
spacetrack update                          # pull latest Starlink TLEs into DB
spacetrack where STARLINK-1234             # current position
spacetrack where 44713 --at "2026-05-10T20:00Z"
spacetrack passes --lat 40.7 --lon -74.0 --hours 48
spacetrack list                            # all tracked Starlink sats
spacetrack scan conjunctions --threshold-km 5
spacetrack scan maneuvers --since 7d
spacetrack scan inspectors --proximity-km 50
spacetrack alerts                          # show recent anomalies
```

## Phase dependencies (why we plan upfront)

- Phase 3's `maneuver.py` **needs** the `tle_snapshots` table populated
  continuously, so the snapshot writer must exist from Phase 1.
- Phase 3's `conjunction.py` **needs** efficient batch propagation for thousands
  of objects across time windows — that shapes how `sgp4_engine.py` is written
  (vectorized via `sgp4`'s array API, not one-call-per-sat).
- Phase 4's dashboard reads from the same SQLite DB the CLI writes to, so no
  separate API layer is needed yet.
