"""GPU-accelerated globe rendered with pydeck (deck.gl).

Why this exists alongside ``globe3d.py``:

* deck.gl's ``GlobeView`` projects markers onto a real 3D sphere, smooth at
  any zoom, with WebGL handling tens of thousands of points without
  re-rasterising on every frame.
* A ``BitmapLayer`` with NASA's Blue Marble image gives a photorealistic
  Earth backdrop that Plotly's ``Scattergeo`` cannot match.

Output is a self-contained HTML file loading deck.gl from a CDN.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pydeck as pdk

from spacetrack.propagate.sgp4_engine import SatPosition

# NASA-served equirectangular Blue Marble. Public, CORS-enabled.
BLUE_MARBLE_URL = (
    "https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57752/"
    "land_ocean_ice_2048.jpg"
)

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

    blue_marble = pdk.Layer(
        "BitmapLayer",
        data=None,
        image=BLUE_MARBLE_URL,
        bounds=[-180, -90, 180, 90],
        opacity=1.0,
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
        layers=[blue_marble, sats],
        tooltip={
            "html": (
                "<b>{name}</b> (NORAD {norad_id})<br/>"
                "tier: <b>{tier}</b><br/>"
                "altitude: {altitude_km} km<br/>"
                "lat {latitude}, lon {longitude}"
            ),
            "style": {
                "backgroundColor": "rgba(6, 9, 15, 0.9)",
                "color": "#dde6f1",
                "fontSize": "12px",
                "padding": "8px",
                "border": "1px solid #2a3a4f",
            },
        },
        # GlobeView ignores basemap providers; the BitmapLayer is the map.
        map_provider=None,
        map_style=None,
        parameters={"cull": True},
        description=title,
    )
    return deck
