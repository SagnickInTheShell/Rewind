"""A lightweight scripted crowd for the demo venue (used before/without the full simulator).

Agents enter through Gate A following an inflow profile, walk towards Gate B, repel each other and
the walls, and leave through Gate B. After ``counterflow_start`` a fraction of agents in the middle
row turn around, creating opposing movement. This produces an escalation pattern (surge → density
rise at B2/C2 → bottleneck at Gate B → counterflow) for end-to-end testing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from rewind.schemas.venue import Venue
from rewind.synthetic.render import Snapshot
from rewind.venue.geometry import wall_segments


def default_inflow(t: float) -> float:
    """People per second entering through Gate A."""
    if t < 20:
        return 1.2
    if t < 110:
        return 4.2
    if t < 140:
        return 2.0
    return 0.6


@dataclass
class ScriptedConfig:
    duration_s: float = 180.0
    dt: float = 0.04
    inflow: Callable[[float], float] = default_inflow
    counterflow_start: float = 65.0
    counterflow_end: float = 115.0
    counterflow_rate: float = 0.35  # agents per second turning around
    v0_mean: float = 1.3
    v0_std: float = 0.2
    tau: float = 0.5
    radius: tuple[float, float] = (0.22, 0.28)
    seed: int = 0


class ScriptedCrowd:
    def __init__(self, venue: Venue, cfg: ScriptedConfig) -> None:
        self.v = venue
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.pos = np.zeros((0, 2))
        self.vel = np.zeros((0, 2))
        self.v0 = np.zeros(0)
        self.rad = np.zeros(0)
        self.ids = np.zeros(0, dtype=np.int64)
        self.counter = np.zeros(0, dtype=bool)
        self.next_id = 0
        self._spawn_acc = 0.0
        self._cf_acc = 0.0
        self.walls = wall_segments(venue)
        a = venue.portal("GATE_A").segment
        b = venue.portal("GATE_B").segment
        self.gate_a = (np.array([a[0].x, a[0].y]), np.array([a[1].x, a[1].y]))
        self.gate_b = (np.array([b[0].x, b[0].y]), np.array([b[1].x, b[1].y]))
        self.t = 0.0

    def _spawn(self, n: int) -> None:
        a0, a1 = self.gate_a
        f = self.rng.uniform(0.1, 0.9, n)
        p = a0 + (a1 - a0) * f[:, None] + np.array([0.0, 0.35])
        p[:, 1] += self.rng.uniform(0, 0.2, n)
        self.pos = np.vstack([self.pos, p])
        self.vel = np.vstack([self.vel, np.tile([0.0, 1.0], (n, 1))])
        self.v0 = np.concatenate([self.v0, np.clip(self.rng.normal(self.cfg.v0_mean, self.cfg.v0_std, n), 0.6, 2.0)])
        self.rad = np.concatenate([self.rad, self.rng.uniform(*self.cfg.radius, n)])
        self.ids = np.concatenate([self.ids, np.arange(self.next_id, self.next_id + n)])
        self.counter = np.concatenate([self.counter, np.zeros(n, dtype=bool)])
        self.next_id += n

    def _targets(self) -> np.ndarray:
        b0, b1 = self.gate_b
        mid_b = (b0 + b1) / 2
        a0, a1 = self.gate_a
        mid_a = (a0 + a1) / 2
        tgt = np.tile(mid_b + [0.0, 1.0], (len(self.pos), 1))
        # funnel: aim at the nearest point of the gate opening (shrunk by a margin)
        x = np.clip(self.pos[:, 0], min(b0[0], b1[0]) + 0.4, max(b0[0], b1[0]) - 0.4)
        near_gate = self.pos[:, 1] > 16.0
        tgt[near_gate, 0] = x[near_gate]
        tgt[self.counter] = mid_a - [0.0, 1.0]
        return tgt

    def _wall_force(self) -> np.ndarray:
        f = np.zeros_like(self.pos)
        for ax, ay, bx, by in self.walls:
            a = np.array([ax, ay])
            ab = np.array([bx - ax, by - ay])
            L2 = float(ab @ ab)
            tt = np.clip(((self.pos - a) @ ab) / max(L2, 1e-9), 0, 1)
            q = a + tt[:, None] * ab
            d = self.pos - q
            dist = np.linalg.norm(d, axis=1)
            n = d / np.maximum(dist, 1e-6)[:, None]
            overlap = self.rad - dist
            f += (2000.0 * np.exp(overlap / 0.08) + 120000.0 * np.maximum(overlap, 0))[:, None] * n
        return f

    def _agent_force(self) -> np.ndarray:
        f = np.zeros_like(self.pos)
        if len(self.pos) < 2:
            return f
        tree = cKDTree(self.pos)
        pairs = tree.query_pairs(1.2, output_type="ndarray")
        if len(pairs) == 0:
            return f
        i, j = pairs[:, 0], pairs[:, 1]
        d = self.pos[i] - self.pos[j]
        dist = np.maximum(np.linalg.norm(d, axis=1), 1e-6)
        n = d / dist[:, None]
        rij = self.rad[i] + self.rad[j]
        overlap = rij - dist
        mag = 2000.0 * np.exp(overlap / 0.08) + 120000.0 * np.maximum(overlap, 0)
        fij = mag[:, None] * n
        np.add.at(f, i, fij)
        np.add.at(f, j, -fij)
        return f

    def step(self) -> None:
        c = self.cfg
        dt = c.dt
        self._spawn_acc += c.inflow(self.t) * dt
        n_new = int(self._spawn_acc)
        if n_new:
            self._spawn_acc -= n_new
            self._spawn(n_new)
        if c.counterflow_start <= self.t < c.counterflow_end and len(self.pos):
            self._cf_acc += c.counterflow_rate * dt
            k = int(self._cf_acc)
            if k:
                self._cf_acc -= k
                cand = np.flatnonzero(~self.counter & (self.pos[:, 1] > 8.0) & (self.pos[:, 1] < 15.0)
                                      & (np.abs(self.pos[:, 0] - 15.0) < 6.0))
                if len(cand):
                    self.counter[self.rng.choice(cand, size=min(k, len(cand)), replace=False)] = True
        if len(self.pos):
            e = self._targets() - self.pos
            e /= np.maximum(np.linalg.norm(e, axis=1), 1e-6)[:, None]
            drive = (self.v0[:, None] * e - self.vel) / c.tau
            acc = drive + (self._agent_force() + self._wall_force()) / 80.0
            acc += self.rng.normal(0, 0.3, acc.shape)
            self.vel += acc * dt
            sp = np.linalg.norm(self.vel, axis=1)
            cap = 1.3 * self.v0
            over = sp > cap
            self.vel[over] *= (cap[over] / sp[over])[:, None]
            self.pos += self.vel * dt
            # leave through Gate B (south) or Gate A (counterflow agents, north)
            gone = (self.pos[:, 1] > 20.3) | (self.counter & (self.pos[:, 1] < -0.3))
            gone |= (self.pos[:, 0] < -1) | (self.pos[:, 0] > 31) | (self.pos[:, 1] < -1)
            if gone.any():
                keep = ~gone
                self.pos, self.vel, self.v0 = self.pos[keep], self.vel[keep], self.v0[keep]
                self.rad, self.ids, self.counter = self.rad[keep], self.ids[keep], self.counter[keep]
        self.t += dt

    def run(self, fps: float) -> Iterator[Snapshot]:
        frame_dt = 1.0 / fps
        next_frame = 0.0
        while self.t <= self.cfg.duration_s + 1e-9:
            if self.t + 1e-9 >= next_frame:
                yield Snapshot(t=round(next_frame, 4), ids=self.ids.copy(), xy=self.pos.copy(), radius=self.rad.copy())
                next_frame += frame_dt
            self.step()
