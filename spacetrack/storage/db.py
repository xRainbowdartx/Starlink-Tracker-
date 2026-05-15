"""SQLite schema and connection helpers.

The full schema is defined here from day one because the Phase 3 anomaly
detectors (maneuver, conjunction, inspector, decay) all read from the
tle_snapshots history. Designing the schema upfront avoids painful migrations.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DB_PATH = Path("data/spacetrack.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tle_snapshots (
    norad_id      INTEGER NOT NULL,
    epoch         REAL    NOT NULL,
    fetched_at    INTEGER NOT NULL,
    line1         TEXT    NOT NULL,
    line2         TEXT    NOT NULL,
    inclination   REAL,
    raan          REAL,
    eccentricity  REAL,
    arg_perigee   REAL,
    mean_anomaly  REAL,
    mean_motion   REAL,
    PRIMARY KEY (norad_id, epoch)
);

CREATE INDEX IF NOT EXISTS idx_tle_norad_epoch
    ON tle_snapshots(norad_id, epoch);

CREATE INDEX IF NOT EXISTS idx_tle_fetched_at
    ON tle_snapshots(fetched_at);

CREATE TABLE IF NOT EXISTS satellites (
    norad_id      INTEGER PRIMARY KEY,
    name          TEXT,
    country       TEXT,
    launch_date   TEXT,
    object_type   TEXT,
    constellation TEXT
);

CREATE INDEX IF NOT EXISTS idx_satellites_constellation
    ON satellites(constellation);

CREATE TABLE IF NOT EXISTS anomalies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at  INTEGER NOT NULL,
    type         TEXT    NOT NULL,
    severity     TEXT    NOT NULL,
    primary_id   INTEGER,
    secondary_id INTEGER,
    details      TEXT
);

CREATE INDEX IF NOT EXISTS idx_anomalies_detected_at
    ON anomalies(detected_at);

CREATE INDEX IF NOT EXISTS idx_anomalies_type
    ON anomalies(type);
"""


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def session(db_path: Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
