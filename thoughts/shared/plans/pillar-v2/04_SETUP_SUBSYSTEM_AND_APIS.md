# 04 — Setup Subsystem and APIs

Setup must be a real subsystem, not a thin wrapper over current diagnostics.

## 1. UI placement

Setup lives under `System` as a sub-navigation section.

```text
System
├── Status
├── Setup
│   ├── Installation Summary
│   ├── Strip Inventory
│   ├── RGB Order Wizard
│   ├── Geometry Wizard
│   └── Commit / Cancel
├── Advanced
└── Admin
```

## 2. Setup design goals

- non-destructive until explicit commit
- session-scoped pattern control
- explicit restore of pre-setup live context
- installation edits available even without camera access
- no duplicated config truths

## 3. New backend services

| Service | Purpose |
|---|---|
| `InstallationManager` | load/save/migrate `installation.yaml` |
| `OutputPlanService` | compile installation + controller profile into runtime plan |
| `SetupSessionService` | snapshot live context, stage edits, drive patterns, restore/cancel |
| `EffectCatalogService` | metadata-backed effect listing |
| `PreviewService` | isolated preview instances and preview frame stream |
| `AudioCompatService` | imported-effect audio adapter surface |

These should be added to `AppDeps`.

## 4. Setup session model

```python
@dataclass
class SetupSnapshot:
    current_scene: str | None
    current_params: dict
    blackout: bool
    media_scene: str | None
```

```python
@dataclass
class SetupSession:
    session_id: str
    snapshot: SetupSnapshot
    staged_installation: InstallationConfig
    active_pattern: SetupPattern | None
    started_at: float
```

### Required behavior

| Action | Required result |
|---|---|
| start session | capture snapshot and clone installation into staged copy |
| modify strip row | update staged installation only |
| run wizard step | drive setup pattern without mutating persistent scene state |
| cancel | clear pattern, restore scene + blackout + media context |
| commit | validate, save installation, compile new plan, hot-swap runtime, restore live context |

## 5. Routes

### 5.1 `pi/app/api/routes/setup.py`

This router should follow the repo factory pattern:

```python
def create_router(deps, require_auth, broadcast_state) -> APIRouter:
    ...
```

### 5.2 Route surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/setup/installation` | return active installation config |
| `POST` | `/api/setup/session/start` | create setup session and snapshot live context |
| `GET` | `/api/setup/session/status` | get staged status and active step |
| `PUT` | `/api/setup/session/installation` | update staged strip rows |
| `POST` | `/api/setup/session/pattern` | run a session-scoped setup pattern |
| `POST` | `/api/setup/session/cancel` | cancel session and restore snapshot |
| `POST` | `/api/setup/session/commit` | validate, persist, compile, hot-apply |
| `GET` | `/api/setup/spatial-map` | return current spatial map if present |
| `POST` | `/api/setup/spatial-map` | save solved spatial map atomically |

Keep camera analysis routes on the same router for coherence:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/setup/rgb-order/analyze` | analyze one strip capture set |
| `POST` | `/api/setup/geometry/analyze` | analyze geometry capture batch |
| `POST` | `/api/setup/geometry/solve` | solve or validate front-projection fit |

## 6. Pattern runner

The current diagnostics API is too small because it only accepts `pattern`.

Create a setup-only pattern runner that can express:

- specific strip IDs
- specific output channels / slots
- all-others black
- identity vs compiled color-order behavior
- step timings
- settle timings
- single LED or full-strip fills

```python
class SetupPatternRequest(BaseModel):
    session_id: str
    mode: Literal["fill_strip", "fill_leds", "clear"]
    targets: list[TargetSpec]
    all_others: Literal["black"] = "black"
    use_compiled_color_order: bool = False
```

## 7. Schemas to add

| Schema | Purpose |
|---|---|
| `StripRowUpdate` | staged strip edits |
| `InstallationResponse` | active/staged installation payload |
| `SetupSessionStartResponse` | session token and snapshot summary |
| `SetupPatternRequest` | pattern runner |
| `SetupCommitResponse` | apply result, restart/firmware flags |
| `SpatialMapRequest` | save solved front-projection map |
| `RGBOrderAnalyzeRequest` | strip snapshots + metadata |
| `GeometryAnalyzeRequest` | capture frames + step metadata |

## 8. Hot-apply behavior

| Change type | Runtime behavior |
|---|---|
| color order only | compile and hot-swap plan |
| enabled flag only | compile and hot-swap plan |
| installed LED count decrease | compile and hot-swap plan |
| installed LED count increase beyond physical max | reject |
| controller-envelope change | admin-only; may require generator + firmware rebuild |

## 9. File touchpoints

| File | Change |
|---|---|
| `pi/app/api/deps.py` | add new services |
| `pi/app/api/server.py` | mount new routers |
| `pi/app/main.py` | instantiate config/setup/preview services |
| `pi/app/api/schemas.py` | new setup schemas |
| new `pi/app/setup/session.py` | session service |
| new `pi/app/setup/patterns.py` | pattern runner |

## 10. Done criteria

- setup can be used without camera features
- cancel always restores the prior live context
- commit only persists validated staged installation
- setup patterns never leave the app stuck in a diagnostic state
