# References

## Data sources

- **CelesTrak Starlink TLE feed:** `https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle`
  - Updated multiple times per day, no API key, no rate limit issues for our scale.
- **CelesTrak SATCAT:** `https://celestrak.org/satcat/search.php`
  - Use to populate the `satellites` metadata table.
- **Space-Track.org:** `https://www.space-track.org/`
  - Higher-quality TLEs and conjunction data messages (CDMs), but requires
    free account + agreeing to a data-use license. Good Phase 3.5 upgrade.
- **SpaceX FCC filings:** semi-annual reports listing Starlink avoidance maneuvers.
  - Used as ground truth for the maneuver detector. Find via FCC EDGAR or
    SpaceX's own publications.

## Python libraries

- `sgp4` — official SGP4/SDP4 implementation. https://pypi.org/project/sgp4/
- `skyfield` — astrodynamics & positional astronomy. https://rhodesmill.org/skyfield/
- `click` — CLI framework. https://click.palletsprojects.com/
- `plotly` — 3D visualization. https://plotly.com/python/
- `streamlit` — Phase 4 dashboard. https://streamlit.io/

## Reading

- *Fundamentals of Astrodynamics and Applications* — Vallado. The bible for orbit math.
- *Satellite Orbits* — Montenbruck & Gill. Algorithms in detail.
- CCSDS Conjunction Data Message standard (502.0-B-2) — defines what a "real"
  conjunction warning looks like, useful to mirror our `anomalies.details` JSON
  schema after.
- Hack-A-Sat writeups — for general space-cybersecurity flavor.

## Real events to model / validate against

- **Kosmos 1408 ASAT test (Nov 2021)** — Russian destruction of own satellite
  created a debris cloud that threatened the ISS. Pattern: sudden cluster of
  new NORAD IDs in a tight altitude shell.
- **Cosmos 2542 / 2543 (2020)** — Russian "inspector" sats trailed USA-245.
  Pattern: persistent low-relative-distance + matching inclination / RAAN drift.
- **Iridium 33 / Cosmos 2251 collision (Feb 2009)** — first major accidental
  satellite collision. Demonstrates why conjunction prediction matters.
- **Starlink-1095 close approach with OneWeb-0178 (March 2021)** — the first
  publicly-reported megaconstellation conjunction. Good test case.
