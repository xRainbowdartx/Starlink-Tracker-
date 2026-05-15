"""Fetch TLE data from CelesTrak.

CelesTrak's GP feed is the canonical free source for current TLEs. The Starlink
group endpoint returns a 3-line-element block (name + line1 + line2 per sat).
"""

from __future__ import annotations

import logging
import time

import requests

from spacetrack.tle.parser import ParsedTLE, parse_block

CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
USER_AGENT = "spacetrack/0.1 (+https://github.com/yourname/spacetrack)"

log = logging.getLogger(__name__)


class FetchError(RuntimeError):
    pass


def fetch_group(group: str = "starlink", *, timeout: float = 30.0) -> str:
    params = {"GROUP": group, "FORMAT": "tle"}
    headers = {"User-Agent": USER_AGENT}

    log.info("Fetching CelesTrak group=%s", group)
    try:
        resp = requests.get(
            CELESTRAK_GP_URL, params=params, headers=headers, timeout=timeout
        )
    except requests.RequestException as exc:
        raise FetchError(f"network error fetching {group}: {exc}") from exc

    if resp.status_code != 200:
        raise FetchError(f"CelesTrak returned HTTP {resp.status_code}")

    text = resp.text.strip()
    if not text or text.lower().startswith("no gp data"):
        raise FetchError(f"CelesTrak returned no data for group={group!r}")

    return text


def fetch_starlink(*, timeout: float = 30.0) -> list[ParsedTLE]:
    raw = fetch_group("starlink", timeout=timeout)
    parsed = parse_block(raw)
    log.info("Parsed %d Starlink TLEs", len(parsed))
    return parsed


def now_unix() -> int:
    return int(time.time())
