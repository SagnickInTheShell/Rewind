"""Venue geometry helpers: wall segments, zone lookup, spaced point sampling."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.prepared import prep

from rewind.schemas.venue import OUTSIDE, Portal, Venue, Zone


def zone_polygon(z: Zone) -> Polygon:
    return Polygon([(p.x, p.y) for p in z.polygon])


def portal_line(p: Portal) -> LineString:
    a, b = p.segment
    return LineString([(a.x, a.y), (b.x, b.y)])


def portal_midpoint(p: Portal) -> np.ndarray:
    a, b = p.segment
    return np.array([(a.x + b.x) / 2.0, (a.y + b.y) / 2.0])


def portal_normal(p: Portal, venue: Venue) -> np.ndarray:
    """Unit normal of the portal segment pointing from ``from_zone`` towards ``to_zone``."""
    a, b = p.segment
    d = np.array([b.x - a.x, b.y - a.y], dtype=np.float64)
    n = np.array([-d[1], d[0]]) / max(float(np.linalg.norm(d)), 1e-9)
    mid = portal_midpoint(p)
    ref_zone = p.from_zone if p.from_zone != OUTSIDE else p.to_zone
    c = np.array(zone_polygon(venue.zone(ref_zone)).centroid.coords[0])
    toward_ref = float(np.dot(c - mid, n))
    # normal should point AWAY from from_zone (i.e. into to_zone)
    if p.from_zone != OUTSIDE:
        return n if toward_ref < 0 else -n
    return n if toward_ref > 0 else -n


def scaled_segment(p: Portal, factor: float) -> tuple[np.ndarray, np.ndarray]:
    a, b = p.segment
    pa, pb = np.array([a.x, a.y]), np.array([b.x, b.y])
    mid = (pa + pb) / 2
    return mid + (pa - mid) * factor, mid + (pb - mid) * factor


def wall_segments(venue: Venue, closed_portals: Iterable[Portal] | None = None) -> np.ndarray:
    """(N, 4) array of wall segments [ax, ay, bx, by]; closed portals are treated as walls."""
    segs = [[w.a.x, w.a.y, w.b.x, w.b.y] for w in venue.walls]
    closed = list(closed_portals) if closed_portals is not None else [p for p in venue.portals if not p.is_open]
    for p in closed:
        a, b = p.segment
        segs.append([a.x, a.y, b.x, b.y])
    return np.asarray(segs, dtype=np.float64).reshape(-1, 4)


class ZoneLocator:
    """Vectorised point -> zone_id lookup using shapely prepared geometries."""

    def __init__(self, venue: Venue) -> None:
        self.zone_ids = [z.zone_id for z in venue.zones]
        self.polys = [zone_polygon(z) for z in venue.zones]
        self._prepared = [prep(p) for p in self.polys]
        for p in self.polys:
            shapely.prepare(p)

    def locate(self, x: float, y: float) -> str | None:
        pt = shapely.Point(x, y)
        for zid, pp in zip(self.zone_ids, self._prepared, strict=True):
            if pp.covers(pt):
                return zid
        return None

    def locate_many(self, xy: np.ndarray) -> np.ndarray:
        """Return array of zone indices (-1 when outside every zone)."""
        xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
        out = np.full(len(xy), -1, dtype=np.int64)
        for i, poly in enumerate(self.polys):
            inside = shapely.contains_xy(poly, xy[:, 0], xy[:, 1]) | shapely.intersects_xy(
                poly.boundary, xy[:, 0], xy[:, 1])
            out[(out == -1) & inside] = i
        return out

    def locate_ids(self, xy: np.ndarray) -> list[str | None]:
        return [self.zone_ids[i] if i >= 0 else None for i in self.locate_many(xy)]


def sample_points_in_polygon(poly: Polygon, n: int, min_spacing: float, rng: np.random.Generator,
                             max_tries: int = 30, margin: float = 0.0) -> np.ndarray:
    """Poisson-disk style dart throwing inside ``poly``.

    Spacing is relaxed progressively when the polygon is too crowded, so exactly ``n`` points
    are always returned (dense crowds legitimately pack closer than the requested spacing).
    """
    if n <= 0:
        return np.zeros((0, 2))
    shape = poly.buffer(-margin) if margin > 0 and poly.buffer(-margin).area > 0 else poly
    shapely.prepare(shape)
    minx, miny, maxx, maxy = shape.bounds
    pts: list[np.ndarray] = []
    spacing = min_spacing
    cell = max(spacing, 1e-3)
    grid: dict[tuple[int, int], list[int]] = {}
    tries = 0
    while len(pts) < n:
        cand = rng.uniform([minx, miny], [maxx, maxy])
        if not shapely.contains_xy(shape, cand[0], cand[1]):
            continue
        key = (int(cand[0] // cell), int(cand[1] // cell))
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((key[0] + dx, key[1] + dy), []):
                    if np.hypot(*(pts[j] - cand)) < spacing:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            grid.setdefault(key, []).append(len(pts))
            pts.append(cand)
            tries = 0
        else:
            tries += 1
            if tries > max_tries * max(n, 1):
                spacing *= 0.8
                tries = 0
    return np.array(pts)


def point_segment_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> tuple[float, np.ndarray]:
    ab = b - a
    denom = float(np.dot(ab, ab))
    t = 0.0 if denom < 1e-12 else float(np.clip(np.dot(p - a, ab) / denom, 0.0, 1.0))
    q = a + t * ab
    return float(np.linalg.norm(p - q)), q


def segments_intersect(p1: np.ndarray, p2: np.ndarray, q1: np.ndarray, q2: np.ndarray) -> bool:
    """True if segment p1-p2 properly intersects q1-q2 (used to check wall crossings)."""
    def orient(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))

    d1, d2 = orient(q1, q2, p1), orient(q1, q2, p2)
    d3, d4 = orient(p1, p2, q1), orient(p1, p2, q2)
    return (d1 * d2 < 0) and (d3 * d4 < 0)
