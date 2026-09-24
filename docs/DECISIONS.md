# Decisions Log

Ambiguities resolved during the build: what was chosen and why.

| # | Date | Decision | Rationale |
|---|---|---|---|
| D1 | 2026-09-24 | REWIND lives in its own git repo at `C:\Users\sagni\Rewind` (branch `main`). | The parent home directory is a git repo with unrelated staged files. Phase commits must not land there. |
| D2 | 2026-09-24 | The Makefile stays canonical, and `scripts/dev.ps1` mirrors its targets. | `make` is not installed on the Windows dev machine. It is available in Docker, CI and WSL. |
| D3 | 2026-09-24 | A minimal synthetic video renderer is built in Phase 3, not only in Phase 12. | Perception acceptance needs a 30 s clip, and no licensed real footage is bundled. |
| D4 | 2026-09-24 | The crowd-pressure turbulence threshold (0.02 s⁻²), specific flow (1.3 p/m/s) and social-force parameters (A, B, k, κ, τ, v0) are literature-derived defaults (Helbing et al. 2000, 2007; Weidmann). | Phase 10 calibrates them per venue. |
