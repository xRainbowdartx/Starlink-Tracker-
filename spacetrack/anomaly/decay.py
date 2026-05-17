"""Re-entry risk assessment from TLE mean motion.

A satellite in LEO loses energy to atmospheric drag and slowly spirals inward.
As the semi-major axis shrinks the mean motion (revs/day) rises, so a rising
mean motion is the most direct TLE-visible signature of decay.

Two assessments per satellite:

* **Static** — from a single TLE, derive semi-major axis (Kepler's third law),
  perigee, and apogee. Low perigee alone is enough to flag risk regardless of
  history.
* **Trend** — given the two most recent snapshots, compute the rate of change
  of mean motion and translate it into an altitude-loss rate (km/day) and a
  back-of-the-envelope days-to-reentry estimate. Returns ``None`` for the
  trend fields when only one snapshot exists.

Risk tiers are perigee-driven and calibrated for the mega-constellation
regime (Starlink operates ~540-570 km nominally; deorbit-phase passes drop
through 300 km in a matter of days):

* ``imminent`` — perigee < 200 km
* ``high``     — perigee < 300 km, or decay rate < -5 km/day
* ``elevated`` — perigee < 450 km, or decay rate < -1 km/day
* ``nominal``  — otherwise
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from typing import Literal

EARTH_MU_KM3_S2 = 398600.4418
EARTH_RADIUS_KM = 6371.0
SECONDS_PER_DAY = 86400.0

Risk = Literal["nominal", "elevated", "high", "imminent"]
_RISK_ORDER: dict[Risk, int] = {"nominal": 0, "elevated": 1, "high": 2, "imminent": 3}


@dataclass(frozen=True)
class DecayAssessment:
    norad_id: int
    name: str
    epoch: float                          # JD of latest TLE
    mean_motion: float                    # rev/day
    eccentricity: float
    semi_major_axis_km: float
    perigee_km: float
    apogee_km: float
    altitude_km: float                    # midpoint (perigee + apogee) / 2
    decay_rate_km_per_day: float | None   # negative = losing altitude
    days_to_reentry: float | None         # None when not decaying or unknown
    risk: Risk


def semi_major_axis_km(mean_motion_rev_per_day: float) -> float:
    """Kepler's third law: a = (μ / n²)^(1/3) with n in rad/s."""
    if mean_motion_rev_per_day <= 0:
        raise ValueError("mean_motion must be positive")
    n_rad_s = mean_motion_rev_per_day * 2.0 * math.pi / SECONDS_PER_DAY
    return (EARTH_MU_KM3_S2 / (n_rad_s * n_rad_s)) ** (1.0 / 3.0)


def perigee_apogee_km(mean_motion: float, eccentricity: float) -> tuple[float, float]:
    a = semi_major_axis_km(mean_motion)
    perigee = a * (1.0 - eccentricity) - EARTH_RADIUS_KM
    apogee = a * (1.0 + eccentricity) - EARTH_RADIUS_KM
    return perigee, apogee


def _classify(perigee_km: float, decay_rate_km_per_day: float | None) -> Risk:
    risk: Risk = "nominal"
    if perigee_km < 450.0:
        risk = "elevated"
    if perigee_km < 300.0:
        risk = "high"
    if perigee_km < 200.0:
        risk = "imminent"
    if decay_rate_km_per_day is not None:
        if decay_rate_km_per_day < -5.0 and _RISK_ORDER[risk] < _RISK_ORDER["high"]:
            risk = "high"
        elif decay_rate_km_per_day < -1.0 and _RISK_ORDER[risk] < _RISK_ORDER["elevated"]:
            risk = "elevated"
    return risk


def _decay_rate_km_per_day(
    mm_new: float, mm_old: float, dt_days: float
) -> float | None:
    """d(altitude)/dt from d(mean motion)/dt.

    Since a ∝ n^(-2/3), da/dn = -2a/(3n), so da/dt = -2a/(3n) * dn/dt.
    Returns None if the epoch separation is too small to trust.
    """
    if dt_days < 1e-3:
        return None
    a = semi_major_axis_km(mm_new)
    dn_dt = (mm_new - mm_old) / dt_days
    return -(2.0 * a) / (3.0 * mm_new) * dn_dt


def assess(
    *,
    norad_id: int,
    name: str,
    epoch: float,
    mean_motion: float,
    eccentricity: float,
    prior_mean_motion: float | None = None,
    prior_epoch: float | None = None,
    reentry_floor_km: float = 120.0,
) -> DecayAssessment:
    """Build a DecayAssessment from raw TLE-derived fields.

    Pure function — does no DB access. Pass ``prior_*`` from the
    second-newest snapshot to enable trend analysis.
    """
    perigee, apogee = perigee_apogee_km(mean_motion, eccentricity)
    altitude = 0.5 * (perigee + apogee)

    decay_rate: float | None = None
    days_to_reentry: float | None = None
    if prior_mean_motion is not None and prior_epoch is not None:
        decay_rate = _decay_rate_km_per_day(
            mean_motion, prior_mean_motion, epoch - prior_epoch
        )
        if decay_rate is not None and decay_rate < 0:
            margin = perigee - reentry_floor_km
            if margin > 0:
                days_to_reentry = margin / (-decay_rate)

    return DecayAssessment(
        norad_id=norad_id,
        name=name,
        epoch=epoch,
        mean_motion=mean_motion,
        eccentricity=eccentricity,
        semi_major_axis_km=semi_major_axis_km(mean_motion),
        perigee_km=perigee,
        apogee_km=apogee,
        altitude_km=altitude,
        decay_rate_km_per_day=decay_rate,
        days_to_reentry=days_to_reentry,
        risk=_classify(perigee, decay_rate),
    )


def assess_satellite(
    conn: sqlite3.Connection, norad_id: int
) -> DecayAssessment | None:
    """Assess one satellite using its two most recent snapshots."""
    rows = conn.execute(
        """
        SELECT s.name, t.epoch, t.mean_motion, t.eccentricity
        FROM tle_snapshots t
        JOIN satellites s ON s.norad_id = t.norad_id
        WHERE t.norad_id = ?
        ORDER BY t.epoch DESC
        LIMIT 2
        """,
        (norad_id,),
    ).fetchall()
    if not rows:
        return None

    latest = rows[0]
    prior = rows[1] if len(rows) > 1 else None
    return assess(
        norad_id=norad_id,
        name=latest["name"],
        epoch=latest["epoch"],
        mean_motion=latest["mean_motion"],
        eccentricity=latest["eccentricity"],
        prior_mean_motion=prior["mean_motion"] if prior else None,
        prior_epoch=prior["epoch"] if prior else None,
    )


def scan(
    conn: sqlite3.Connection,
    *,
    min_risk: Risk = "elevated",
    constellation: str | None = "starlink",
) -> list[DecayAssessment]:
    """Assess every tracked satellite; return those at or above ``min_risk``.

    Results are sorted highest-risk first, then by ascending perigee.
    """
    if constellation:
        norad_rows = conn.execute(
            "SELECT norad_id FROM satellites WHERE constellation = ?",
            (constellation,),
        ).fetchall()
    else:
        norad_rows = conn.execute("SELECT norad_id FROM satellites").fetchall()

    threshold = _RISK_ORDER[min_risk]
    flagged: list[DecayAssessment] = []
    for row in norad_rows:
        assessment = assess_satellite(conn, row["norad_id"])
        if assessment is None:
            continue
        if _RISK_ORDER[assessment.risk] >= threshold:
            flagged.append(assessment)

    flagged.sort(key=lambda a: (-_RISK_ORDER[a.risk], a.perigee_km))
    return flagged
