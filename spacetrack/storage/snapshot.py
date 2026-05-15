"""Persist parsed TLEs into the snapshot history table.

Idempotent: the (norad_id, epoch) primary key means re-running an update
without a fresh CelesTrak refresh just no-ops on the conflicting rows.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable

from spacetrack.tle.parser import ParsedTLE

log = logging.getLogger(__name__)


def upsert_satellite(conn: sqlite3.Connection, tle: ParsedTLE, constellation: str) -> None:
    conn.execute(
        """
        INSERT INTO satellites (norad_id, name, constellation)
        VALUES (?, ?, ?)
        ON CONFLICT(norad_id) DO UPDATE SET
            name = excluded.name,
            constellation = excluded.constellation
        """,
        (tle.norad_id, tle.name, constellation),
    )


def insert_snapshot(
    conn: sqlite3.Connection, tle: ParsedTLE, fetched_at: int
) -> bool:
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO tle_snapshots (
            norad_id, epoch, fetched_at, line1, line2,
            inclination, raan, eccentricity,
            arg_perigee, mean_anomaly, mean_motion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tle.norad_id,
            tle.epoch_jd,
            fetched_at,
            tle.line1,
            tle.line2,
            tle.inclination,
            tle.raan,
            tle.eccentricity,
            tle.arg_perigee,
            tle.mean_anomaly,
            tle.mean_motion,
        ),
    )
    return cur.rowcount > 0


def write_snapshots(
    conn: sqlite3.Connection,
    tles: Iterable[ParsedTLE],
    *,
    fetched_at: int,
    constellation: str,
) -> tuple[int, int]:
    new_count = 0
    total = 0
    for tle in tles:
        upsert_satellite(conn, tle, constellation)
        if insert_snapshot(conn, tle, fetched_at):
            new_count += 1
        total += 1

    log.info("Persisted %d new TLEs (out of %d fetched)", new_count, total)
    return new_count, total
