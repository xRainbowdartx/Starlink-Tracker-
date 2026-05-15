"""Read-only queries for satellites and TLE snapshots."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class LatestTLE:
    norad_id: int
    name: str
    line1: str
    line2: str
    epoch: float       # Julian date
    fetched_at: int    # unix ts


def find_satellite(conn: sqlite3.Connection, query: str) -> int | None:
    """Resolve a user-supplied identifier to a NORAD ID.

    Accepts either a numeric NORAD ID or a (case-insensitive) name.
    Returns None if no match.
    """
    q = query.strip()
    if q.isdigit():
        row = conn.execute(
            "SELECT norad_id FROM satellites WHERE norad_id = ?", (int(q),)
        ).fetchone()
        return row["norad_id"] if row else None

    row = conn.execute(
        "SELECT norad_id FROM satellites WHERE UPPER(name) = UPPER(?)", (q,)
    ).fetchone()
    if row:
        return row["norad_id"]

    # Fall back to a LIKE match if there's exactly one hit.
    rows = conn.execute(
        "SELECT norad_id, name FROM satellites WHERE UPPER(name) LIKE UPPER(?) LIMIT 2",
        (f"%{q}%",),
    ).fetchall()
    if len(rows) == 1:
        return rows[0]["norad_id"]
    return None


def get_latest_tle(conn: sqlite3.Connection, norad_id: int) -> LatestTLE | None:
    row = conn.execute(
        """
        SELECT s.norad_id, s.name, t.line1, t.line2, t.epoch, t.fetched_at
        FROM tle_snapshots t
        JOIN satellites s ON s.norad_id = t.norad_id
        WHERE t.norad_id = ?
        ORDER BY t.epoch DESC
        LIMIT 1
        """,
        (norad_id,),
    ).fetchone()
    if row is None:
        return None
    return LatestTLE(
        norad_id=row["norad_id"],
        name=row["name"],
        line1=row["line1"],
        line2=row["line2"],
        epoch=row["epoch"],
        fetched_at=row["fetched_at"],
    )
