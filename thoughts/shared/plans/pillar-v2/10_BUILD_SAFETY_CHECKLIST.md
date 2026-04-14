# 10 — Build Safety Checklist

Use this document to avoid the failure modes most likely on this repo.

## 1. Path and mounting checks

| Check | Why it matters |
|---|---|
| UI root file is `pi/app/ui/static/index.html` | not `pi/app/ui/index.html` |
| `server.py` serves `/` from `static/index.html` | wrong path will 404 the UI |
| static JS is `pi/app/ui/static/js/app.js` | current frontend is not bundled |

## 2. Router factory checks

| Router | Current shape |
|---|---|
| `ws.create_router(deps)` | returns `(router, broadcast_state)` |
| `scenes.create_router(deps, require_auth, broadcast_state)` | needs broadcast callback |
| `brightness.create_router(...)` | also expects broadcast callback |
| new `setup.create_router(...)` | should accept `broadcast_state` because commit/cancel changes UI state |
| new `preview.create_router(...)` | should own its own websocket and preview service |

## 3. Main-app wiring checks

Before coding new routes, update all of these together:

- `pi/app/api/deps.py`
- `pi/app/main.py`
- `pi/app/api/server.py`

If you only add the router module and forget `AppDeps` or `create_app`, the app will import-fail or silently miss features.

## 4. Current response-shape checks

| Endpoint | Current expectation |
|---|---|
| `/api/scenes/list` | returns `{"effects": {name: {type}}, "current": ...}` |
| `/ws` | JSON state updates only |
| `/api/diagnostics/test-pattern` | body only contains `pattern` |
| `RenderState.to_dict()` | currently minimal audio fields only |

Do not break the current frontend while introducing richer APIs.

## 5. Renderer checks

| Trap | Fix |
|---|---|
| hardcoded `(5, 344, 3)` blackout/no-effect arrays | use compiled plan dimensions |
| current logical height imported as `N` from legacy mapper | move to plan/controller profile |
| live and preview state sharing | use separate effect instances |

## 6. Color-order checks

| Trap | Fix |
|---|---|
| stale GRB comments in `hardware_constants.py` fallback | normalize to BGR live path |
| stale GRB comment in `cylinder.py` serializer | replace with controller-profile language |
| handwritten swizzle table drift | derive swizzle via permutation simulation |

## 7. Setup checks

| Trap | Fix |
|---|---|
| using diagnostics clear to “restore” setup | not enough; add snapshot/restore service |
| mutating `state_manager.current_scene` during wizard steps | keep setup session separate |
| persisting staged edits before user confirms | only save on commit |

## 8. Preview checks

| Trap | Fix |
|---|---|
| extending `/ws` for preview frames | use `/api/preview/ws` |
| preview mutates live scene | separate preview instances |
| canvas assumes wrong height/width | stream dimensions in preview frame header |

## 9. Imported-effects checks

| Trap | Fix |
|---|---|
| importing `led_sim.py` directly | port helpers and effects cleanly |
| requiring Pygame in production | no |
| shipping sound effects before audio adapter exists | gate by batch |

## 10. Commands to run after each phase

```bash
python -m compileall pi/app
PYTHONPATH=. pytest tests/ -q
```

After controller-envelope changes:

```bash
python pi/scripts/generate_teensy_config.py
```

After adding new config files or deployment assets:

- update deployment script or packaging to include them

## 11. Final smoke checklist

- UI loads from `/`
- existing tabs still work
- `/api/scenes/list` still populates the effects tab
- setup start/cancel does not leave a diagnostic scene active
- preview starts and stops without touching live LEDs
- legacy install still renders identical bytes
