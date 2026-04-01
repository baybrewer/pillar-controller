# Remediation R2 — Overview

External code review identified 23 issues across P0/P1/P2 severity levels.
This pass addresses all of them with a focus on transport correctness first,
then SSOT enforcement, then everything else.

## Execution order

1. Fix Teensy COBS encoder/decoder (P0-01, P0-02) — nothing works without this
2. Fix stats sequencing (P0-03) and test-pattern exit (P0-04)
3. Establish hardware SSOT + generated constants (P0-05)
4. Fix serial transport concurrency (P1-01)
5. Fix FPS measurement (P1-02) and render metrics
6. Fix Fire overflow (P1-06)
7. Unify scene activation (P1-07)
8. Fix config precedence (P1-08) and wire effects.yaml (P1-09)
9. Fix media pipeline (P1-03, P1-04) — async offload + correct timing
10. Optimize slow effects (P1-05) — vectorize hot paths
11. Fix firmware issues (P1-11 through P1-14)
12. Fix deployment consistency (P0-07), hotspot provisioning (P0-06)
13. Fix UI/API contract (P1-10)
14. P2 cleanup (models, dead code, docs)

## Key decisions

- COBS: Replace both Teensy encoder/decoder with standard algorithm. Add
  golden-vector cross-language tests.
- Stats: Teensy sends STATS only on PING (not PONG+STATS). Simpler contract.
- Test patterns: Clear on any FRAME or explicit CLEAR_TEST command.
- Hardware SSOT: Python `hardware_constants.py` generated from `hardware.yaml`
  at import time. Teensy constants stay in `config.h` (validated by tests).
- Serial transport: Use asyncio Lock around all serial I/O. Full async
  thread offload is deferred to v2 (diminishing returns for ~5KB frames).
- Effects: Vectorize Plasma, NoiseWash, CylinderRotate, RainbowRotate
  using numpy. Fire gets channel clamping.
- Scene activation: Single `activate_scene()` method handles all types.
- Config: Strict precedence: code defaults < yaml config < persisted state < live API.
- Deployment: Single model — editable install from repo, deployed via rsync+pip.
- Hotspot: Script creates NM profile from config. Not an app-managed feature.
