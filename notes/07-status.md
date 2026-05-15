# Project status log

Running history of what's done, what's next.

## 2026-05-09 — Phases 1 & 2 complete

### Phase 1 — foundation (shipped)

- TLE fetching from CelesTrak (`spacetrack/tle/fetcher.py`)
- TLE parsing with checksum validation (`spacetrack/tle/parser.py`)
- Full SQLite schema: `tle_snapshots`, `satellites`, `anomalies` (`spacetrack/storage/db.py`)
- Idempotent snapshot writer (`spacetrack/storage/snapshot.py`)
- Read-only DB queries (`spacetrack/storage/queries.py`)
- SGP4 propagation via Skyfield (`spacetrack/propagate/sgp4_engine.py`)
- CLI commands: `update`, `stats`, `where`

### Phase 2 — visualization (shipped)

- 3D globe of full constellation (`spacetrack/viz/globe3d.py`)
- 2D ground tracks for individual satellites (`spacetrack/viz/groundtrack.py`)
- Observer view: polar sky plot + elevation timeline (`spacetrack/viz/skyplot.py`)
- Observer-relative geometry (`spacetrack/observer/visibility.py`)
- Batch + multi-step propagation helpers
- CLI commands: `globe`, `track`, `observe`
- Default observer = Colorado Springs, CO (user's location, also US military space hub)
- All renders output self-contained HTML (Plotly + CDN), open in any browser

### Verified working

- `spacetrack update` pulls 10,315 live Starlink TLEs into SQLite (~4 sec)
- `spacetrack where STARLINK-1008` returns lat/lon/alt/speed
- `spacetrack where 44714 --at 2026-05-10T20:00:00Z` works for arbitrary times
- `spacetrack globe -o globe.html` renders all 10,315 sats on a 3D Earth
- `spacetrack track STARLINK-1008` renders 2-orbit ground track
- 26 tests pass (parser, storage, queries, propagation, viz smoke tests)

### Generated artifacts (gitignored)

- `data/spacetrack.db` — SQLite with current TLE snapshot
- `globe.html` — 2.1 MB, full constellation
- `globe-sample.html` — 100-sat subset
- `track-STARLINK-1008.html` — single-sat ground track

### Phase 2.5 — live modes (shipped 2026-05-10)

Three independent ways to keep the project running continuously. See
[notes/09-live.md](09-live.md) for full details.

- **Scheduled background updates** — Windows Task Scheduler script at
  `scripts/register_scheduled_update.ps1` registers a 6-hourly task that runs
  `spacetrack update` automatically. Not yet installed (user-installable).
- **Terminal live stream** — `spacetrack live STARLINK-1008` prints one
  satellite's position + observer look angles every ~2 seconds. Reuses the
  most recent stored TLE so no network calls per tick.
- **Web dashboard** — `spacetrack dashboard` launches a Streamlit app at
  http://localhost:8501 with three tabs: 3D globe, observer/sky plot, ground
  track. Sidebar exposes observer location and satellite selector.
  Auto-refreshes every 1 hour via HTML meta-refresh (preserves interactive
  state); manual rerun with **R** in the browser, 60-second data cache.

New code added:
- `dashboard/app.py` — Streamlit application
- `spacetrack/live.py` — `live_sample()` helper, testable in isolation
- `spacetrack/cli.py` — `live` and `dashboard` commands
- `scripts/register_scheduled_update.ps1` — Windows Task Scheduler installer

### Live demo entry points

| What | URL / command |
|---|---|
| Web dashboard | http://localhost:8501 (after `spacetrack dashboard`) |
| Terminal stream | `spacetrack live STARLINK-1008` |
| One-off pass scan | `spacetrack observe STARLINK-1008 --hours 24 --open` |

### Pause point — 2026-05-13

**Session summary (since 05-11):**

- Continent experiment on the 3D globe — multiple attempts (rasterised mask, then Mesh3d filled polygons at 110m then 50m), all rolled back per user feedback ("looks like shit")
- **Constellation tab redesigned** with `Scattergeo` + orthographic projection, styled to match the ground-track palette (continents, lakes, ocean — no country borders/coastlines for perf)
- **Performance pass** on the dashboard:
  - Propagation now cached per (limit, UTC minute) via `@st.cache_data`
  - Default sat slider dropped from 2,000 → 500 (Scattergeo SVG sweet spot)
  - Smaller marker size (2 px)
  - Streamlit `use_container_width=True` → `width="stretch"` everywhere (deprecation fix)
- **Lakes enabled** on both the globe and ground-track views (Great Lakes, Caspian, Baikal, etc.)
- Em dash in chart title replaced with a comma

**What's still blocked:** still needs `gh auth login` from the user to push to GitHub and deploy to Streamlit Cloud.

**Tradeoff to remember:** Scattergeo gives us native Earth styling but is SVG-rendered, not WebGL — rotation slows above ~1,500 markers. If the user ever finds rotation unacceptable, the fallback is reverting `render_globe()` to `Scatter3d` (WebGL, smooth at 10k+, no continents).

### Pause point — 2026-05-11

**Where we stopped:** mid-way through public deployment to Streamlit Community Cloud.

**What's done since last entry:**
- Dashboard refresh interval changed from 30s → 1 hour (preserves interactive state); 60s data cache for manual reruns
- "Last update" metric now shows relative time ("3m ago") with full UTC + local timestamp on a caption line below
- All emojis stripped from dashboard UI; tab labels use middle dots (·) instead
- `.gitignore` updated to exclude generated HTML and `logs/`
- `requirements.txt` now includes `plotly` and `streamlit` so Streamlit Cloud installs them
- `dashboard/app.py` has `bootstrap_catalog_if_empty()` — auto-fetches TLEs on first run if DB is empty
- `.streamlit/config.toml` baked in (dark theme matching the local renders)
- GitHub CLI (`gh`) installed via winget; version 2.92.0
- Memory `project_decisions.md` updated: "git deferred" decision reversed

**What's blocked:** waiting on user to run `gh auth login` in PowerShell. After that, the next steps are:
1. `git init` + first commit (in project root)
2. `gh repo create starlink-watch --public --source=. --push`
3. Visit share.streamlit.io, point at the new repo + `dashboard/app.py`
4. Get a public live demo URL
5. Add the URL to README.md as a "Live demo" link

**Dashboard state:** Streamlit was running in a background process at http://localhost:8501 when we paused. If the VS Code session terminates, that process dies — restart with `spacetrack dashboard`.

**Test count at pause:** 32/32 passing. No code changes are in flight; the codebase is clean and committable as-is the moment `gh auth login` finishes.

### Next up — Phase 3 (anomaly detection)

The cybersecurity layer. Requires multiple TLE snapshots over time to be useful
(maneuver detection diffs orbital elements between successive TLE epochs).

**Recommended approach:**
1. Run `spacetrack update` daily for ~1 week to build TLE history.
2. Implement detectors in this order:
   - `decay.py` first (simplest — works on a single TLE epoch's mean motion)
   - `conjunction.py` next (works on current TLEs + propagation)
   - `maneuver.py` (needs >=2 epochs per sat)
   - `inspector.py` (needs >=7 days of history per sat-pair)
3. Add `spacetrack scan` and `spacetrack alerts` CLI commands.

### Optional Phase 1 polish (skipped)

- `passes.py` — predict satellite passes over a ground station (lat/lon based).
  Not strictly needed for the Phase 3 anomaly story; defer unless useful for the
  README's "what can it do" demo.
