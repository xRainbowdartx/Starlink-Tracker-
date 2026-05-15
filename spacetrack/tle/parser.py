"""TLE parsing, validation, and orbital-element extraction.

Wraps the `sgp4` library so callers get a typed object with NORAD ID and the
six classical orbital elements pulled out of line 2, without having to know
the column-by-column TLE format.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sgp4.api import Satrec


@dataclass(frozen=True)
class ParsedTLE:
    name: str
    norad_id: int
    line1: str
    line2: str
    epoch_jd: float
    inclination: float    # degrees
    raan: float           # degrees
    eccentricity: float
    arg_perigee: float    # degrees
    mean_anomaly: float   # degrees
    mean_motion: float    # revs/day


class TLEParseError(ValueError):
    """Raised when a TLE block is malformed or fails checksum."""


def _verify_checksum(line: str) -> bool:
    if len(line) != 69:
        return False
    total = 0
    for ch in line[:68]:
        if ch.isdigit():
            total += int(ch)
        elif ch == "-":
            total += 1
    return total % 10 == int(line[68])


def parse(name: str, line1: str, line2: str) -> ParsedTLE:
    name = name.strip()
    line1 = line1.rstrip()
    line2 = line2.rstrip()

    if not line1.startswith("1 ") or not line2.startswith("2 "):
        raise TLEParseError("TLE lines must start with '1 ' and '2 '")
    if len(line1) != 69 or len(line2) != 69:
        raise TLEParseError(f"TLE lines must be 69 chars (got {len(line1)}, {len(line2)})")
    if not _verify_checksum(line1):
        raise TLEParseError(f"Line 1 checksum failed: {line1!r}")
    if not _verify_checksum(line2):
        raise TLEParseError(f"Line 2 checksum failed: {line2!r}")

    try:
        sat = Satrec.twoline2rv(line1, line2)
    except Exception as exc:
        raise TLEParseError(f"sgp4 rejected TLE: {exc}") from exc

    return ParsedTLE(
        name=name,
        norad_id=sat.satnum,
        line1=line1,
        line2=line2,
        epoch_jd=sat.jdsatepoch + sat.jdsatepochF,
        inclination=math.degrees(sat.inclo),
        raan=math.degrees(sat.nodeo),
        eccentricity=sat.ecco,
        arg_perigee=math.degrees(sat.argpo),
        mean_anomaly=math.degrees(sat.mo),
        mean_motion=sat.no_kozai * 1440.0 / (2.0 * math.pi),
    )


def parse_block(text: str) -> list[ParsedTLE]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) % 3 != 0:
        raise TLEParseError(
            f"Expected 3-line TLE blocks (name + line1 + line2), got {len(lines)} lines"
        )

    out: list[ParsedTLE] = []
    for i in range(0, len(lines), 3):
        out.append(parse(lines[i], lines[i + 1], lines[i + 2]))
    return out
