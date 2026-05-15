"""Smoke tests for visualization — figures build without raising."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from spacetrack.propagate.sgp4_engine import propagate, propagate_track
from spacetrack.viz.globe3d import render_globe
from spacetrack.viz.groundtrack import render_ground_track


STARLINK_NAME = "STARLINK-1007"
STARLINK_LINE1 = "1 44713U 19074A   24320.91666667  .00002182  00000-0  14897-3 0  9993"
STARLINK_LINE2 = "2 44713  53.0541 132.6789 0001482  85.6213 274.4928 15.06414000274566"
WHEN = datetime(2024, 11, 16, 0, 0, 0, tzinfo=timezone.utc)


def test_render_globe_builds_with_one_satellite():
    pos = propagate(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2, when=WHEN)
    fig = render_globe([pos])
    # Single Scattergeo trace; the Earth itself is drawn by the geo layout.
    assert len(fig.data) == 1
    assert fig.data[0].type == "scattergeo"


def test_render_globe_rejects_empty_input():
    with pytest.raises(ValueError):
        render_globe([])


def test_render_ground_track_segments_at_antimeridian():
    positions = propagate_track(
        STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2,
        start=WHEN, minutes=100, step_seconds=30.0,
    )
    fig = render_ground_track(positions)
    # Should have multiple line segments + start marker + end marker.
    assert len(fig.data) >= 3


def test_render_ground_track_rejects_empty_input():
    with pytest.raises(ValueError):
        render_ground_track([])
