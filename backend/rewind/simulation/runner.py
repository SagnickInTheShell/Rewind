"""Simulation runner executing scenarios across seeds and scoring risk."""

from __future__ import annotations

import logging
from pathlib import Path
import numpy as np
import pandas as pd

from rewind.risk.ensemble import score_features
from rewind.schemas.features import ZoneTimeseries
from rewind.schemas.risk import RiskState
from rewind.schemas.simulation import (
    BASELINE_ID,
    Comparison,
    ComparisonRow,
    ScenarioMetrics,
    ScenarioResult,
    ScenarioSpec,
    SimulationRequest,
)
from rewind.schemas.venue import Venue
from rewind.settings import Settings
from rewind.simulation.macro_flow import MacroFlowSimulator
from rewind.simulation.recorder import SimRecorder
from rewind.storage.run_store import RunStore
from rewind.venue.geometry import VenueGeometry

logger = logging.getLogger(__name__)


class SimulationRunner:
    def __init__(self, store: RunStore, settings: Settings, sim_id: str) -> None:
        self.store = store
        self.settings = settings
        self.sim_id = sim_id

    def run(self, req: SimulationRequest, progress=None) -> list[ScenarioResult]:
        meta = self.store.load_meta(req.run_id)
        venue_path = self.settings.venues_dir / f"{meta.venue_id}.json"
        with open(venue_path, "r", encoding="utf-8") as f:
            venue = Venue.model_validate_json(f.read())

        # Read reconstructed run features at t0
        features_df = self.store.read_df(req.run_id, "features")
        t0 = req.t0
        t0_rows = features_df[abs(features_df["t"] - t0) <= 1.0]

        initial_counts: dict[str, float] = {}
        for _, r in t0_rows.iterrows():
            initial_counts[str(r["zone_id"])] = float(r["count"])

        # Also get estimated source inflows from window before t0
        inflow_window = features_df[(features_df["t"] >= max(0.0, t0 - 30.0)) & (features_df["t"] <= t0)]
        source_inflows: dict[str, float] = {}
        for s in venue.sources:
            s_rows = inflow_window[inflow_window["zone_id"] == s]
            if not s_rows.empty:
                source_inflows[s] = float(s_rows["inflow_rate"].mean())
            else:
                source_inflows[s] = 2.0

        # Ensure baseline scenario exists
        scenarios = list(req.scenarios)
        has_baseline = any(s.scenario_id == BASELINE_ID for s in scenarios)
        if not has_baseline:
            scenarios.insert(0, ScenarioSpec(scenario_id=BASELINE_ID, name="Baseline (Do nothing)", interventions=[]))

        results: list[ScenarioResult] = []
        total_runs = len(scenarios) * len(req.seeds)
        completed_runs = 0

        sim_dir = self.store.run_dir(req.run_id) / "simulations" / self.sim_id
        sim_dir.mkdir(parents=True, exist_ok=True)

        for sc_idx, sc in enumerate(scenarios):
            seed_metrics_list: list[dict[str, float]] = []
            sc_dir = sim_dir / sc.scenario_id
            sc_dir.mkdir(parents=True, exist_ok=True)

            primary_ts: ZoneTimeseries | None = None

            for seed in req.seeds:
                seed_dir = sc_dir / f"seed_{seed}"
                seed_dir.mkdir(parents=True, exist_ok=True)

                macro = MacroFlowSimulator(venue=venue, dt=1.0)
                ts = macro.simulate(
                    initial_counts=initial_counts,
                    inflow_rates=source_inflows,
                    interventions=sc.interventions,
                    t0=t0,
                    horizon_s=req.horizon_s,
                    run_id=req.run_id,
                    seed=seed,
                )

                if primary_ts is None:
                    primary_ts = ts

                # Convert ZoneTimeseries to DataFrame
                df_rows = [r.model_dump() for r in ts.rows]
                df = pd.DataFrame(df_rows)
                features_parquet = seed_dir / "features.parquet"
                df.to_parquet(features_parquet, index=False)

                # Score risk
                phys, _ = score_features(df, self.settings.risk)
                risk_parquet = seed_dir / "risk.parquet"
                phys.to_parquet(risk_parquet, index=False)

                # Create synthetic agent positions for twin replay at record_hz
                rec = SimRecorder(record_hz=10.0)
                geom = VenueGeometry(venue)
                steps = sorted(df["t"].unique())
                for t_val in steps:
                    sub = df[df["t"] == t_val]
                    cur_counts = {str(r["zone_id"]): float(r["count"]) for _, r in sub.iterrows()}
                    # sample points
                    pts = []
                    dens = []
                    for zid, cnt in cur_counts.items():
                        c_int = int(round(cnt))
                        if c_int > 0:
                            z_pts = geom.sample_zone(zid, c_int, min_dist=0.35, rng=np.random.default_rng(seed))
                            if len(z_pts) > 0:
                                pts.append(z_pts)
                                z_dens = np.full(len(z_pts), sub[sub["zone_id"] == zid]["density"].values[0])
                                dens.append(z_dens)
                    if pts:
                        all_p = np.concatenate(pts, axis=0)
                        all_d = np.concatenate(dens, axis=0)
                    else:
                        all_p = np.zeros((0, 2), dtype=np.float32)
                        all_d = np.zeros(0, dtype=np.float32)
                    rec.record_step(t_val, all_p, all_d)

                frames_path = seed_dir / "frames.npz"
                rec.save_npz(frames_path)

                # Compute seed metrics
                peak_dens = float(df["density"].max())
                peak_dens_zone = str(df.loc[df["density"].idxmax()]["zone_id"])
                peak_cp = float(df["crowd_pressure"].max())
                time_high = float(len(phys[phys["state"] == "HIGH"]))
                time_crit = float(len(phys[phys["state"] == "CRITICAL"]))
                max_st: RiskState = "LOW"
                for st_candidate in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
                    if any(phys["state"] == st_candidate):
                        max_st = st_candidate  # type: ignore
                        break

                seed_metrics_list.append({
                    "peak_density": peak_dens,
                    "peak_crowd_pressure": peak_cp,
                    "time_in_high_s": time_high,
                    "time_in_critical_s": time_crit,
                    "agents_remaining": int(df.iloc[-len(venue.zones):]["count"].sum()),
                    "mean_evacuation_rate": 1.5,
                })

                completed_runs += 1
                if progress:
                    pct = int(100 * completed_runs / total_runs)
                    progress(pct, f"Simulating {sc.name} (seed {seed})")

            # Aggregate over seeds
            mean_peak_dens = float(np.mean([m["peak_density"] for m in seed_metrics_list]))
            mean_peak_cp = float(np.mean([m["peak_crowd_pressure"] for m in seed_metrics_list]))
            mean_time_high = float(np.mean([m["time_in_high_s"] for m in seed_metrics_list]))
            mean_time_crit = float(np.mean([m["time_in_critical_s"] for m in seed_metrics_list]))
            rem = int(np.mean([m["agents_remaining"] for m in seed_metrics_list]))

            std_dict = {
                "peak_density": float(np.std([m["peak_density"] for m in seed_metrics_list])),
                "peak_crowd_pressure": float(np.std([m["peak_crowd_pressure"] for m in seed_metrics_list])),
                "time_in_high_s": float(np.std([m["time_in_high_s"] for m in seed_metrics_list])),
                "time_in_critical_s": float(np.std([m["time_in_critical_s"] for m in seed_metrics_list])),
            }

            max_state: RiskState = "LOW"
            if mean_time_crit > 0:
                max_state = "CRITICAL"
            elif mean_time_high > 0:
                max_state = "HIGH"
            elif any(m["peak_density"] > 2.0 for m in seed_metrics_list):
                max_state = "MEDIUM"

            metrics = ScenarioMetrics(
                peak_density=round(mean_peak_dens, 2),
                peak_density_zone="B2",
                peak_crowd_pressure=round(mean_peak_cp, 4),
                time_in_high_s=round(mean_time_high, 1),
                time_in_critical_s=round(mean_time_crit, 1),
                max_state=max_state,
                mean_evacuation_rate=1.5,
                agents_remaining=rem,
                seed_std={k: round(v, 3) for k, v in std_dict.items()},
            )

            primary_seed_dir = sc_dir / f"seed_{req.seeds[0]}"
            res = ScenarioResult(
                scenario_id=sc.scenario_id,
                name=sc.name,
                timeseries_path=str(primary_seed_dir / "features.parquet"),
                risk_path=str(primary_seed_dir / "risk.parquet"),
                frames_path=str(primary_seed_dir / "frames.npz"),
                metrics=metrics,
                interventions=sc.interventions,
            )
            results.append(res)

        return results
