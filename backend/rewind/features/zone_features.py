"""Zone feature engine: per zone, per ``window_s`` window → :class:`ZoneFeatures` rows.

The same :class:`FeatureEngine` is used for video (via :func:`video_window_inputs`) and for the
simulator (``rewind.simulation.runner``), which is what makes real/simulated comparisons fair.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd

from rewind.features import crowd_metrics as cm
from rewind.perception.fusion import fuse_zone
from rewind.schemas.features import NUMERIC_FEATURES, FeatureSource, ZoneFeatures, ZoneTimeseries
from rewind.schemas.venue import OUTSIDE, Venue
from rewind.settings import Settings
from rewind.venue.geometry import portal_midpoint, portal_normal
from rewind.venue.graph import VenueGraph

FEATURE_COLUMNS = ["t", "zone_id", *NUMERIC_FEATURES[:5], "dominant_dir", *NUMERIC_FEATURES[5:], "source"]
PORTAL_BAND_M = 1.5  # flow samples within this distance of a portal segment count towards its flux
MAX_TRACK_SCALE = 3.0


@dataclass
class WindowInput:
    t: float
    zone_id: str
    count: float
    area_m2: float
    vectors: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    abs_curl: float = 0.0
    inflow: float = 0.0  # persons / s
    outflow: float = 0.0
    source: FeatureSource = "fused"


def downstream_capacity(graph: VenueGraph) -> dict[str, float]:
    """Σ capacity of open portals leaving each zone *towards the exits*.

    An edge z→v counts when v is strictly closer (along open portals) to ``OUTSIDE`` than z.
    Zones with no reachable exit fall back to all their open outgoing capacity.
    """
    og = graph.open_graph()
    dist: dict[str, float] = {}
    if OUTSIDE in og:
        dist = dict(nx.single_source_dijkstra_path_length(og.reverse(copy=False), OUTSIDE, weight="length"))
    caps: dict[str, float] = {}
    for z in graph.zone_ids:
        dz = dist.get(z, math.inf)
        total = 0.0
        for _, v, d in graph.g.out_edges(z, data=True):
            if not d["is_open"]:
                continue
            if math.isinf(dz) or dist.get(v, math.inf) < dz:
                total += float(d["capacity"])
        caps[z] = total
    return caps


class FeatureEngine:
    def __init__(self, venue: Venue, settings: Settings, graph: VenueGraph | None = None) -> None:
        self.venue = venue
        self.s = settings
        self.set_graph(graph or VenueGraph(venue, settings.features.specific_flow_p_per_m_s))

    def set_graph(self, graph: VenueGraph) -> None:
        self.graph = graph
        self.out_cap = downstream_capacity(graph)

    def raw_row(self, w: WindowInput) -> dict[str, Any]:
        f = self.s.features
        v = np.asarray(w.vectors, dtype=np.float64).reshape(-1, 2)
        area = max(w.area_m2, 1e-6)
        density = max(w.count, 0.0) / area
        dom = cm.dominant_dir(v, f.min_speed_for_direction)
        vvar = cm.velocity_var(v)
        mv = cm.mean_velocity(v)
        return {
            "t": w.t, "zone_id": w.zone_id, "count": max(w.count, 0.0), "density": density,
            "mean_speed": cm.mean_speed(v), "speed_var": cm.speed_var(v), "velocity_var": vvar,
            "dominant_dir": dom,
            "direction_entropy": cm.direction_entropy(v, f.direction_bins, f.min_speed_for_direction),
            "counterflow_index": cm.counterflow_index(v, dom, f.counterflow_angle_deg, f.min_speed_for_direction),
            "flow_instability": 0.0,  # filled in finalize (needs the previous window)
            "inflow_rate": max(w.inflow, 0.0), "outflow_rate": max(w.outflow, 0.0),
            "bottleneck_pressure": cm.bottleneck_pressure(w.inflow, self.out_cap.get(w.zone_id, 0.0)),
            "crowd_pressure": cm.crowd_pressure(density, vvar),
            "source": w.source,
            "_mvx": float(mv[0]), "_mvy": float(mv[1]), "_curl": float(w.abs_curl), "_n": len(v),
        }

    def finalize(self, rows: list[dict[str, Any]]) -> pd.DataFrame:
        """Compute flow instability, apply causal rolling-mean smoothing per zone, enforce ranges."""
        if not rows:
            return pd.DataFrame(columns=FEATURE_COLUMNS)
        df = pd.DataFrame(rows).sort_values(["zone_id", "t"]).reset_index(drop=True)
        dt = self.s.features.window_s
        out = []
        for _, g in df.groupby("zone_id", sort=False):
            g = g.copy()
            dvx = g["_mvx"].diff()
            dvy = g["_mvy"].diff()
            dent = g["direction_entropy"].diff().abs()
            accel = np.hypot(dvx, dvy) / dt
            inst = 0.5 * (accel + dent / dt) + g["_curl"]
            # A window without motion samples carries no information about change.
            has = (g["_n"] > 0) & (g["_n"].shift(1).fillna(0) > 0)
            g["flow_instability"] = np.where(has, inst.fillna(0.0), g["_curl"])
            k = max(1, int(self.s.features.smoothing_window))
            num = [c for c in NUMERIC_FEATURES]
            g[num] = g[num].rolling(k, min_periods=1).mean()
            # circular smoothing for direction
            ang = g["dominant_dir"].to_numpy()
            cs = pd.Series(np.cos(ang)).rolling(k, min_periods=1).mean()
            sn = pd.Series(np.sin(ang)).rolling(k, min_periods=1).mean()
            g["dominant_dir"] = np.arctan2(sn.to_numpy(), cs.to_numpy())
            out.append(g)
        res = pd.concat(out, ignore_index=True)
        res["direction_entropy"] = res["direction_entropy"].clip(0, 1)
        res["counterflow_index"] = res["counterflow_index"].clip(0, 1)
        for c in NUMERIC_FEATURES:
            if c not in ("direction_entropy", "counterflow_index"):
                res[c] = res[c].clip(lower=0)
        res = res[FEATURE_COLUMNS].sort_values(["t", "zone_id"]).reset_index(drop=True)
        return res


# ---- video-specific window assembly ------------------------------------------------------------
def _track_transitions(tracks: pd.DataFrame, venue: Venue, graph: VenueGraph, entry_radius: float = 3.0
                       ) -> pd.DataFrame:
    """Zone transitions (t, zone_id, kind in/out) from trajectories, incl. births/deaths at gates."""
    if tracks.empty:
        return pd.DataFrame(columns=["t", "zone_id", "kind"])
    events: list[tuple[float, str, str]] = []
    entry_mid = [portal_midpoint(p) for p in graph.entry_portals()]
    exit_mid = [portal_midpoint(p) for p in graph.exit_portals(open_only=False)]

    def near(pt: np.ndarray, mids: list[np.ndarray]) -> bool:
        return any(float(np.linalg.norm(pt - m)) <= entry_radius for m in mids)

    for _, g in tracks.sort_values(["track_id", "t"]).groupby("track_id", sort=False):
        zones = g["zone_id"].to_numpy()
        ts = g["t"].to_numpy()
        xy = g[["wx", "wy"]].to_numpy()
        first, last = zones[0], zones[-1]
        if isinstance(first, str) and near(xy[0], entry_mid):
            events.append((float(ts[0]), first, "in"))
        for i in range(1, len(zones)):
            a, b = zones[i - 1], zones[i]
            if a != b:
                if isinstance(a, str):
                    events.append((float(ts[i]), a, "out"))
                if isinstance(b, str):
                    events.append((float(ts[i]), b, "in"))
        if isinstance(last, str) and near(xy[-1], exit_mid):
            events.append((float(ts[-1]), last, "out"))
    return pd.DataFrame(events, columns=["t", "zone_id", "kind"])


def portal_geometry(venue: Venue) -> list[tuple[str, str, np.ndarray, np.ndarray, np.ndarray, float]]:
    """(from, to, a, b, normal from→to, width) per portal."""
    out = []
    for p in venue.portals:
        a = np.array([p.segment[0].x, p.segment[0].y])
        b = np.array([p.segment[1].x, p.segment[1].y])
        out.append((p.from_zone, p.to_zone, a, b, portal_normal(p, venue), p.width_m if p.is_open else 0.0))
    return out


def _dist_to_segment(xy: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ab = b - a
    tt = np.clip(((xy - a) @ ab) / max(float(ab @ ab), 1e-12), 0, 1)
    q = a + tt[:, None] * ab
    return np.asarray(np.linalg.norm(xy - q, axis=1))


def flux_by_zone(samples: pd.DataFrame, densities: dict[str, float], portals: list[tuple[str, str, np.ndarray,
                 np.ndarray, np.ndarray, float]]) -> dict[str, tuple[float, float]]:
    """(inflow, outflow) persons/s per zone from flow samples near portals: flux = ρ·(v·n)·width."""
    res: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    if samples.empty:
        return {}
    xy = samples[["x", "y"]].to_numpy()
    v = samples[["vx", "vy"]].to_numpy()
    for fz, tz, a, b, n, width in portals:
        if width <= 0:
            continue
        sel = _dist_to_segment(xy, a, b) <= PORTAL_BAND_M
        if not sel.any():
            continue
        vn = v[sel] @ n
        rho = np.mean([densities.get(z, 0.0) for z in (fz, tz) if z != OUTSIDE] or [0.0])
        fwd, bwd = cm.portal_flux(vn, float(rho), width)
        if fz != OUTSIDE:
            res[fz][1] += fwd
            res[fz][0] += bwd
        if tz != OUTSIDE:
            res[tz][0] += fwd
            res[tz][1] += bwd
    return {z: (vals[0], vals[1]) for z, vals in res.items()}


def video_window_inputs(density_zone: pd.DataFrame, tracks: pd.DataFrame, flow_zone: pd.DataFrame,
                        flow_curl: pd.DataFrame, venue: Venue, graph: VenueGraph, settings: Settings
                        ) -> list[WindowInput]:
    s = settings
    w = s.features.window_s
    if density_zone.empty:
        return []
    t_max = float(density_zone["t"].max())
    n_win = max(1, int(math.ceil((t_max + 1e-9) / w)))
    edges = np.arange(n_win + 1) * w

    def win_idx(t: pd.Series) -> np.ndarray:
        return np.asarray(np.clip(np.ceil(t.to_numpy() / w - 1e-9).astype(int) - 1, 0, n_win - 1))

    dz = density_zone.assign(win=win_idx(density_zone["t"]))
    dz_g = dz.groupby(["win", "zone_id"]).agg(count_det=("count_det", "mean"), count_map=("count_map", "mean"),
                                               area=("area_m2", "first")).reset_index()
    dz_rows: dict[tuple[int, str], tuple[float, float, float]] = {
        (int(k), str(z)): (float(cd), float(cmap), float(a))
        for k, z, cd, cmap, a in zip(dz_g["win"], dz_g["zone_id"], dz_g["count_det"], dz_g["count_map"],
                                     dz_g["area"], strict=True)}
    tr = tracks.assign(win=win_idx(tracks["t"])) if not tracks.empty else tracks.assign(win=[])
    tr_groups = {k: g for k, g in tr.groupby(["win", "zone_id"])} if not tr.empty else {}
    fl = flow_zone.assign(win=win_idx(flow_zone["t"])) if not flow_zone.empty else flow_zone.assign(win=[])
    fl_groups = {k: g for k, g in fl.groupby(["win", "zone_id"])} if not fl.empty else {}
    fl_win = {k: g for k, g in fl.groupby("win")} if not fl.empty else {}
    cu = flow_curl.assign(win=win_idx(flow_curl["t"])) if not flow_curl.empty else flow_curl.assign(win=[])
    cu_g = cu.groupby(["win", "zone_id"])["abs_curl"].mean().to_dict() if not cu.empty else {}
    trans = _track_transitions(tracks, venue, graph)
    trans = trans.assign(win=win_idx(trans["t"])) if not trans.empty else trans.assign(win=[])
    trans_counts = trans.groupby(["win", "zone_id", "kind"]).size().to_dict() if not trans.empty else {}
    portals = portal_geometry(venue)
    p = s.perception
    inputs: list[WindowInput] = []
    for k in range(n_win):
        fused = {}
        for z in venue.zone_ids:
            if (k, z) not in dz_rows:
                continue
            c_det, c_map, z_area = dz_rows[(k, z)]
            tg = tr_groups.get((k, z))
            fg = fl_groups.get((k, z))
            fused[z] = fuse_zone(
                count_det=c_det, count_map=c_map, area_m2=z_area,
                track_vectors=tg[["vx", "vy"]].to_numpy() if tg is not None else np.zeros((0, 2)),
                n_tracks=int(tg["track_id"].nunique()) if tg is not None else 0,
                flow_vectors=fg[["vx", "vy"]].to_numpy() if fg is not None else np.zeros((0, 2)),
                flow_abs_curl=float(cu_g.get((k, z), 0.0)), switch=p.hybrid_switch_density,
                band=p.hybrid_blend_band, min_tracks=p.min_tracks_for_velocity)
        dens = {z: f.density for z, f in fused.items()}
        flux = flux_by_zone(fl_win.get(k, pd.DataFrame(columns=["x", "y", "vx", "vy"])), dens, portals)
        for z, f in fused.items():
            area = dz_rows[(k, z)][2]
            if f.velocity_source == "tracks":
                tg = tr_groups.get((k, z))
                n_tr = int(tg["track_id"].nunique()) if tg is not None else 0
                scale = float(np.clip(f.count / max(n_tr, 1), 1.0, MAX_TRACK_SCALE))
                inflow = trans_counts.get((k, z, "in"), 0) * scale / w
                outflow = trans_counts.get((k, z, "out"), 0) * scale / w
            else:
                inflow, outflow = flux.get(z, (0.0, 0.0))
            inputs.append(WindowInput(t=float(edges[k + 1]), zone_id=z, count=f.count, area_m2=area,
                                      vectors=f.vectors, abs_curl=f.abs_curl, inflow=inflow, outflow=outflow,
                                      source=f.source))
    return inputs


def compute_features(inputs: list[WindowInput], engine: FeatureEngine) -> pd.DataFrame:
    return engine.finalize([engine.raw_row(i) for i in inputs])


def to_timeseries(df: pd.DataFrame, run_id: str, origin: str, window_s: float, zones: list[str],
                  include_rows: bool = True) -> ZoneTimeseries:
    rows = [ZoneFeatures.model_validate(r) for r in df.to_dict("records")] if include_rows else []
    return ZoneTimeseries(run_id=run_id, origin=origin, window_s=window_s, zones=zones, rows=rows)  # type: ignore[arg-type]
