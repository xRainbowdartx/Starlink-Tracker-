"""Earth coastlines and land polygons for the 3D globe.

We bundle three Natural Earth GeoJSON files:

* ``coastlines_110m.geojson`` — 110m line segments; available for callers
  that want thin overlay outlines (currently unused by the globe renderer).
* ``land_110m.geojson`` — 110m filled polygons; kept as a fallback / legacy.
* ``land_50m.geojson`` — 50m filled polygons; the resolution actually used
  by the globe. Sharper coastlines (visible fjords, islands like Iceland,
  the Indonesian archipelago) at the cost of a ~2.7 MB asset.

All files load offline; renders are reproducible across machines.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from importlib import resources

import mapbox_earcut as earcut
import numpy as np


@lru_cache(maxsize=1)
def load_segments() -> list[list[tuple[float, float]]]:
    """Return coastlines as a list of (lat, lon) line segments.

    Each segment is one continuous line — separate continents and islands
    come back as separate segments. Caches in-memory after the first call.
    """
    asset = resources.files("spacetrack.viz") / "assets" / "coastlines_110m.geojson"
    with asset.open("r", encoding="utf-8") as fp:
        data = json.load(fp)

    segments: list[list[tuple[float, float]]] = []
    for feature in data.get("features", []):
        geom = feature.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates") or []

        if gtype == "LineString":
            segments.append([(lat, lon) for lon, lat in coords])
        elif gtype == "MultiLineString":
            for line in coords:
                segments.append([(lat, lon) for lon, lat in line])
        # Other geometry types in this dataset are not expected; ignore them.

    return segments


def project_to_sphere(
    segments: list[list[tuple[float, float]]],
    *,
    radius: float = 1.001,
) -> tuple[list[float], list[float], list[float]]:
    """Project (lat, lon) segments onto a unit sphere for Scatter3d lines.

    Segments are joined into single x/y/z arrays with ``None`` inserted at
    the boundaries so Plotly renders each segment as a separate polyline
    instead of connecting them across the globe.

    Args:
        segments: Output of ``load_segments()``.
        radius:   Sphere radius in Earth-radii. Slightly above 1.0 keeps the
                  coastline visible just outside the Earth surface fill.

    Returns:
        Three parallel lists (xs, ys, zs) suitable for ``go.Scatter3d``.
    """
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for segment in segments:
        for lat_deg, lon_deg in segment:
            lat = math.radians(lat_deg)
            lon = math.radians(lon_deg)
            xs.append(radius * math.cos(lat) * math.cos(lon))
            ys.append(radius * math.cos(lat) * math.sin(lon))
            zs.append(radius * math.sin(lat))
        # Break between segments so Plotly doesn't draw a stray connector.
        xs.append(float("nan"))
        ys.append(float("nan"))
        zs.append(float("nan"))
    return xs, ys, zs


# ---------------------------------------------------------------------------
# Land polygons — used to rasterise a land/ocean mask for surfacecolor.
# ---------------------------------------------------------------------------

# A polygon as list of (lat, lon) tuples, paired with a (lat_min, lat_max,
# lon_min, lon_max) bounding box for fast point-in-polygon short-circuiting.
_BBox = tuple[float, float, float, float]
_Polygon = list[tuple[float, float]]


_LAND_ASSET = "land_50m.geojson"  # bumped from 110m for sharper coastlines


@lru_cache(maxsize=1)
def _load_land_polygons() -> list[tuple[_Polygon, _BBox]]:
    """Parse the bundled land GeoJSON into (polygon, bbox) tuples."""
    asset = resources.files("spacetrack.viz") / "assets" / _LAND_ASSET
    with asset.open("r", encoding="utf-8") as fp:
        data = json.load(fp)

    out: list[tuple[_Polygon, _BBox]] = []
    for feature in data.get("features", []):
        geom = feature.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates") or []

        # In a Polygon, coords[0] is the outer ring; in a MultiPolygon each
        # element's [0] is the outer ring. We ignore inner rings (holes) at
        # 110m resolution they're negligible (e.g. lakes inside continents).
        rings: list[list[list[float]]] = []
        if gtype == "Polygon":
            rings = [coords[0]] if coords else []
        elif gtype == "MultiPolygon":
            rings = [poly[0] for poly in coords if poly]

        for ring in rings:
            polygon = [(lat, lon) for lon, lat in ring]
            if len(polygon) < 3:
                continue
            lats = [p[0] for p in polygon]
            lons = [p[1] for p in polygon]
            bbox = (min(lats), max(lats), min(lons), max(lons))
            out.append((polygon, bbox))
    return out


def _point_in_polygon(lat: float, lon: float, polygon: _Polygon) -> bool:
    """Ray-casting point-in-polygon. Polygon is a list of (lat, lon)."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]
        if ((lat_i > lat) != (lat_j > lat)) and (
            lon < (lon_j - lon_i) * (lat - lat_i) / (lat_j - lat_i + 1e-12) + lon_i
        ):
            inside = not inside
        j = i
    return inside


def _is_land(lat: float, lon: float) -> bool:
    for polygon, (lat_min, lat_max, lon_min, lon_max) in _load_land_polygons():
        if lat < lat_min or lat > lat_max or lon < lon_min or lon > lon_max:
            continue
        if _point_in_polygon(lat, lon, polygon):
            return True
    return False


# ---------------------------------------------------------------------------
# Land mesh — filled continents as triangulated Mesh3d data.
# ---------------------------------------------------------------------------

def _subdivide_polygon(
    polygon: _Polygon, max_edge_deg: float
) -> _Polygon:
    """Insert intermediate points wherever an edge is longer than the limit.

    Triangle edges between two sphere-surface points are chords through the
    sphere; long chords dip noticeably below the surface. By subdividing
    long polygon edges before triangulation, every resulting triangle is
    small enough that its chords stay close to the actual sphere surface.
    """
    out: _Polygon = []
    n = len(polygon)
    for i in range(n):
        lat_a, lon_a = polygon[i]
        lat_b, lon_b = polygon[(i + 1) % n]
        out.append((lat_a, lon_a))
        dlat = lat_b - lat_a
        dlon = lon_b - lon_a
        length = math.hypot(dlat, dlon)
        if length > max_edge_deg:
            steps = int(length / max_edge_deg) + 1
            for k in range(1, steps):
                t = k / steps
                out.append((lat_a + t * dlat, lon_a + t * dlon))
    return out


@lru_cache(maxsize=4)
def land_mesh(
    radius: float = 1.004, max_edge_deg: float = 3.0
) -> tuple[
    tuple[float, ...], tuple[float, ...], tuple[float, ...],
    tuple[int, ...], tuple[int, ...], tuple[int, ...],
]:
    """Triangulate land polygons and project onto the sphere.

    Returns six tuples ``(xs, ys, zs, i, j, k)`` ready to feed directly to
    a Plotly ``Mesh3d`` trace. Each (i[n], j[n], k[n]) triplet indexes into
    (xs, ys, zs) to form one filled triangle. Cached after the first call.
    """
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    i_list: list[int] = []
    j_list: list[int] = []
    k_list: list[int] = []

    for polygon, _bbox in _load_land_polygons():
        dense = _subdivide_polygon(polygon, max_edge_deg=max_edge_deg)
        if len(dense) < 3:
            continue

        # mapbox-earcut wants flat (x, y) pairs and a list of ring sizes.
        # We have a single outer ring per polygon; treat (lon, lat) as (x, y).
        flat = np.array(
            [[lon, lat] for (lat, lon) in dense], dtype=np.float64
        )
        ring_ends = np.array([len(dense)], dtype=np.uint32)
        triangle_indices = earcut.triangulate_float64(flat, ring_ends)
        if triangle_indices.size == 0:
            continue

        offset = len(xs)
        for lat_deg, lon_deg in dense:
            lat = math.radians(lat_deg)
            lon = math.radians(lon_deg)
            xs.append(radius * math.cos(lat) * math.cos(lon))
            ys.append(radius * math.cos(lat) * math.sin(lon))
            zs.append(radius * math.sin(lat))

        triangle_indices = triangle_indices.astype(int)
        # earcut returns a flat array [a0, b0, c0, a1, b1, c1, ...].
        i_list.extend(int(idx) + offset for idx in triangle_indices[0::3])
        j_list.extend(int(idx) + offset for idx in triangle_indices[1::3])
        k_list.extend(int(idx) + offset for idx in triangle_indices[2::3])

    return (
        tuple(xs), tuple(ys), tuple(zs),
        tuple(i_list), tuple(j_list), tuple(k_list),
    )


@lru_cache(maxsize=4)
def land_mask_grid(resolution: int = 180) -> tuple[tuple[float, ...], ...]:
    """Rasterise the land polygons onto the sphere's surface grid.

    Returns a (resolution+1) × (resolution+1) grid of 1.0 (land) or 0.0
    (ocean) matching the parameterisation used by the sphere trace in
    ``globe3d.py``. Uses vectorised numpy ray-casting so higher resolutions
    stay fast (~0.5 s for resolution=180). Cached after the first call.
    """
    # Build the lat/lon grid that matches the sphere parameterisation.
    j = np.arange(resolution + 1, dtype=np.float64)
    i = np.arange(resolution + 1, dtype=np.float64)
    v = j / resolution * math.pi
    u = i / resolution * 2.0 * math.pi
    lat_1d = 90.0 - np.degrees(v)                 # shape (R+1,)
    lon_1d = np.degrees(u)
    lon_1d = np.where(lon_1d > 180.0, lon_1d - 360.0, lon_1d)
    lat_grid, lon_grid = np.meshgrid(lat_1d, lon_1d, indexing="ij")

    mask = np.zeros_like(lat_grid, dtype=bool)
    for polygon, (lat_min, lat_max, lon_min, lon_max) in _load_land_polygons():
        in_bbox = (
            (lat_grid >= lat_min)
            & (lat_grid <= lat_max)
            & (lon_grid >= lon_min)
            & (lon_grid <= lon_max)
        )
        if not in_bbox.any():
            continue

        # Vectorised ray-casting: for each polygon edge, flip the inside
        # flag wherever a ray cast westward from the grid point crosses it.
        poly = np.asarray(polygon)   # shape (N, 2): (lat, lon)
        lat_i = poly[:, 0]
        lon_i = poly[:, 1]
        lat_j = np.roll(lat_i, 1)
        lon_j = np.roll(lon_i, 1)
        inside = np.zeros_like(lat_grid, dtype=bool)
        for k in range(poly.shape[0]):
            ai, aj = lat_i[k], lat_j[k]
            bi, bj = lon_i[k], lon_j[k]
            cond1 = (ai > lat_grid) != (aj > lat_grid)
            cond2 = lon_grid < (bj - bi) * (lat_grid - ai) / (aj - ai + 1e-12) + bi
            inside ^= cond1 & cond2

        mask |= in_bbox & inside

    floats = mask.astype(np.float64)
    return tuple(tuple(row.tolist()) for row in floats)
