# Decisions Log

Ambiguities resolved during the build: what was chosen and why.

| # | Date | Decision | Rationale |
|---|---|---|---|
| D1 | 2026-09-24 | REWIND lives in its own git repo at `C:\Users\sagni\Rewind` (branch `main`). | The parent home directory is a git repo with unrelated staged files. Phase commits must not land there. |
| D2 | 2026-09-24 | The Makefile stays canonical, and `scripts/dev.ps1` mirrors its targets. | `make` is not installed on the Windows dev machine. It is available in Docker, CI and WSL. |
| D3 | 2026-09-24 | A minimal synthetic video renderer is built in Phase 3, not only in Phase 12. | Perception acceptance needs a 30 s clip, and no licensed real footage is bundled. |
| D5 | 2026-09-24 | Additive contract fields: `VideoMeta.synthetic`; `ScenarioResult.name` and `interventions`; `ValidationReport` UI context (`calibration_window`, `validation_window`, `worst_zone`, observed/simulated series); `RiskSeries` wrapper (`zones`, `global_risk`, `methods`). | The UI must label synthetic footage, name scenarios, and plot validation without extra round trips. No Section 5 field was removed or renamed. |
| D6 | 2026-09-24 | Strategy contracts (`Recommendation`, `PreventionPlan`) live in `schemas/validation.py`, alongside the shared `CAVEAT` string. | The Section 3 file list has no `schemas/strategy.py`, and the caveat is shared by both. |
| D4 | 2026-09-24 | The crowd-pressure turbulence threshold (0.02 s⁻²), specific flow (1.3 p/m/s) and social-force parameters (A, B, k, κ, τ, v0) are literature-derived defaults (Helbing et al. 2000, 2007; Weidmann). | Phase 10 calibrates them per venue. |
