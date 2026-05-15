"""2D ground-track visualization for a single satellite.

Plots the sub-satellite point over a propagation window on a world map.
Useful for sanity-checking orbits and seeing the inclination/coverage.
"""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go

from spacetrack.propagate.sgp4_engine import SatPosition


def render_ground_track(positions: Sequence[SatPosition], *, title: str | None = None) -> go.Figure:
    if not positions:
        raise ValueError("render_ground_track needs at least one SatPosition")

    name = positions[0].name
    norad = positions[0].norad_id

    # Break the path on antimeridian crossings so plotly doesn't draw a line
    # halfway around the world when longitude wraps from +180 to -180.
    segments_lat: list[list[float]] = [[]]
    segments_lon: list[list[float]] = [[]]
    prev_lon = None
    for p in positions:
        if prev_lon is not None and abs(p.longitude - prev_lon) > 180.0:
            segments_lat.append([])
            segments_lon.append([])
        segments_lat[-1].append(p.latitude)
        segments_lon[-1].append(p.longitude)
        prev_lon = p.longitude

    fig = go.Figure()
    for lats, lons in zip(segments_lat, segments_lon):
        if not lats:
            continue
        fig.add_trace(
            go.Scattergeo(
                lat=lats, lon=lons,
                mode="lines",
                line=dict(width=2, color="#ff8c42"),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Mark start and current/end positions distinctly.
    start, end = positions[0], positions[-1]
    fig.add_trace(go.Scattergeo(
        lat=[start.latitude], lon=[start.longitude],
        mode="markers",
        marker=dict(size=10, color="#7afcff", symbol="circle"),
        name="start",
        text=[f"start: {start.when.isoformat(timespec='seconds')}"],
        hoverinfo="text",
    ))
    fig.add_trace(go.Scattergeo(
        lat=[end.latitude], lon=[end.longitude],
        mode="markers",
        marker=dict(size=10, color="#ff5c8a", symbol="diamond"),
        name="end",
        text=[f"end: {end.when.isoformat(timespec='seconds')}"],
        hoverinfo="text",
    ))

    minutes = (end.when - start.when).total_seconds() / 60.0
    fig.update_layout(
        title=title or f"{name} (NORAD {norad}) — ground track ({minutes:.0f} min)",
        paper_bgcolor="#06090f",
        font=dict(color="#dde6f1"),
        geo=dict(
            projection_type="natural earth",
            showland=True, landcolor="#1c2735",
            showocean=True, oceancolor="#06090f",
            showlakes=True, lakecolor="#06090f",
            showcountries=True, countrycolor="#2a3a4f",
            showcoastlines=True, coastlinecolor="#3a4a60",
            bgcolor="#06090f",
        ),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig
