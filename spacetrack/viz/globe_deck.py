"""GPU-accelerated globe rendered with pydeck (deck.gl).

Why this exists alongside ``globe3d.py``:

* deck.gl's ``GlobeView`` projects markers onto a real 3D sphere, smooth at
  any zoom, with WebGL handling tens of thousands of points without
  re-rasterising on every frame.
* The Earth surface is a matte dark-grey landmass with hairline borders
  over a flat dark-navy ocean — an operational, Palantir-style basemap
  rather than a photorealistic one, so markers and risk overlays read
  cleanly without competing texture.

Output is a self-contained HTML file loading deck.gl from a CDN.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from functools import lru_cache
from importlib import resources

import pydeck as pdk

from spacetrack.propagate.sgp4_engine import SatPosition

# Palantir-style Earth palette (matches dashboard theme; alpha 255 unless noted).
OCEAN_RGBA: list[int] = [13, 17, 23, 255]        # #0d1117 — flat dark navy
LAND_RGBA: list[int] = [28, 37, 51, 255]         # #1c2533 — matte slate
LAND_BORDER_RGBA: list[int] = [42, 52, 65, 255]  # #2a3441 — hairline


@lru_cache(maxsize=1)
def _land_geojson() -> dict:
    """Load the bundled Natural Earth land polygons (110m resolution)."""
    raw = resources.files("spacetrack.viz.assets").joinpath(
        "land_110m.geojson"
    ).read_text(encoding="utf-8")
    return json.loads(raw)


# Discrete risk styling: same palette as globe3d.py but in RGBA arrays
# (deck.gl expects 0-255 ints). Radii are in meters because GlobeView
# measures everything in real-world units.
RISK_COLORS_RGBA: dict[str, list[int]] = {
    "nominal":  [180, 200, 220, 110],
    "elevated": [255, 204,  68, 230],
    "high":     [255, 136,  51, 255],
    "imminent": [255,  51,  68, 255],
}
RISK_RADII_M: dict[str, int] = {
    "nominal":   25_000,
    "elevated":  60_000,
    "high":      90_000,
    "imminent": 140_000,
}


def _to_record(p: SatPosition, tier: str) -> dict:
    return {
        "name": p.name,
        "norad_id": p.norad_id,
        "tier": tier,
        "longitude": p.longitude,
        "latitude": p.latitude,
        "altitude_km": round(p.altitude_km, 1),
        "color": RISK_COLORS_RGBA[tier],
        "radius": RISK_RADII_M[tier],
    }


def render_globe_deck(
    positions: Sequence[SatPosition],
    *,
    risk_map: Mapping[int, str] | None = None,
    title: str | None = None,
) -> pdk.Deck:
    if not positions:
        raise ValueError("render_globe_deck needs at least one SatPosition")

    data = [
        _to_record(p, (risk_map or {}).get(p.norad_id, "nominal"))
        for p in positions
    ]

    # Ocean: one rectangle the size of the world, filled flat dark navy.
    # GlobeView wraps it onto the sphere, giving a uniform matte backdrop.
    ocean = pdk.Layer(
        "SolidPolygonLayer",
        data=[{"polygon": [
            [-180, -89.9], [180, -89.9], [180, 89.9], [-180, 89.9]
        ]}],
        get_polygon="polygon",
        get_fill_color=OCEAN_RGBA,
        stroked=False,
        filled=True,
    )

    # Land: Natural Earth landmasses, matte slate with hairline border.
    land = pdk.Layer(
        "GeoJsonLayer",
        data=_land_geojson(),
        stroked=True,
        filled=True,
        get_fill_color=LAND_RGBA,
        get_line_color=LAND_BORDER_RGBA,
        line_width_min_pixels=0.5,
        pickable=False,
    )

    sats = pdk.Layer(
        "ScatterplotLayer",
        data,
        get_position="[longitude, latitude]",
        get_radius="radius",
        get_fill_color="color",
        radius_min_pixels=1,
        radius_max_pixels=10,
        pickable=True,
        stroked=False,
        filled=True,
    )

    view = pdk.View(type="GlobeView", controller=True)
    view_state = pdk.ViewState(longitude=-80, latitude=30, zoom=0)

    deck = pdk.Deck(
        views=[view],
        initial_view_state=view_state,
        layers=[ocean, land, sats],
        tooltip={
            "html": (
                "<b>{name}</b> (NORAD {norad_id})<br/>"
                "tier: <b>{tier}</b><br/>"
                "altitude: {altitude_km} km<br/>"
                "lat {latitude}, lon {longitude}"
            ),
            "style": {
                "backgroundColor": "rgba(13, 17, 23, 0.92)",
                "color": "#e1e7ef",
                "fontFamily": (
                    "'JetBrains Mono', 'Fira Code', "
                    "'SF Mono', Consolas, monospace"
                ),
                "fontSize": "12px",
                "padding": "8px 10px",
                "border": "1px solid #2a3441",
                "borderRadius": "2px",
            },
        },
        # GlobeView ignores basemap providers; ocean + land layers are the map.
        map_provider=None,
        map_style=None,
        parameters={"cull": True},
        description=title,
    )
    return deck
