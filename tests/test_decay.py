"""Tests for the re-entry-risk decay detector."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from spacetrack.anomaly import decay
from spacetrack.storage import db


# --- Physics ----------------------------------------------------------------

def test_semi_major_axis_matches_iss_regime():
    # ISS-like: ~15.5 rev/day -> a ~ 6790 km (altitude ~ 420 km).
    a = decay.semi_major_axis_km(15.5)
    assert 6770 < a < 6810


def test_semi_major_axis_matches_starlink_regime():
    # Starlink shell ~ 550 km altitude -> a ~ 6921 km -> n ~ 15.07 rev/day.
    a = decay.semi_major_axis_km(15.07)
    assert 6905 < a < 6940


def test_perigee_apogee_circular_orbit_collapses():
    p, ap = decay.perigee_apogee_km(15.07, 0.0)
    assert p == pytest.approx(ap, abs=1e-9)


def test_perigee_apogee_eccentric_orbit_spreads():
    p, ap = decay.perigee_apogee_km(15.07, 0.01)
    # Apogee well above perigee for e=0.01 (spread ~ 2 * a * e ~ 138 km)
    assert (ap - p) == pytest.approx(2 * decay.semi_major_axis_km(15.07) * 0.01, rel=1e-6)


def test_semi_major_axis_rejects_nonpositive_mean_motion():
    with pytest.raises(ValueError):
        decay.semi_major_axis_km(0.0)


# --- Risk classification ----------------------------------------------------

def _assess(perigee_target_km: float, decay_rate: float | None = None):
    """Build an assessment whose perigee matches the target altitude."""
    # Pick mean_motion that yields a = perigee_target_km + R_earth (circular).
    a = perigee_target_km + decay.EARTH_RADIUS_KM
    n_rad_s = math.sqrt(decay.EARTH_MU_KM3_S2 / a**3)
    mean_motion = n_rad_s * decay.SECONDS_PER_DAY / (2.0 * math.pi)

    prior_mm = None
    prior_epoch = None
    if decay_rate is not None:
        # da/dt = -2a/(3n) * dn/dt  =>  dn/dt = -3 n dr / (2 a)  (r negative when decaying)
        # Use unit time separation = 1 day so prior_mm easy to derive.
        dn_dt = -3.0 * mean_motion * decay_rate / (2.0 * a)
        prior_mm = mean_motion - dn_dt * 1.0
        prior_epoch = 2461170.0
    return decay.assess(
        norad_id=99999,
        name="TEST-SAT",
        epoch=2461171.0,
        mean_motion=mean_motion,
        eccentricity=0.0,
        prior_mean_motion=prior_mm,
        prior_epoch=prior_epoch,
    )


def test_risk_nominal_for_starlink_operational_altitude():
    assert _assess(550.0).risk == "nominal"


def test_risk_elevated_below_450_km():
    assert _assess(440.0).risk == "elevated"


def test_risk_high_below_300_km():
    assert _assess(280.0).risk == "high"


def test_risk_imminent_below_200_km():
    assert _assess(150.0).risk == "imminent"


def test_risk_elevated_when_decay_rate_modest_even_at_safe_altitude():
    a = _assess(550.0, decay_rate=-2.0)
    assert a.decay_rate_km_per_day == pytest.approx(-2.0, rel=0.05)
    assert a.risk == "elevated"


def test_risk_high_when_decay_rate_steep_even_at_safe_altitude():
    a = _assess(550.0, decay_rate=-8.0)
    assert a.risk == "high"


def test_perigee_classification_wins_over_mild_decay_rate():
    # Imminent perigee should not be downgraded by a mild decay rate.
    a = _assess(150.0, decay_rate=-2.0)
    assert a.risk == "imminent"


# --- Decay rate -------------------------------------------------------------

def test_decay_rate_negative_when_mean_motion_rising():
    # Mean motion goes up by 0.001 rev/day over one day -> orbit shrinking.
    rate = decay._decay_rate_km_per_day(15.10, 15.099, 1.0)
    assert rate is not None and rate < 0


def test_decay_rate_returns_none_for_tiny_dt():
    assert decay._decay_rate_km_per_day(15.10, 15.10, 1e-6) is None


def test_days_to_reentry_present_only_when_decaying_and_above_floor():
    # Decaying, perigee above floor -> ETA computed.
    a = _assess(300.0, decay_rate=-5.0)
    assert a.days_to_reentry is not None
    assert a.days_to_reentry == pytest.approx((300.0 - 120.0) / 5.0, rel=0.05)

    # Not decaying -> no ETA.
    a = _assess(300.0, decay_rate=None)
    assert a.days_to_reentry is None


# --- DB-backed assess_satellite + scan --------------------------------------

@pytest.fixture
def populated_db(tmp_path: Path) -> Path:
    p = tmp_path / "test.db"
    db.init_db(p)
    with db.session(p) as conn:
        # Nominal Starlink sat (550 km, two stable snapshots).
        _insert_sat(conn, 10001, "STARLINK-NOMINAL", "starlink",
                    snapshots=[(2461170.0, 15.07), (2461171.0, 15.0701)])
        # Decaying sat: perigee 280 km, mean motion rising fast.
        _insert_sat(conn, 10002, "STARLINK-FALLING", "starlink",
                    snapshots=[(2461170.0, _mm_for_alt(295.0)),
                               (2461171.0, _mm_for_alt(280.0))])
        # Single-snapshot sat at very low altitude (no trend, but flagged on perigee).
        _insert_sat(conn, 10003, "STARLINK-LOWBALL", "starlink",
                    snapshots=[(2461171.0, _mm_for_alt(150.0))])
        # Non-Starlink (should be excluded from default scan).
        _insert_sat(conn, 20001, "DEBRIS-FALLING", "iridium",
                    snapshots=[(2461171.0, _mm_for_alt(180.0))])
    return p


def _mm_for_alt(altitude_km: float) -> float:
    a = altitude_km + decay.EARTH_RADIUS_KM
    n_rad_s = math.sqrt(decay.EARTH_MU_KM3_S2 / a**3)
    return n_rad_s * decay.SECONDS_PER_DAY / (2.0 * math.pi)


def _insert_sat(conn, norad_id, name, constellation, *, snapshots):
    conn.execute(
        "INSERT INTO satellites (norad_id, name, constellation) VALUES (?, ?, ?)",
        (norad_id, name, constellation),
    )
    for epoch, mm in snapshots:
        conn.execute(
            """
            INSERT INTO tle_snapshots
            (norad_id, epoch, fetched_at, line1, line2, eccentricity, mean_motion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (norad_id, epoch, int(epoch), "stub-line1", "stub-line2", 0.0, mm),
        )


def test_assess_satellite_returns_none_for_unknown(populated_db):
    with db.session(populated_db) as conn:
        assert decay.assess_satellite(conn, 999_999_999) is None


def test_assess_satellite_uses_two_most_recent_snapshots(populated_db):
    with db.session(populated_db) as conn:
        a = decay.assess_satellite(conn, 10002)
    assert a is not None
    assert a.decay_rate_km_per_day is not None
    assert a.decay_rate_km_per_day < 0


def test_assess_satellite_handles_single_snapshot(populated_db):
    with db.session(populated_db) as conn:
        a = decay.assess_satellite(conn, 10003)
    assert a is not None
    assert a.decay_rate_km_per_day is None
    assert a.risk == "imminent"


def test_scan_flags_only_satellites_at_or_above_min_risk(populated_db):
    with db.session(populated_db) as conn:
        results = decay.scan(conn, min_risk="elevated")
    norad_ids = {r.norad_id for r in results}
    assert 10002 in norad_ids  # falling
    assert 10003 in norad_ids  # lowball
    assert 10001 not in norad_ids  # nominal sat excluded


def test_scan_respects_constellation_filter(populated_db):
    with db.session(populated_db) as conn:
        starlink_only = decay.scan(conn, min_risk="elevated", constellation="starlink")
        all_sats = decay.scan(conn, min_risk="elevated", constellation=None)
    assert 20001 not in {r.norad_id for r in starlink_only}
    assert 20001 in {r.norad_id for r in all_sats}


def test_scan_sorts_highest_risk_first(populated_db):
    with db.session(populated_db) as conn:
        results = decay.scan(conn, min_risk="elevated")
    ordered = [decay._RISK_ORDER[r.risk] for r in results]
    assert ordered == sorted(ordered, reverse=True)
