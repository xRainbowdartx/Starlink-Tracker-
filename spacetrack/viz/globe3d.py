"""Constellation overview rendered on an orthographic globe.

Uses Plotly's ``Scattergeo`` trace with an orthographic projection so the
output is a rotatable Earth-shaped map that natively renders continents,
country borders, coastlines, and oceans — the same geographic layers used
by the ``groundtrack`` view, just wrapped onto a globe.

Each satellite plots at its current sub-satellite point (lat/lon). Marker
color encodes either altitude (continuous Plasma colorbar) or decay risk
tier (discrete legend with size + color emphasis on flagged sats).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import plotly.graph_objects as go

from spacetrack.propagate.sgp4_engine import SatPosition

# Match the ground-track palette exactly so the two views feel like one tool.
LAND_COLOR = "#1c2735"
OCEAN_COLOR = "#06090f"
COUNTRY_COLOR = "#2a3a4f"
COASTLINE_COLOR = "#3a4a60"
BG_COLOR = "#06090f"

# Risk tier styling: gray nominal sats form a dim backdrop; flagged sats
# step up in both size and saturation so they pop on the rotating globe.
RISK_STYLE: dict[str, dict] = {
    "nominal":  {"color": "#6a7a90", "size": 2, "opacity": 0.55, "order": 0},
    "elevated": {"color": "#ffcc44", "size": 4, "opacity": 0.95, "order": 1},
    "high":     {"color": "#ff8833", "size": 6, "opacity": 1.0,  "order": 2},
    "imminent": {"color": "#ff3344", "size": 9, "opacity": 1.0,  "order": 3},
}


def _altitude_trace(positions: Sequence[SatPosition]) -> go.Scattergeo:
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
    return go.Scattergeo(
        lat=lats, lon=lons, mode="markers",
        marker=dict(
            size=2,
            color=alts,
            colorscale="Plasma",
            colorbar=dict(title="Altitude (km)"),
            opacity=0.9,
            line=dict(width=0),
        ),
        text=hover, hoverinfo="text", name="Starlink",
    )


def _risk_traces(
    positions: Sequence[SatPosition], risk_map: Mapping[int, str]
) -> list[go.Scattergeo]:
    buckets: dict[str, list[SatPosition]] = {tier: [] for tier in RISK_STYLE}
    for p in positions:
        tier = risk_map.get(p.norad_id, "nominal")
        buckets.setdefault(tier, []).append(p)

    traces: list[go.Scattergeo] = []
    # Lowest-order tier first so higher-risk markers render on top.
    for tier in sorted(RISK_STYLE, key=lambda t: RISK_STYLE[t]["order"]):
        sats = buckets.get(tier, [])
        if not sats:
            continue
        style = RISK_STYLE[tier]
        hover = [
            (
                f"{p.name} (NORAD {p.norad_id})<br>"
                f"risk: <b>{tier}</b><br>"
                f"alt {p.altitude_km:.1f} km<br>"
                f"lat {p.latitude:.2f}°, lon {p.longitude:.2f}°"
            )
            for p in sats
        ]
        traces.append(
            go.Scattergeo(
                lat=[p.latitude for p in sats],
                lon=[p.longitude for p in sats],
                mode="markers",
                marker=dict(
                    size=style["size"],
                    color=style["color"],
                    opacity=style["opacity"],
                    line=dict(width=0),
                ),
                text=hover, hoverinfo="text",
                name=f"{tier} ({len(sats):,})",
                showlegend=True,
            )
        )
    return traces


def _split_flagged(
    positions: Sequence[SatPosition], risk_map: Mapping[int, str]
) -> tuple[list[SatPosition], list[SatPosition]]:
    """Split positions into (nominal, flagged) by risk tier."""
    nominal: list[SatPosition] = []
    flagged: list[SatPosition] = []
    for p in positions:
        if risk_map.get(p.norad_id, "nominal") == "nominal":
            nominal.append(p)
        else:
            flagged.append(p)
    return nominal, flagged


def _thin(positions: Sequence[SatPosition], factor: int) -> list[SatPosition]:
    """Keep every Nth position (factor=1 -> keep all)."""
    if factor <= 1:
        return list(positions)
    return list(positions[::factor])


def _build_frame_traces(
    positions: Sequence[SatPosition],
    risk_map: Mapping[int, str] | None,
    *,
    pulse_scale: float = 1.0,
    thin_nominal: int = 1,
) -> list[go.Scattergeo]:
    """Build the trace list for one animation frame.

    ``pulse_scale`` is a multiplier applied to the imminent marker size
    so that 2-frame oscillation reads as a pulse.

    ``thin_nominal`` keeps every Nth nominal sat; flagged sats are always
    rendered in full. Use >1 to cut SVG load and speed up rotation.
    """
    if risk_map is None:
        kept = _thin(positions, thin_nominal)
        return [_altitude_trace(kept)]

    nominal, flagged = _split_flagged(positions, risk_map)
    nominal = _thin(nominal, thin_nominal)
    kept = nominal + flagged

    traces = _risk_traces(kept, risk_map)
    if pulse_scale != 1.0:
        for tr in traces:
            if tr.name and tr.name.startswith("imminent"):
                tr.marker.size = RISK_STYLE["imminent"]["size"] * pulse_scale
    return traces


def render_globe(
    positions: Sequence[SatPosition],
    *,
    title: str | None = None,
    risk_map: Mapping[int, str] | None = None,
    pulse: bool = False,
    time_frames: Sequence[tuple[str, Sequence[SatPosition]]] | None = None,
    frame_duration_ms: int = 600,
    thin_nominal: int = 1,
) -> go.Figure:
    """Render an orthographic globe of the constellation.

    Modes:
      * default — single instant, marker color = altitude (Plasma).
      * ``risk_map`` set — single instant, marker color = decay tier.
      * ``pulse=True`` (with ``risk_map``) — autoplay a 2-frame oscillation
        on imminent markers so they throb.
      * ``time_frames`` set — slider + play button stepping through positions
        at successive instants. When ``risk_map`` is also set, only flagged
        sats are animated; nominal sats stay as a static backdrop trace so
        each frame stays small and rotation stays responsive.

    ``thin_nominal`` keeps every Nth nominal sat (flagged always kept).
    Use 3-5 to cut SVG load when rotation feels sluggish.
    """
    if not positions:
        raise ValueError("render_globe needs at least one SatPosition")

    flagged_count = (
        sum(1 for p in positions if risk_map.get(p.norad_id, "nominal") != "nominal")
        if risk_map else 0
    )
    if risk_map is None:
        default_title = f"Starlink constellation, {len(positions):,} satellites"
    else:
        default_title = f"Starlink decay watch — {flagged_count:,} flagged of {len(positions):,}"

    frames: list[go.Frame] = []
    slider_steps: list[dict] = []
    updatemenus: list[dict] = []

    if time_frames and risk_map is not None:
        # Static backdrop = thinned nominal sats from the first frame; animated
        # foreground = flagged sats per frame. Drastically reduces per-frame
        # payload (10k -> ~1.5k) and keeps the static layer GPU-friendly.
        first_positions = time_frames[0][1]
        nominal0, _ = _split_flagged(first_positions, risk_map)
        nominal0 = _thin(nominal0, thin_nominal)
        static_trace = _risk_traces(nominal0, {p.norad_id: "nominal" for p in nominal0})

        for label, frame_positions in time_frames:
            _, flagged = _split_flagged(frame_positions, risk_map)
            flag_traces = _risk_traces(flagged, risk_map)
            # Frames must include ALL traces in order; reuse the static
            # backdrop unchanged across frames.
            frames.append(go.Frame(data=static_trace + flag_traces, name=label))
            slider_steps.append(dict(
                method="animate",
                label=label,
                args=[[label], dict(
                    mode="immediate",
                    frame=dict(duration=frame_duration_ms, redraw=True),
                    transition=dict(duration=0),
                )],
            ))

        base_traces = static_trace + _risk_traces(
            [p for p in first_positions
             if risk_map.get(p.norad_id, "nominal") != "nominal"],
            risk_map,
        )
    else:
        base_traces = _build_frame_traces(positions, risk_map, thin_nominal=thin_nominal)

    fig = go.Figure(data=base_traces)

    if time_frames and risk_map is None:
        for label, frame_positions in time_frames:
            frames.append(go.Frame(
                data=_build_frame_traces(frame_positions, risk_map, thin_nominal=thin_nominal),
                name=label,
            ))
            slider_steps.append(dict(
                method="animate",
                label=label,
                args=[[label], dict(
                    mode="immediate",
                    frame=dict(duration=frame_duration_ms, redraw=True),
                    transition=dict(duration=0),
                )],
            ))
    elif not time_frames and pulse and risk_map is not None:
        frames.append(go.Frame(
            data=_build_frame_traces(positions, risk_map,
                                     pulse_scale=1.0, thin_nominal=thin_nominal),
            name="pulse-0",
        ))
        frames.append(go.Frame(
            data=_build_frame_traces(positions, risk_map,
                                     pulse_scale=1.7, thin_nominal=thin_nominal),
            name="pulse-1",
        ))

    if frames:
        fig.frames = frames
        play_args = [None, dict(
            frame=dict(duration=frame_duration_ms, redraw=True),
            fromcurrent=True,
            transition=dict(duration=0),
            mode="immediate",
        )]
        pause_args = [[None], dict(
            frame=dict(duration=0, redraw=False),
            mode="immediate",
            transition=dict(duration=0),
        )]
        updatemenus.append(dict(
            type="buttons",
            direction="left",
            showactive=False,
            x=0.05, y=0.02, xanchor="left", yanchor="bottom",
            bgcolor="rgba(6,9,15,0.7)",
            bordercolor="#2a3a4f", borderwidth=1,
            font=dict(color="#dde6f1"),
            buttons=[
                dict(label="▶ Play", method="animate", args=play_args),
                dict(label="❚❚ Pause", method="animate", args=pause_args),
            ],
        ))

    layout: dict = dict(
        title=title or default_title,
        paper_bgcolor=BG_COLOR,
        font=dict(color="#dde6f1"),
        legend=dict(
            bgcolor="rgba(6,9,15,0.7)",
            bordercolor="#2a3a4f",
            borderwidth=1,
            font=dict(color="#dde6f1"),
        ),
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
        margin=dict(l=0, r=0, t=40, b=60 if time_frames else 0),
    )
    if updatemenus:
        layout["updatemenus"] = updatemenus
    if time_frames:
        layout["sliders"] = [dict(
            active=0,
            x=0.18, y=0.02, len=0.78, xanchor="left", yanchor="bottom",
            pad=dict(b=10, t=10),
            currentvalue=dict(prefix="time: ", font=dict(color="#dde6f1")),
            bgcolor="#1c2735",
            bordercolor="#2a3a4f",
            tickcolor="#dde6f1",
            font=dict(color="#dde6f1"),
            steps=slider_steps,
        )]
    fig.update_layout(**layout)
    return fig
