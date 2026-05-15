# Anomaly detection — the security angle

This is the part that turns the project from "satellite tracker" into something
that bridges cybersecurity and space. Each detector below is self-contained,
runs against the SQLite TLE history, and writes findings to the `anomalies` table.

## 1. Conjunction detector (`conjunction.py`)

**What it finds:** two objects whose orbits will pass within a threshold
distance (e.g. 5 km) of each other within a time horizon (e.g. 72 hours).

**Approach:**
1. Pull current TLEs for all Starlink + a "neighborhood" of non-Starlink LEO sats.
2. Propagate every object forward in 60-second steps for 72 hours (vectorized SGP4).
3. For each timestep, find pairs where 3D distance < threshold.
4. Refine with bisection to find the time of closest approach (TCA) and miss distance.

**Performance note:** naive O(n²) pairs is too slow at 6500 sats. Bin objects by
inclination + altitude shell first; only check pairs within the same/adjacent bins.

**Validation:** SpaceX's FCC reports list real conjunctions Starlink avoided.

## 2. Maneuver detector (`maneuver.py`)

**What it finds:** a satellite whose orbital elements changed more than ballistic
drag and J2 perturbations can explain — i.e., it fired a thruster.

**Approach:**
1. For each satellite, walk through TLE snapshots in time order.
2. Compare consecutive TLEs: did `mean_motion`, `eccentricity`, or `arg_perigee`
   shift more than expected from natural decay over the elapsed time?
3. Threshold-based: if the residual after subtracting modeled drag exceeds N
   sigma, flag as a maneuver.

**Why this is interesting:** every maneuver costs propellant, so unannounced ones
are rare and meaningful. SpaceX publishes some maneuvers; ours should match.
Anything we detect that *isn't* in SpaceX's list is either a missed publication
or a detector false positive — both worth investigating.

## 3. Inspector / proximity detector (`inspector.py`)

**What it finds:** a non-Starlink satellite whose orbit is consistently close to
a Starlink satellite over many days, suggesting deliberate co-orbiting rather
than a random close approach.

**Approach:**
1. For each Starlink, find all other objects within (e.g.) 50 km over a 7-day
   window.
2. Score by: average distance, time spent within threshold, RAAN/inclination
   match, mean-motion match.
3. Flag persistent followers, not one-off close passes.

**Real-world precedent:** Cosmos 2542/2543 trailing USA-245 (NRO satellite) in
2020 was the textbook example. Same pattern would show up in Starlink data if
anyone tried it.

## 4. Decay / re-entry detector (`decay.py`)

**What it finds:** satellites whose perigee is dropping fast — about to re-enter,
or being deliberately deorbited.

**Approach:**
1. For each satellite, compute `d(perigee)/dt` over the last N TLEs.
2. Flag if the rate exceeds a threshold tuned to natural drag at Starlink's altitude.
3. Cross-reference SpaceX's published deorbit list to label "expected" vs.
   "unexpected" decays.

**Bonus:** an ASAT test would show up as a sudden cluster of new NORAD IDs
(debris) all decaying together — building on this detector lets us flag that
pattern too.

## Severity levels

- **info** — natural-looking event (predicted decay, routine close approach)
- **warning** — unannounced maneuver, persistent inspector pattern
- **critical** — sub-1km conjunction, unexpected debris cluster, Starlink-on-Starlink
  conjunction

## Output

Every detection writes a row to the `anomalies` table with a JSON `details`
payload (the specific orbital elements involved, distance, time, etc.) so the
CLI and eventual dashboard can render it without re-running detection.
