"""Tests for the SQLite storage layer (uses tmp paths, no network)."""

from __future__ import annotations

from pathlib import Path

from spacetrack.storage import db
from spacetrack.storage.snapshot import write_snapshots
from spacetrack.tle.parser import parse


STARLINK_NAME = "STARLINK-1007"
STARLINK_LINE1 = "1 44713U 19074A   24320.91666667  .00002182  00000-0  14897-3 0  9993"
STARLINK_LINE2 = "2 44713  53.0541 132.6789 0001482  85.6213 274.4928 15.06414000274566"


def test_init_db_creates_tables(tmp_path: Path):
    p = tmp_path / "test.db"
    db.init_db(p)
    with db.session(p) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    names = {r[0] for r in rows}
    assert {"tle_snapshots", "satellites", "anomalies"}.issubset(names)


def test_write_snapshots_inserts_new_rows(tmp_path: Path):
    p = tmp_path / "test.db"
    db.init_db(p)
    tle = parse(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2)

    with db.session(p) as conn:
        new, total = write_snapshots(
            conn, [tle], fetched_at=1_700_000_000, constellation="starlink"
        )

    assert new == 1
    assert total == 1


def test_write_snapshots_is_idempotent(tmp_path: Path):
    p = tmp_path / "test.db"
    db.init_db(p)
    tle = parse(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2)

    with db.session(p) as conn:
        write_snapshots(conn, [tle], fetched_at=1_700_000_000, constellation="starlink")
    with db.session(p) as conn:
        new, total = write_snapshots(
            conn, [tle], fetched_at=1_700_000_001, constellation="starlink"
        )

    assert new == 0
    assert total == 1


def test_satellites_row_populated(tmp_path: Path):
    p = tmp_path / "test.db"
    db.init_db(p)
    tle = parse(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2)

    with db.session(p) as conn:
        write_snapshots(conn, [tle], fetched_at=1_700_000_000, constellation="starlink")
        row = conn.execute(
            "SELECT name, constellation FROM satellites WHERE norad_id = 44713"
        ).fetchone()

    assert row["name"].startswith("STARLINK")
    assert row["constellation"] == "starlink"
