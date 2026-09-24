"""Risk state machine with hysteresis, minimum dwell time and physical override rules."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from rewind.schemas.risk import RISK_ORDER, RISK_STATES, RiskState
from rewind.settings import RiskSettings


def level_for(score: float, thresholds: Sequence[float]) -> int:
    """Highest level whose threshold ≤ score (0 = LOW). ``thresholds`` = [medium, high, critical]."""
    lvl = 0
    for i, th in enumerate(thresholds, start=1):
        if score >= th:
            lvl = i
    return lvl


class RiskStateMachine:
    """Maps a score series to states without flicker.

    * Raising: the state rises to the level whose threshold the score has reached.
    * Lowering: a state is only lowered when the score falls below that level's threshold minus
      ``hysteresis``.
    * Dwell: a new level must be indicated continuously for ``min_dwell_s`` before the state changes
      (a debounce), so isolated spikes or dips do not flip the state.
    * Overrides: density ≥ ``density_levels.critical`` or crowd pressure ≥ ``crowd_pressure_turbulence``
      (the latter only when density ≥ ``density_levels.caution``) force at least HIGH.
    """

    def __init__(self, risk: RiskSettings) -> None:
        t = risk.thresholds
        self.thresholds = [t.medium, t.high, t.critical]
        self.h = risk.hysteresis
        self.dwell = risk.min_dwell_s
        self.dens_crit = risk.density_levels.critical
        self.turbulence = risk.crowd_pressure_turbulence
        self.dens_caution = risk.density_levels.caution

    def target_level(self, current: int, score: float, density: float = 0.0, crowd_pressure: float = 0.0) -> int:
        up = level_for(score, self.thresholds)
        down = level_for(score + self.h, self.thresholds)
        if up > current:
            cand = up
        elif down < current:
            cand = down
        else:
            cand = current
        # Crowd turbulence is only meaningful in dense crowds, so the pressure override requires at
        # least the caution density (sparse crowds have high velocity variance from individual paths).
        if density >= self.dens_crit or (crowd_pressure >= self.turbulence and density >= self.dens_caution):
            cand = max(cand, RISK_ORDER["HIGH"])
        return cand

    def run(self, times: Sequence[float] | np.ndarray, scores: Sequence[float] | np.ndarray,
            densities: Sequence[float] | np.ndarray | None = None,
            crowd_pressures: Sequence[float] | np.ndarray | None = None) -> list[RiskState]:
        n = len(scores)
        dens = np.zeros(n) if densities is None else np.asarray(densities, dtype=float)
        cps = np.zeros(n) if crowd_pressures is None else np.asarray(crowd_pressures, dtype=float)
        ts = np.asarray(times, dtype=float)
        window = float(np.median(np.diff(ts))) if n > 1 else 1.0
        out: list[RiskState] = []
        cur = 0
        pending_dir = 0  # +1 rising, -1 falling, 0 none
        pending_since = 0.0
        for i in range(n):
            t = float(ts[i])
            cand = self.target_level(cur, float(scores[i]), float(dens[i]), float(cps[i]))
            direction = int(np.sign(cand - cur))
            if direction == 0:
                pending_dir = 0
            else:
                if direction != pending_dir:
                    pending_dir, pending_since = direction, t
                if t - pending_since + window >= self.dwell - 1e-9:
                    cur = cand
                    pending_dir = 0
            out.append(RISK_STATES[cur])
        return out


def max_state(states: Sequence[str]) -> RiskState:
    if not states:
        return "LOW"
    return RISK_STATES[max(RISK_ORDER[s] for s in states)]
