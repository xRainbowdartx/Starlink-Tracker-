"""Tests for the TLE parser using synthetic fixtures (no network)."""

from __future__ import annotations

import pytest

from spacetrack.tle.parser import TLEParseError, parse, parse_block


ISS_NAME = "ISS (ZARYA)"
ISS_LINE1 = "1 25544U 98067A   24320.54791667  .00016717  00000-0  10270-3 0  9991"
ISS_LINE2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49309239427692"


STARLINK_NAME = "STARLINK-1007"
STARLINK_LINE1 = "1 44713U 19074A   24320.91666667  .00002182  00000-0  14897-3 0  9993"
STARLINK_LINE2 = "2 44713  53.0541 132.6789 0001482  85.6213 274.4928 15.06414000274566"


def test_parse_iss_extracts_norad_id():
    tle = parse(ISS_NAME, ISS_LINE1, ISS_LINE2)
    assert tle.norad_id == 25544
    assert tle.name == "ISS (ZARYA)"


def test_parse_iss_orbital_elements_in_expected_ranges():
    tle = parse(ISS_NAME, ISS_LINE1, ISS_LINE2)
    assert 51.0 < tle.inclination < 52.0
    assert 0.0 <= tle.eccentricity < 0.01
    assert 15.0 < tle.mean_motion < 16.0


def test_parse_starlink_extracts_norad_id():
    tle = parse(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2)
    assert tle.norad_id == 44713
    assert tle.name.startswith("STARLINK")


def test_parse_starlink_inclination_is_typical_shell():
    tle = parse(STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2)
    assert 52.0 < tle.inclination < 54.0


def test_parse_rejects_wrong_line_prefix():
    bad_l1 = "9 25544U 98067A   24320.54791667  .00016717  00000-0  10270-3 0  9994"
    with pytest.raises(TLEParseError):
        parse(ISS_NAME, bad_l1, ISS_LINE2)


def test_parse_rejects_wrong_length():
    short = "1 25544U 98067A   24320.54791667  .00016717"
    with pytest.raises(TLEParseError):
        parse(ISS_NAME, short, ISS_LINE2)


def test_parse_rejects_bad_checksum():
    bad = ISS_LINE1[:-1] + "0"
    with pytest.raises(TLEParseError, match="checksum"):
        parse(ISS_NAME, bad, ISS_LINE2)


def test_parse_block_handles_multiple_satellites():
    text = "\n".join([
        ISS_NAME, ISS_LINE1, ISS_LINE2,
        STARLINK_NAME, STARLINK_LINE1, STARLINK_LINE2,
    ])
    tles = parse_block(text)
    assert len(tles) == 2
    assert {t.norad_id for t in tles} == {25544, 44713}


def test_parse_block_rejects_partial_record():
    text = "\n".join([ISS_NAME, ISS_LINE1])  # missing line 2
    with pytest.raises(TLEParseError):
        parse_block(text)
