# 15 — Opus Execution Prompt

You are working inside the `pillar-controller` repo.

Read these files in order:

1. `MASTER_SPEC.md`
2. `01_REPO_TRUTH_AND_GUARDRAILS.md`
3. `02_SSOT_AND_CONFIGURATION.md`
4. `03_OUTPUT_COMPILER_AND_PROTOCOL.md`
5. `04_SETUP_SUBSYSTEM_AND_APIS.md`
6. `05_CAMERA_RGB_ORDER_WIZARD.md`
7. `06_CAMERA_GEOMETRY_WIZARD.md`
8. `07_EFFECT_CATALOG_AND_UI_POLISH.md`
9. `08_IMPORTED_ANIMATIONS_AND_AUDIO_ADAPTER.md`
10. `09_WEB_SIMULATOR_AND_PREVIEW.md`
11. `10_BUILD_SAFETY_CHECKLIST.md`
12. `11_TEST_PLAN_AND_ACCEPTANCE.md`
13. `12_IMPLEMENTATION_SEQUENCE.md`
14. `13_REVIEW_MERGE_DECISIONS.md`
15. `14_EFFECT_INVENTORY.md`

## Mission

Implement the setup, mapping, imported-effects, and preview architecture described in those files.

## Non-negotiable rules

1. Preserve current behavior first; pass the legacy parity gate before replacing the mapper.
2. Setup must live under `System`, not as a new top-level tab.
3. Use `installation.yaml` as mutable setup truth. Do not use runtime setup writes to `hardware.yaml`.
4. Normalize the current live path on BGR and remove stale GRB remnants.
5. Keep DotStar / APA102 unsupported on the current OctoWS2811 path.
6. Use a dedicated preview websocket. Do not overload the current `/ws`.
7. Live and preview must use separate effect instances.
8. Imported `led_sim.py` effects must be ported cleanly, not embedded wholesale.
9. Browser camera flow requires secure context; keep manual fallback.
10. Use a setup session with snapshot/restore semantics.
11. Keep the current `/api/scenes/list` working during migration or cut over atomically.
12. Keep the fixed channel-major wire contract. Variable strip counts are compiled to padded output.
13. Keep the current static frontend approach.
14. Run `python -m compileall pi/app` and `PYTHONPATH=. pytest tests/ -q` after each phase gate.

## Current repo truths you must respect

- UI HTML is at `pi/app/ui/static/index.html`.
- Current frontend JS is at `pi/app/ui/static/js/app.js`.
- `server.py` serves `/` from `static/index.html`.
- `ws.create_router(deps)` returns `(router, broadcast_state)`.
- `scenes.create_router(deps, require_auth, broadcast_state)` uses that broadcast callback.
- Current `/api/scenes/list` returns a name-keyed `effects` object plus `current`.
- Current `/ws` only handles JSON state actions like `ping` and `get_state`.
- Current diagnostics request model only accepts `pattern`.
- Current render blackout/no-effect paths still hardcode `(5, 344, 3)`.
- `config.h` distinguishes electrical `LEDS_PER_STRIP = 344` from physical `LEDS_PER_PHYSICAL = 172`.
- Current `led_sim.py` defines 27 import candidates, not 23.

## Required outputs

Produce and wire the following:

- `installation.yaml` schema + migration
- compiled output plan + runtime mapper
- setup session service + routes + UI
- RGB-order wizard with backend-scored still capture
- geometry wizard with anchor-fit-first solving
- catalog metadata service + `/api/scenes/list` compatibility
- imported-effect helper modules + metadata
- audio adapter sufficient for batch-gated sound effects
- dedicated preview service + `/api/preview/ws`
- Sim tab in the UI
- tests covering parity, setup restore, preview isolation, audio adapter, imported effects, and geometry/RGB wizard logic

## Implementation order

Use the phase order in `12_IMPLEMENTATION_SEQUENCE.md`.

Do not skip the parity gate.

## Definition of done

The work is done only when:

- untouched installs behave exactly like the current repo
- setup cancel restores the prior live context
- per-strip count/order edits are real runtime behavior
- current Effects tab still works
- simulator preview does not change live LEDs
- imported effects ship according to dependency batches
- compileall and the full test suite pass
