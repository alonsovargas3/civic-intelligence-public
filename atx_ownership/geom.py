"""Pure planar geometry for the parcel->district crosswalk (no DB, stdlib only).

Works on GeoJSON-style geometries (Polygon / MultiPolygon) whose rings are lists
of [x, y] pairs. The crosswalk reprojects parcel centroids to lon/lat (pyproj)
and uses point_in_polygon against the district boundary polygons; both helpers
here are coordinate-system agnostic, so they're exercised with plain unit squares.
"""
from __future__ import annotations


def _point_in_ring(point, ring) -> bool:
    """Ray-casting test: is (x, y) inside the closed ring (list of [x, y])?"""
    x, y = point
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        # does the horizontal ray at y cross edge (i, j)?
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _point_in_single(point, rings) -> bool:
    """rings = [exterior, hole1, ...]: inside the exterior and outside every hole."""
    if not rings or not _point_in_ring(point, rings[0]):
        return False
    return not any(_point_in_ring(point, hole) for hole in rings[1:])


def point_in_polygon(point, geom) -> bool:
    """True if `point` (x, y) is inside the GeoJSON Polygon/MultiPolygon `geom`,
    accounting for holes."""
    t = geom.get("type")
    coords = geom.get("coordinates", [])
    if t == "Polygon":
        return _point_in_single(point, coords)
    if t == "MultiPolygon":
        return any(_point_in_single(point, rings) for rings in coords)
    return False


def bbox(geom):
    """Axis-aligned bounding box (minx, miny, maxx, maxy) over all rings of a
    Polygon/MultiPolygon. Used as a cheap prefilter before full point-in-polygon."""
    t = geom.get("type")
    polys = geom.get("coordinates", []) if t == "MultiPolygon" else [geom.get("coordinates", [])]
    xs, ys = [], []
    for rings in polys:
        for x, y in rings[0]:          # exterior ring bounds the whole polygon
            xs.append(x)
            ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys))


def point_in_bbox(point, box) -> bool:
    """True if (x, y) is within the (minx, miny, maxx, maxy) box (inclusive)."""
    x, y = point
    minx, miny, maxx, maxy = box
    return minx <= x <= maxx and miny <= y <= maxy


def _ring_centroid_area(ring):
    """Area-weighted centroid and signed area of one ring (shoelace)."""
    cx = cy = a2 = 0.0
    n = len(ring)
    for i in range(n - 1):
        x0, y0 = ring[i][0], ring[i][1]
        x1, y1 = ring[i + 1][0], ring[i + 1][1]
        cross = x0 * y1 - x1 * y0
        a2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if a2 == 0:                                  # degenerate ring -> vertex mean
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return (sum(xs) / len(xs), sum(ys) / len(ys), 0.0)
    return (cx / (3 * a2), cy / (3 * a2), abs(a2) / 2.0)


def polygon_centroid(geom):
    """A representative interior point (x, y) for a Polygon/MultiPolygon: the
    area-weighted centroid of its single largest exterior ring. Using the largest
    part (rather than averaging across disjoint parts) keeps the point inside the
    geometry, which matters for assigning a parcel to a district."""
    t = geom.get("type")
    coords = geom.get("coordinates", [])
    if t == "Polygon":
        if not coords or not coords[0]:
            raise ValueError("empty Polygon coordinates")
        cx, cy, _ = _ring_centroid_area(coords[0])
        return (cx, cy)
    if t == "MultiPolygon":
        best = None
        for rings in coords:
            if not rings or not rings[0]:
                continue
            cx, cy, area = _ring_centroid_area(rings[0])
            if best is None or area > best[2]:
                best = (cx, cy, area)
        if best is None:
            raise ValueError("empty MultiPolygon coordinates")
        return (best[0], best[1])
    raise ValueError(f"unsupported geometry type: {t}")
