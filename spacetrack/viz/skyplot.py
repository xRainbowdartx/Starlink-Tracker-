"""Observer-centric visualizations: sky plot + elevation timeline.

Two views combined into one Plotly figure with subplots:
1. Polar sky plot — azimuth (compass bearing) vs. elevation (sky angle).
   Center = directly overhead (zenith), outer ring = horizon. This is the
   plot satellite-spotting apps use to tell you "look up and to the southwest."
2. Elevation timeline — elevation vs. time with the two visibility thresholds
   (0° horizon, 10° practical) marked as colored bands.
"""

from __future__ import annotations

from collections.abc import Sequence

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from spacetrack.observer.visibility import LookAngle, ObserverLocation, Pass


HORIZON_DEG = 0.0
PRACTICAL_DEG = 10.0


def render_sky(
    angles: Sequence[LookAngle],
    observer: ObserverLocation,
    *,
    sat_name: str,
    horizon_passes: Sequence[Pass] | None = None,
    practical_passes: Sequence[Pass] | None = None,
) -> go.Figure:
    if not angles:
        raise ValueError("render_sky needs at least one LookAngle")

    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.45, 0.55],
        specs=[[{"type": "polar"}, {"type": "xy"}]],
        subplot_titles=("Sky view (zenith = center)", "Elevation over time"),
        horizontal_spacing=0.12,
    )

    # ---- Polar sky plot ----
    # Convert elevation to a radial coordinate where 0 = zenith, 90 = horizon
    # so the plot reads like a fisheye photo of the sky.
    above = [a for a in angles if a.elevation >= HORIZON_DEG]
    if above:
        fig.add_trace(
            go.Scatterpolar(
                r=[90.0 - a.elevation for a in above],
                theta=[a.azimuth for a in above],
                mode="lines+markers",
                marker=dict(
                    size=4,
                    color=[a.elevation for a in above],
                    colorscale="Viridis",
                    cmin=0, cmax=90,
                    showscale=False,
                ),
                line=dict(width=1, color="#7afcff"),
                text=[
                    f"{a.when.strftime('%H:%M:%S UTC')}<br>"
                    f"az {a.azimuth:.1f}°, el {a.elevation:.1f}°<br>"
                    f"range {a.range_km:,.0f} km"
                    for a in above
                ],
                hoverinfo="text",
                name="visible path",
                showlegend=False,
            ),
            row=1, col=1,
        )

    # ---- Elevation timeline ----
    times = [a.when for a in angles]
    elevs = [a.elevation for a in angles]

    fig.add_trace(
        go.Scatter(
            x=times, y=elevs, mode="lines",
            line=dict(width=2, color="#dde6f1"),
            name="elevation",
            hovertemplate="%{x|%H:%M:%S}<br>el %{y:.1f}°<extra></extra>",
        ),
        row=1, col=2,
    )

    # Shade visibility windows. Use add_shape with explicit xref="x2"/yref="y2 domain"
    # because add_vrect doesn't handle mixed polar+xy subplots cleanly.
    def _vband(x0, x1, fillcolor, opacity):
        fig.add_shape(
            type="rect", xref="x2", yref="y2 domain",
            x0=x0, x1=x1, y0=0, y1=1,
            fillcolor=fillcolor, opacity=opacity, line_width=0, layer="below",
        )

    if horizon_passes:
        for p in horizon_passes:
            _vband(p.rise.when, p.fall.when, "#7afcff", 0.10)
    if practical_passes:
        for p in practical_passes:
            _vband(p.rise.when, p.fall.when, "#ff8c42", 0.20)

    fig.add_shape(
        type="line", xref="x2 domain", yref="y2",
        x0=0, x1=1, y0=HORIZON_DEG, y1=HORIZON_DEG,
        line=dict(color="#7afcff", width=1, dash="dot"),
    )
    fig.add_shape(
        type="line", xref="x2 domain", yref="y2",
        x0=0, x1=1, y0=PRACTICAL_DEG, y1=PRACTICAL_DEG,
        line=dict(color="#ff8c42", width=1, dash="dot"),
    )

    # ---- Layout ----
    fig.update_polars(
        radialaxis=dict(
            range=[0, 90], tickvals=[0, 30, 60, 90],
            ticktext=["zenith", "60°", "30°", "horizon"],
            gridcolor="#2a3a4f",
        ),
        angularaxis=dict(
            direction="clockwise", rotation=90,
            tickmode="array",
            tickvals=[0, 90, 180, 270],
            ticktext=["N", "E", "S", "W"],
            gridcolor="#2a3a4f",
        ),
        bgcolor="#06090f",
    )
    fig.update_yaxes(title_text="elevation (°)", range=[-90, 90], row=1, col=2)
    fig.update_xaxes(title_text="UTC", row=1, col=2)

    n_horizon = len(horizon_passes) if horizon_passes else 0
    n_practical = len(practical_passes) if practical_passes else 0
    fig.update_layout(
        title=(
            f"{sat_name} viewed from {observer.name}<br>"
            f"<span style='font-size:12px'>"
            f"{n_horizon} pass{'es' if n_horizon != 1 else ''} above horizon · "
            f"{n_practical} above 10° (practical visibility)"
            f"</span>"
        ),
        paper_bgcolor="#06090f",
        plot_bgcolor="#06090f",
        font=dict(color="#dde6f1"),
        margin=dict(l=40, r=20, t=80, b=40),
        showlegend=False,
    )
    return fig
