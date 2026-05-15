"""Observer-relative geometry: turn satellite positions into "where to look."

Given an observer location (lat/lon/altitude) and a satellite TLE, sample the
azimuth, elevation, and range to the satellite at each step over a time
window. Then group the results into discrete *passes* — contiguous spans of
time when the satellite is above a chosen elevation threshold.

All the trigonometry is delegated to Skyfield's topocentric frame, which
handles the TEME → ECI → ECEF → ENU rotations using IAU 2000A
precession-nutation. We just feed it a TLE, a site, and an array of times.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from skyfield.api import EarthSatellite, wgs84

from spacetrack.propagate.sgp4_engine import _timescale


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ObserverLocation:
    """A point on Earth from which we're watching the sky."""

    name: str
    latitude: float      # degrees north of the equator (negative = south)
    longitude: float     # degrees east of Greenwich (negative = west)
    altitude_m: float    # height above the WGS-84 ellipsoid, in meters


@dataclass(frozen=True)
class LookAngle:
    """Where to point at a given moment to see the satellite."""

    when: datetime       # always timezone-aware (UTC)
    azimuth: float       # compass bearing: 0°=N, 90°=E, 180°=S, 270°=W
    elevation: float     # angle above the horizon: 0°=horizon, 90°=overhead
    range_km: float      # straight-line distance to the satellite


@dataclass(frozen=True)
class Pass:
    """A continuous span of time when the satellite is visible.

    A pass runs from the moment the satellite rises above the elevation
    threshold (``rise``) to the moment it falls back below it (``fall``).
    ``peak`` is the highest-elevation sample inside that span.
    """

    rise: LookAngle
    peak: LookAngle
    fall: LookAngle
    threshold_deg: float


# ---------------------------------------------------------------------------
# Default observer
# ---------------------------------------------------------------------------

#: Default observation site. Colorado Springs sits at the operational heart
#: of US military space — NORAD (Cheyenne Mountain), US Space Force HQ at
#: Peterson SFB, Schriever SFB (GPS operations), and USSPACECOM.
COLORADO_SPRINGS = ObserverLocation(
    name="Colorado Springs, CO",
    latitude=38.8339,
    longitude=-104.8214,
    altitude_m=1839.0,
)


def default_observer() -> ObserverLocation:
    """Return the project's default observer (Colorado Springs)."""
    return COLORADO_SPRINGS


# ---------------------------------------------------------------------------
# Look-angle computation
# ---------------------------------------------------------------------------

def look_angles(
    sat_name: str,
    line1: str,
    line2: str,
    observer: ObserverLocation,
    *,
    start: datetime,
    minutes: float = 360.0,
    step_seconds: float = 15.0,
) -> list[LookAngle]:
    """Sample (azimuth, elevation, range) over a time window.

    Args:
        sat_name:     Satellite name; used only for display/labels.
        line1:        First line of the satellite's TLE.
        line2:        Second line of the satellite's TLE.
        observer:     Where on Earth we're standing.
        start:        Beginning of the window. Must be timezone-aware (UTC).
        minutes:      Length of the window. Default 6 hours.
        step_seconds: Sample interval. Smaller = sharper plots, more work.

    Returns:
        One ``LookAngle`` per sample, in chronological order.
    """
    if start.tzinfo is None:
        raise ValueError("`start` must be timezone-aware (UTC)")

    # Build the propagation context: a timescale, the satellite, and the site.
    timescale = _timescale()
    satellite = EarthSatellite(line1, line2, sat_name, timescale)
    site = wgs84.latlon(observer.latitude, observer.longitude, observer.altitude_m)

    # Sample times evenly across the window.
    sample_count = max(2, int(minutes * 60.0 / step_seconds) + 1)
    start_utc = start.astimezone(timezone.utc)
    sample_times = [
        start_utc + timedelta(seconds=i * step_seconds)
        for i in range(sample_count)
    ]
    t = timescale.from_datetimes(sample_times)

    # "satellite − site" gives the observer-to-satellite vector at each time;
    # `.altaz()` converts that into (elevation, azimuth, range).
    topocentric = (satellite - site).at(t)
    elevation, azimuth, distance = topocentric.altaz()

    # Skyfield's @reify properties return float | ndarray, but with an array
    # of times we always get arrays. cast(Any, ...) silences the type checker
    # without any runtime cost.
    elevations_deg = cast(Any, elevation.degrees)
    azimuths_deg = cast(Any, azimuth.degrees)
    ranges_km = cast(Any, distance.km)

    return [
        LookAngle(
            when=sample_times[i],
            azimuth=float(azimuths_deg[i]),
            elevation=float(elevations_deg[i]),
            range_km=float(ranges_km[i]),
        )
        for i in range(sample_count)
    ]


# ---------------------------------------------------------------------------
# Pass extraction
# ---------------------------------------------------------------------------

def find_passes(
    angles: Iterable[LookAngle],
    threshold_deg: float = 0.0,
) -> list[Pass]:
    """Group consecutive look-angle samples into passes above a threshold.

    A pass is a maximal contiguous run of samples whose elevation is at or
    above ``threshold_deg``. Common thresholds:

    * ``0°``  — geometrically above the horizon
    * ``10°`` — above typical obstructions (practical visibility)

    Args:
        angles:        Samples to scan, typically the output of ``look_angles``.
        threshold_deg: Minimum elevation that counts as "visible".

    Returns:
        One ``Pass`` per visible run, in chronological order. The peak of
        each pass is the highest-elevation sample within it.
    """
    passes: list[Pass] = []
    current_run: list[LookAngle] = []

    def close_run() -> None:
        if not current_run:
            return
        peak = max(current_run, key=lambda sample: sample.elevation)
        passes.append(Pass(
            rise=current_run[0],
            peak=peak,
            fall=current_run[-1],
            threshold_deg=threshold_deg,
        ))

    for sample in angles:
        if sample.elevation >= threshold_deg:
            current_run.append(sample)
        else:
            close_run()
            current_run = []

    close_run()
    return passes
