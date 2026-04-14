# 01 — Repo Truth and Guardrails

This document captures the current repo assumptions that the implementation must respect.

## 1. Canonical repo touchpoints

| Area | Current canonical path |
|---|---|
| App entry | `pi/app/main.py` |
| App factory | `pi/app/api/server.py` |
| Dependency container | `pi/app/api/deps.py` |
| Pydantic models | `pi/app/api/schemas.py` |
| Current scene routes | `pi/app/api/routes/scenes.py` |
| Current diagnostics routes | `pi/app/api/routes/diagnostics.py` |
| Current state websocket | `pi/app/api/routes/ws.py` |
| Renderer | `pi/app/core/renderer.py` |
| Persistent state | `pi/app/core/state.py` |
| Legacy mapper | `pi/app/mapping/cylinder.py` |
| Hardware constants | `pi/app/hardware_constants.py` |
| Hardware config | `pi/config/hardware.yaml` |
| Effects defaults | `pi/config/effects.yaml` |
| UI HTML | `pi/app/ui/static/index.html` |
| UI JS | `pi/app/ui/static/js/app.js` |
| UI CSS | `pi/app/ui/static/css/app.css` |
| Teensy firmware | `teensy/firmware/src/main.cpp` |
| Teensy config | `teensy/firmware/include/config.h` |
| Teensy config generator | `pi/scripts/generate_teensy_config.py` |
| Contract docs | `docs/current-contracts.md`, `docs/MASTER_SPEC.md` |

## 2. Current runtime truths

| Topic | Current truth |
|---|---|
| Logical pillar canvas | `10 x 172` |
| Electrical packing | `5 x 344` active outputs |
| Internal live render width | `40` by default |
| Scene list source | `/api/scenes/list` |
| Frontend shell | static HTML + vanilla JS |
| Existing state websocket | `/ws` JSON state only |
| Diagnostics request model | `{{ pattern: str }}` only |
| Root UI path | `pi/app/ui/static/index.html` served by `/` |
| Atomic save pattern already exists | `StateManager` |

## 3. Current code-level contradictions

| Issue | What is true now | What must happen |
|---|---|---|
| Color-order docs drift | `hardware.yaml` says BGR; `hardware_constants.py` fallback still says GRB; `cylinder.py` comment still says GRB | normalize all stale comments, fallbacks, and docs to current live BGR path |
| Legacy mapper ignores config | `cylinder.py` hardcodes adjacent strip pairing and even/odd serpentine directions | move to compiled runtime output plan |
| Renderer hardcodes output shape | blackout/no-effect paths still allocate `(5, 344, 3)` directly | replace with compiled/meta-driven allocation |
| Diagnostics clear is incomplete | `clear` only clears Teensy test pattern and does not restore Pi scene | use a setup session service with snapshot/restore |
| Current `/ws` is tiny | only `ping` and `get_state` actions exist | keep it for state; do not overload it with preview/setup frames |
| Scene catalog is minimal | `/api/scenes/list` only returns `type` and `current` | add a catalog service and compatibility shim |

## 4. Current signatures you must preserve or update carefully

| Function | Current signature |
|---|---|
| `ws.create_router` | `create_router(deps) -> (router, broadcast_state)` |
| `scenes.create_router` | `create_router(deps, require_auth, broadcast_state)` |
| `diagnostics.create_router` | `create_router(deps, require_auth)` |
| `renderer.activate_scene` | `activate_scene(scene_name, params=None, media_manager=None)` |
| `StateManager` | atomic save via temp file + `os.replace` |
| `create_app` | accepts transport, renderer, render_state, state_manager, brightness_engine, media_manager, audio_analyzer, config |

## 5. Guardrails

### 5.1 Architecture guardrails

- Keep the Pi as the owner of setup logic, mapping, preview, media, audio, and UI.
- Keep the Teensy as a deterministic output appliance.
- Do not redesign the wire protocol into variable-length per-strip payloads.
- Do not move setup state, geometry logic, or per-strip protocol-family logic into firmware.

### 5.2 Config guardrails

- `hardware.yaml` stays the hardware/controller envelope and generator input.
- `installation.yaml` becomes the mutable setup/runtime truth.
- `spatial_map.json` stores the selected front-projection calibration result.
- Derived runtime plans are caches, not editable truth.

### 5.3 UI guardrails

- Setup lives under `System`, not as a new main tab.
- A new `Sim` tab is acceptable for preview.
- Critical controls cannot remain cryptic single-letter buttons.
- Keep the static frontend approach; do not add a heavyweight JS framework.

### 5.4 Import guardrails

- Do not embed the Pygame main loop from `led_sim.py`.
- Do not monkeypatch globals around the existing simulator file at runtime.
- Port effects cleanly into repo-native effect classes and helpers.

## 6. Hard do-not-do list

| Do not do this | Why |
|---|---|
| Write strip setup directly back into `hardware.yaml` on every edit | wrong SSOT boundary and risks codegen confusion |
| Treat DotStar as a supported enum on the current controller path | different signaling family |
| Use the existing `/ws` for preview video/frame traffic | breaks migration safety and couples unrelated concerns |
| Claim camera setup works reliably on plain HTTP | false on mobile browsers |
| Pretend a single fixed camera produces full 360° geometry | false |
| Trust the stale `GRB` fallback/comments over live runtime BGR behavior | creates wrong swizzle logic |
| Replace the existing `/api/scenes/list` without a compatibility plan | breaks current frontend immediately |

## 7. Minimal success definition

The implementation is only acceptable when:

- an untouched install behaves exactly like the current repo
- per-strip count/order/chipset setup is real runtime behavior
- setup cancel restores the previous live context
- RGB-order wizard either detects confidently or defers safely
- simulator preview runs without mutating live LED output
- imported effects are cataloged and ported according to their dependency gates
