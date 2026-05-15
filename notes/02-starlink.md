# Why Starlink

Picked over "all satellites" on 2026-05-09. The reasoning:

## Scope is tight but meaningful
- ~6,500 active satellites — enough that anomaly detection is non-trivial,
  not so many that the dataset is intractable on a laptop.
- One CelesTrak feed (`?GROUP=starlink`) instead of the full ~10k catalog.
- Homogeneous fleet — "what does normal look like?" is well-defined.

## SpaceX publishes ground truth
- **Avoidance maneuvers:** SpaceX submits semi-annual reports to the FCC listing
  conjunction-avoidance maneuvers. We can validate our maneuver detector against
  this published data.
- **Deorbits:** SpaceX announces planned deorbits; our decay detector should
  catch them.
- This makes the project **falsifiable**, which most "look at sats!" projects
  aren't. That's a real differentiator on a portfolio.

## The security narrative is real and current
- **Russia/Ukraine:** Starlink terminals jammed on the front lines; SpaceX
  geofencing decisions made operational news. Surface-level RF stuff is out of
  scope here, but the orbital-side angle (collision risk, deliberate proximity
  ops) is in scope.
- **ASAT threat:** A Chinese or Russian anti-satellite test in LEO would
  primarily threaten LEO megaconstellations — Starlink is the obvious target.
  Our detector for "sudden cluster of new debris in a Starlink shell" is exactly
  the kind of analysis SDA orgs run.
- **"Inspector" satellites:** Foreign government satellites that linger near
  Starlink operationals are a known concern. Our proximity detector targets this
  pattern directly.

## Easier to explain in interviews
"I built a tool that watches Starlink for collisions and unannounced maneuvers"
is a one-sentence pitch that lands with both technical and non-technical
listeners. "I built a generic TLE viewer" is not.

## What we lose
- We won't catch interesting non-Starlink events (Cosmos breakups, NRO sats,
  etc.) without flipping a config switch.
  - **Mitigation:** the storage layer is keyed on NORAD ID, not constellation —
    pulling additional CelesTrak groups later is a one-line change. We'll just
    not detect/alert on them in v1.
