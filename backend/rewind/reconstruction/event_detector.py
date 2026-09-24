"""Rule-based incident event detection on smoothed zone features and risk states (Section 7.11)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from rewind.explain.narrator import Narrator, fmt_clock
from rewind.schemas.events import EventType, IncidentEvent
from rewind.schemas.risk import RISK_ORDER, RISK_STATES, RiskState
from rewind.settings import Settings
from rewind.venue.graph import VenueGraph

MIN_EVENT_DENSITY = 0.3  # people/m²: motion-pattern events are ignored in near-empty zones


@dataclass
class RawEvent:
    t_start: float
    t_end: float | None
    zone_id: str
    type: EventType
    severity: RiskState
    title: str
    detail: str
    evidence: dict[str, float] = field(default_factory=dict)
    ref: str | None = None  # auxiliary link (e.g. SPILLOVER source zone)


def runs(t: np.ndarray, cond: np.ndarray, min_duration: float, window: float) -> list[tuple[float, float]]:
    """Maximal runs where ``cond`` holds, lasting at least ``min_duration`` seconds (window end times)."""
    out: list[tuple[float, float]] = []
    start: int | None = None
    for i, c in enumerate(cond):
        if c and start is None:
            start = i
        if (not c or i == len(cond) - 1) and start is not None:
            end = i if c else i - 1
            t0 = float(t[start]) - window  # window start of the first window
            t1 = float(t[end])
            if t1 - t0 >= min_duration - 1e-9:
                out.append((float(t[start]), t1))
            start = None
    return out


def rolling_slope(t: np.ndarray, y: np.ndarray, span_s: float) -> np.ndarray:
    """Least-squares slope of y over the trailing ``span_s`` seconds (per sample)."""
    out = np.zeros(len(y))
    j = 0
    for i in range(len(y)):
        while t[i] - t[j] > span_s:
            j += 1
        if i - j >= 2:
            tt, yy = t[j: i + 1], y[j: i + 1]
            tc = tt - tt.mean()
            den = float((tc**2).sum())
            out[i] = float((tc * (yy - yy.mean())).sum() / den) if den > 0 else 0.0
    return out


def merge_events(events: Iterable[RawEvent], gap_s: float) -> list[RawEvent]:
    """Merge consecutive events of the same (zone, type) whose gap is ≤ ``gap_s``."""
    merged: list[RawEvent] = []
    for e in sorted(events, key=lambda x: (x.zone_id, x.type, x.title, x.t_start)):
        if merged:
            last = merged[-1]
            same = (last.zone_id, last.type, last.title) == (e.zone_id, e.type, e.title)
            if same and last.t_end is not None and e.t_start - last.t_end <= gap_s and e.type not in (
                    "RISK_STATE_CHANGE", "PEAK_RISK", "DE_ESCALATION", "SPILLOVER"):
                last.t_end = max(last.t_end, e.t_end or e.t_start)
                for k, v in e.evidence.items():
                    last.evidence[k] = max(last.evidence.get(k, v), v)
                if RISK_ORDER[e.severity] > RISK_ORDER[last.severity]:
                    last.severity = e.severity
                continue
        merged.append(e)
    return merged


class EventDetector:
    def __init__(self, graph: VenueGraph, settings: Settings, narrator: Narrator | None = None) -> None:
        self.g = graph
        self.s = settings
        self.e = settings.events
        self.window = settings.features.window_s
        self.nar = narrator or Narrator(graph.venue, settings, graph)

    def _state_at(self, states: pd.Series, t: float) -> RiskState:
        s = states[states.index <= t + 1e-9]
        return s.iloc[-1] if len(s) else "LOW"  # type: ignore[no-any-return]

    def _sev(self, states: pd.Series, t: float, floor: RiskState = "LOW") -> RiskState:
        st = self._state_at(states, t)
        return RISK_STATES[max(RISK_ORDER[st], RISK_ORDER[floor])]

    def detect(self, features: pd.DataFrame, risk_df: pd.DataFrame, global_df: pd.DataFrame) -> list[RawEvent]:
        ev: list[RawEvent] = []
        if features.empty:
            return ev
        f = features.merge(risk_df[["t", "zone_id", "ensemble_score", "state"]], on=["t", "zone_id"], how="left")
        f["state"] = f["state"].fillna("LOW")
        state_series = {z: g.set_index("t")["state"] for z, g in f.groupby("zone_id")}
        for zid, g in f.sort_values("t").groupby("zone_id", sort=False):
            ev += self._zone_events(str(zid), g.reset_index(drop=True), state_series[zid])
        ev += self._spillover(state_series)
        ev += self._peak(global_df, state_series)
        return merge_events(ev, self.e.min_duration_s)

    # ---- per-zone triggers ----------------------------------------------------------------
    def _zone_events(self, z: str, g: pd.DataFrame, states: pd.Series) -> list[RawEvent]:
        e, w = self.e, self.window
        t = g["t"].to_numpy()
        dens = g["density"].to_numpy()
        occupied = dens >= MIN_EVENT_DENSITY
        name = self.nar.zone_label(z)
        gate = self.nar.portal_near(z)
        out: list[RawEvent] = []

        # ENTRY_SURGE — source zones only
        if z in self.g.venue.sources:
            inflow = g["inflow_rate"].to_numpy()
            span = min(e.surge_baseline_s, max(t[-1] / 3.0, 5 * w))
            base = inflow[t <= span]
            if len(base) >= 3:
                mu, sd = float(base.mean()), float(base.std())
                thr = mu + e.surge_sigma * max(sd, 0.1 * mu + 0.1)
                for t0, t1 in runs(t, (inflow > thr) & (t > span), e.min_duration_s, w):
                    peak = float(inflow[(t >= t0) & (t <= t1)].max())
                    out.append(RawEvent(t0, t1, z, "ENTRY_SURGE", self._sev(states, t0, "MEDIUM"),
                                        f"Entry surge at {gate or name}",
                                        f"Inflow into {name} rose to {peak:.1f} people/s against a baseline of "
                                        f"{mu:.1f} people/s.", {"inflow_rate": peak, "baseline": mu}))

        # DENSITY_RISING
        slope = rolling_slope(t, dens, e.density_slope_window_s)
        for t0, t1 in runs(t, (slope > e.density_slope_threshold) & occupied, 3 * w, w):
            sel = (t >= t0) & (t <= t1)
            d0, d1 = float(dens[sel][0]), float(dens[sel][-1])
            out.append(RawEvent(t0, t1, z, "DENSITY_RISING", self._sev(states, t0),
                                f"Density rising in {self.nar.zone_name(z)}",
                                f"Density in {name} climbed from {d0:.1f} to {d1:.1f} people/m² "
                                f"(up to {float(slope[sel].max()):.2f} people/m² per second).",
                                {"density": d1, "density_slope": float(slope[sel].max())}))

        # DENSITY_THRESHOLD — one event per level
        levels = self.s.risk.density_levels
        for lvl_name, lvl, sev in (("caution", levels.caution, "MEDIUM"), ("high", levels.high, "HIGH"),
                                   ("critical", levels.critical, "CRITICAL")):
            above = dens >= lvl
            if above.any():
                i = int(np.argmax(above))
                below_after = np.where(~above[i:])[0]
                t_end = float(t[i + below_after[0] - 1]) if len(below_after) else None
                out.append(RawEvent(float(t[i]), t_end, z, "DENSITY_THRESHOLD", self._sev(states, t[i], sev),  # type: ignore[arg-type]
                                    f"Density reached {lvl_name} level in {self.nar.zone_name(z)}",
                                    f"Density in {name} crossed {lvl:.1f} people/m² ({lvl_name} level).",
                                    {"density": float(dens[i]), "level": lvl}))

        # BOTTLENECK_FORMED
        bp = g["bottleneck_pressure"].to_numpy()
        for t0, t1 in runs(t, (bp > e.bottleneck_threshold) & occupied, e.min_duration_s, w):
            peak = float(bp[(t >= t0) & (t <= t1)].max())
            where = f"at {gate}" if gate and self.nar.has_own_gate(z) else (
                f"towards {gate}" if gate else f"in {self.nar.zone_name(z)}")
            out.append(RawEvent(t0, t1, z, "BOTTLENECK_FORMED", self._sev(states, t0, "MEDIUM"),
                                f"Bottleneck detected {where}",
                                f"Inflow into {name} exceeded the estimated capacity of the way out "
                                f"(peak {peak:.1f}×).", {"bottleneck_pressure": peak}))

        # COUNTERFLOW_EMERGED
        cf = g["counterflow_index"].to_numpy()
        for t0, t1 in runs(t, (cf > e.counterflow_threshold) & occupied, e.min_duration_s, w):
            peak = float(cf[(t >= t0) & (t <= t1)].max())
            out.append(RawEvent(t0, t1, z, "COUNTERFLOW_EMERGED", self._sev(states, t0),
                                f"Counterflow emerged in {self.nar.zone_name(z)}",
                                f"Opposing movement developed in {name} (counterflow up to {peak:.2f}).",
                                {"counterflow_index": peak}))

        # INSTABILITY_RISING
        fi = g["flow_instability"].to_numpy()
        fi_slope = rolling_slope(t, fi, 10.0)
        cond = (fi_slope > 0) & (fi > e.instability_norm_fraction * self.s.risk.norm["flow_instability"]) & occupied
        for t0, t1 in runs(t, cond, e.min_duration_s, w):
            peak = float(fi[(t >= t0) & (t <= t1)].max())
            out.append(RawEvent(t0, t1, z, "INSTABILITY_RISING", self._sev(states, t0),
                                f"Flow instability rising in {self.nar.zone_name(z)}",
                                f"Movement in {name} became increasingly irregular (instability {peak:.2f}).",
                                {"flow_instability": peak}))

        # RISK_STATE_CHANGE and DE_ESCALATION
        st = g["state"].tolist()
        for i in range(1, len(st)):
            if st[i] == st[i - 1]:
                continue
            ti = float(t[i])
            evid = {"ensemble_score": float(g["ensemble_score"].iloc[i]), "density": float(dens[i])}
            up = RISK_ORDER[st[i]] > RISK_ORDER[st[i - 1]]
            out.append(RawEvent(ti, None, z, "RISK_STATE_CHANGE", st[i],
                                f"{self.nar.zone_name(z)} risk {'rose' if up else 'fell'} to {st[i]}",
                                f"Modelled risk in {name} changed from {st[i - 1]} to {st[i]} at {fmt_clock(ti)}.",
                                evid))
            if RISK_ORDER[st[i - 1]] >= RISK_ORDER["HIGH"] and RISK_ORDER[st[i]] <= RISK_ORDER["MEDIUM"]:
                out.append(RawEvent(ti, None, z, "DE_ESCALATION", st[i],
                                    f"De-escalation in {self.nar.zone_name(z)}",
                                    f"Modelled risk in {name} dropped from {st[i - 1]} to {st[i]}.", evid))
        return out

    def _spillover(self, state_series: dict[str, pd.Series]) -> list[RawEvent]:
        """Neighbour of an already-HIGH zone becomes HIGH within ``spillover_window_s``."""
        became_high: dict[str, float] = {}
        for z, s in state_series.items():
            hi = s[s.map(lambda x: RISK_ORDER[x] >= RISK_ORDER["HIGH"])]
            if len(hi):
                became_high[z] = float(hi.index[0])
        out = []
        for z, tz in became_high.items():
            srcs = [(n, tn) for n, tn in became_high.items() if n in self.g.neighbours(z)
                    and tn < tz and tz - tn <= self.e.spillover_window_s]
            if srcs:
                n, tn = min(srcs, key=lambda x: x[1])
                out.append(RawEvent(tz, None, z, "SPILLOVER", "HIGH",
                                    f"Risk spilled over from {self.nar.zone_name(n)} to {self.nar.zone_name(z)}",
                                    f"{self.nar.zone_name(z)} reached HIGH {tz - tn:.0f} s after neighbouring "
                                    f"{self.nar.zone_name(n)}.", {"lag_s": tz - tn}, ref=n))
        return out

    def _peak(self, global_df: pd.DataFrame, state_series: dict[str, pd.Series]) -> list[RawEvent]:
        if global_df.empty:
            return []
        i = int(global_df["max_score"].to_numpy().argmax())
        row = global_df.iloc[i]
        z, t = str(row["worst_zone"]), float(row["t"])
        sev = self._state_at(state_series.get(z, pd.Series(dtype=object)), t)
        if RISK_ORDER[sev] < RISK_ORDER["MEDIUM"]:
            return []
        return [RawEvent(t, None, z, "PEAK_RISK", sev, f"Peak modelled risk in {self.nar.zone_name(z)}",
                         f"The highest modelled risk ({float(row['max_score']):.2f}, {sev}) occurred in "
                         f"{self.nar.zone_label(z)} at {fmt_clock(t)}.", {"ensemble_score": float(row["max_score"])})]


def to_incident_events(raw: list[RawEvent]) -> tuple[list[IncidentEvent], dict[str, RawEvent]]:
    raw_sorted = sorted(raw, key=lambda e: (e.t_start, RISK_ORDER[e.severity], e.zone_id))
    events, by_id = [], {}
    for i, r in enumerate(raw_sorted, start=1):
        eid = f"ev_{i:03d}"
        by_id[eid] = r
        events.append(IncidentEvent(event_id=eid, t_start=r.t_start, t_end=r.t_end, zone_id=r.zone_id, type=r.type,
                                    severity=r.severity, title=r.title, detail=r.detail,
                                    evidence={k: float(v) for k, v in r.evidence.items()}, caused_by=[]))
    return events, by_id
