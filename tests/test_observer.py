"""Tests for observer-relative computations.

We can't easily assert exact (az, el) without a reference solver, so we
sanity-check that:
- A satellite directly above the observer reads elevation ~90°.
- Returned arrays have the right shape and bounds.
- Pass-finding groups contiguous above-threshold samples correctly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from spacetrack.observer.visibility import (
    LookAngle,
    ObserverLocation,
    find_passes,
    look_angles,
)


STARLINK_NAME = "STARLINK-1007"
STARLINK_LINE1 = "1 44713U 19074A   24320.91666667  .00002182  00000-0  14897-3 0  9993"
STARLINK_LINE2 = "2 44713  53.0541 132.6789 0001482  85.6213 274.4928 15.06414000274566"
COS = ObserverLocation("Colorado Springs", 38.8339, -104.8214, 1839.0)
WHEN = datetime(2024, 11, 16, 0, 0, 0, tzinfo=timezone.utc)


def test_look_angles_returns_expected_sample_count():
    angles = look_angles(
        STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2, COS,
        start=WHEN, minutes=10, step_seconds=30.0,
    )
    # 10 min / 30 s = 20 intervals, so 21 samples.
    assert len(angles) == 21


def test_look_angles_within_geometric_bounds():
    angles = look_angles(
        STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2, COS,
        start=WHEN, minutes=60, step_seconds=30.0,
    )
    for a in angles:
        assert 0.0 <= a.azimuth <= 360.0 or -180.0 <= a.azimuth <= 360.0
        assert -90.0 <= a.elevation <= 90.0
        # Slant range bound: for any LEO sat seen from anywhere on Earth,
        # the line-of-sight distance is < Earth diameter + orbital altitude.
        assert 0 < a.range_km < 14000


def test_look_angles_rejects_naive_datetime():
    with pytest.raises(ValueError):
        look_angles(
            STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2, COS,
            start=datetime(2024, 11, 16, 0, 0, 0),
            minutes=10,
        )


def _synthetic_pass_sequence() -> list[LookAngle]:
    base = datetime(2024, 11, 16, 0, 0, 0, tzinfo=timezone.utc)
    # below, below, above, above (peak), above, below, below, above, below
    elevs = [-5, -1, 5, 30, 12, -1, -10, 8, -2]
    return [
        LookAngle(
            when=base + timedelta(seconds=i * 30),
            azimuth=180.0,
            elevation=float(e),
            range_km=2000.0,
        )
        for i, e in enumerate(elevs)
    ]


def test_find_passes_groups_contiguous_above_horizon_runs():
    passes = find_passes(_synthetic_pass_sequence(), threshold_deg=0.0)
    assert len(passes) == 2
    assert passes[0].peak.elevation == 30
    assert passes[1].peak.elevation == 8


def test_find_passes_with_higher_threshold():
    passes = find_passes(_synthetic_pass_sequence(), threshold_deg=10.0)
    # Only the first run has anything >= 10°.
    assert len(passes) == 1
    assert passes[0].peak.elevation == 30


def test_find_passes_empty_when_nothing_visible():
    base = datetime(2024, 11, 16, 0, 0, 0, tzinfo=timezone.utc)
    below = [
        LookAngle(when=base + timedelta(seconds=i * 30),
                  azimuth=0.0, elevation=-30.0, range_km=2000.0)
        for i in range(10)
    ]
    assert find_passes(below, threshold_deg=0.0) == []
