"""Sanity checks on the propagation engine using a synthetic Starlink TLE."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from spacetrack.propagate.sgp4_engine import propagate


STARLINK_NAME = "STARLINK-1007"
STARLINK_LINE1 = "1 44713U 19074A   24320.91666667  .00002182  00000-0  14897-3 0  9993"
STARLINK_LINE2 = "2 44713  53.0541 132.6789 0001482  85.6213 274.4928 15.06414000274566"


def test_propagate_returns_sensible_geographic_position():
    when = datetime(2024, 11, 16, 0, 0, 0, tzinfo=timezone.utc)
    pos = propagate(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2, when=when)

    assert pos.norad_id == 44713
    assert -90 <= pos.latitude <= 90
    assert -180 <= pos.longitude <= 180
    # Starlink shell ~550 km. Allow a generous range for any V1/V2 mix.
    assert 400 < pos.altitude_km < 700


def test_propagate_speed_is_orbital_velocity_range():
    when = datetime(2024, 11, 16, 0, 0, 0, tzinfo=timezone.utc)
    pos = propagate(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2, when=when)
    # LEO orbital velocity is ~7.5 km/s; allow some spread.
    assert 7.0 < pos.speed_km_s < 8.0


def test_propagate_rejects_naive_datetime():
    naive = datetime(2024, 11, 16, 0, 0, 0)  # no tzinfo
    with pytest.raises(ValueError):
        propagate(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2, when=naive)


def test_propagate_position_changes_over_time():
    t1 = datetime(2024, 11, 16, 0, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 11, 16, 0, 5, 0, tzinfo=timezone.utc)  # +5 minutes
    p1 = propagate(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2, when=t1)
    p2 = propagate(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2, when=t2)
    # In 5 minutes a Starlink moves a long way; lat or lon must change appreciably.
    assert abs(p1.latitude - p2.latitude) + abs(p1.longitude - p2.longitude) > 1.0
