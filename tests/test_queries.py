"""Tests for the read-only DB query helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from spacetrack.storage import db
from spacetrack.storage.queries import find_satellite, get_latest_tle
from spacetrack.storage.snapshot import write_snapshots
from spacetrack.tle.parser import parse


STARLINK_NAME = "STARLINK-1007"
STARLINK_LINE1 = "1 44713U 19074A   24320.91666667  .00002182  00000-0  14897-3 0  9993"
STARLINK_LINE2 = "2 44713  53.0541 132.6789 0001482  85.6213 274.4928 15.06414000274566"


@pytest.fixture
def populated_db(tmp_path: Path) -> Path:
    p = tmp_path / "test.db"
    db.init_db(p)
    tle = parse(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2)
    with db.session(p) as conn:
        write_snapshots(conn, [tle], fetched_at=1_700_000_000, constellation="starlink")
    return p


def test_find_satellite_by_norad_id(populated_db: Path):
    with db.session(populated_db) as conn:
        assert find_satellite(conn, "44713") == 44713


def test_find_satellite_by_exact_name(populated_db: Path):
    with db.session(populated_db) as conn:
        assert find_satellite(conn, "STARLINK-1007") == 44713


def test_find_satellite_is_case_insensitive(populated_db: Path):
    with db.session(populated_db) as conn:
        assert find_satellite(conn, "starlink-1007") == 44713


def test_find_satellite_returns_none_for_unknown(populated_db: Path):
    with db.session(populated_db) as conn:
        assert find_satellite(conn, "DOES-NOT-EXIST") is None


def test_get_latest_tle_returns_stored_lines(populated_db: Path):
    with db.session(populated_db) as conn:
        tle = get_latest_tle(conn, 44713)
    assert tle is not None
    assert tle.line1 == STARLINK_LINE1
    assert tle.line2 == STARLINK_LINE2
    assert tle.name == STARLINK_NAME
