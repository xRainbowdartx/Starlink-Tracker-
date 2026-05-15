"""Constellation overview rendered on an orthographic globe.

Uses Plotly's ``Scattergeo`` trace with an orthographic projection so the
output is a rotatable Earth-shaped map that natively renders continents,
country borders, coastlines, and oceans — the same geographic layers used
by the ``groundtrack`` view, just wrapped onto a globe.

Each satellite plots at its current sub-satellite point (lat/lon). Altitude
is preserved as marker color via the colorbar on the right.
"""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go

from spacetrack.propagate.sgp4_engine import SatPosition

# Match the ground-track palette exactly so the two views feel like one tool.
LAND_COLOR = "#1c2735"
OCEAN_COLOR = "#06090f"
COUNTRY_COLOR = "#2a3a4f"
COASTLINE_COLOR = "#3a4a60"
BG_COLOR = "#06090f"


def render_globe(positions: Sequence[SatPosition], *, title: str | None = None) -> go.Figure:
    if not positions:
        raise ValueError("render_globe needs at least one SatPosition")

    lats = [p.latitude for p in positions]
    lons = [p.longitude for p in positions]
    alts = [p.altitude_km for p in positions]
    hover = [
        (
            f"{p.name} (NORAD {p.norad_id})<br>"
            f"lat {p.latitude:.2f}°, lon {p.longitude:.2f}°<br>"
            f"alt {p.altitude_km:.1f} km"
        )
        for p in positions
    ]

    sats = go.Scattergeo(
        lat=lats,
        lon=lons,
        mode="markers",
        marker=dict(
            size=2,
            color=alts,
            colorscale="Plasma",
            colorbar=dict(title="Altitude (km)"),
            opacity=0.9,
            line=dict(width=0),
        ),
        text=hover,
        hoverinfo="text",
        name="Starlink",
    )

    fig = go.Figure(data=[sats])
    fig.update_layout(
        title=title or f"Starlink constellation, {len(positions):,} satellites",
        paper_bgcolor=BG_COLOR,
        font=dict(color="#dde6f1"),
        geo=dict(
            projection_type="orthographic",
            projection=dict(rotation=dict(lon=-80, lat=30, roll=0)),
            # Country borders + coastlines add hundreds of SVG paths that
            # re-rasterise on every rotation frame. Disabling them is the
            # single biggest win for spin smoothness. Filled continents
            # plus the major lakes still read clearly as geography.
            showland=True, landcolor=LAND_COLOR,
            showocean=True, oceancolor=OCEAN_COLOR,
            showlakes=True, lakecolor=OCEAN_COLOR,
            showcountries=False,
            showcoastlines=False,
            bgcolor=BG_COLOR,
        ),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig
