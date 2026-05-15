"""Terminal "live" view of a single satellite.

Polls SGP4 every N seconds and prints the satellite's current geographic
position plus its look angles from a given observer. The same TLE is reused
across iterations — only the propagation time advances, so the loop is fast
(milliseconds per tick).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from spacetrack.observer.visibility import LookAngle, ObserverLocation, look_angles
from spacetrack.propagate.sgp4_engine import SatPosition, propagate


@dataclass(frozen=True)
class LiveSample:
    """One tick of the live stream: position + look angle from the observer."""

    position: SatPosition
    look: LookAngle


def live_sample(
    sat_name: str,
    line1: str,
    line2: str,
    observer: ObserverLocation,
    *,
    when: datetime | None = None,
) -> LiveSample:
    """Compute one snapshot: geographic position and observer look angles."""
    if when is None:
        when = datetime.now(timezone.utc)

    position = propagate(sat_name, line1, line2, when=when)
    # look_angles enforces a minimum of 2 samples; we just want the first one.
    look = look_angles(
        sat_name, line1, line2, observer,
        start=when, minutes=0.0, step_seconds=1.0,
    )[0]
    return LiveSample(position=position, look=look)
