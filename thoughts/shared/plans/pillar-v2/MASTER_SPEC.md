# MASTER SPEC — Final Pillar Controller Expansion Packet

This is the one-file implementation brief for extending `pillar-controller` with setup-driven strip configuration, camera-assisted commissioning, imported simulator effects, and a web preview/simulator.

## 1. Executive summary

Keep the current macro architecture:

- Raspberry Pi owns API, renderer, media, audio, state, setup logic, and phone UI
- Teensy 4.1 owns USB packet ingestion and deterministic OctoWS2811 output
- logical pillar model remains `10 x 172`
- electrical output remains `5 x 344` channel-major bytes

Do not replace that architecture.

Instead, add:

1. a mutable installation config
2. a compiled runtime output plan
3. a non-destructive setup session system
4. a metadata-backed effect catalog
5. a dedicated preview transport
6. a real audio adapter for imported sound-reactive effects

## 2. Final decisions

| Topic | Final decision |
|---|---|
| Setup location | `System > Setup` |
| Mutable install truth | `installation.yaml` |
| Geometry truth | optional `spatial_map.json` front-projection profile |
| Hardware/controller envelope | `hardware.yaml` |
| Per-strip count and order | Pi-side compiled packer |
| DotStar | unsupported on current path |
| RGB wizard CV | browser still capture + backend analysis |
| Geometry solver | anchor-fit first, dense fallback only if needed |
| Simulator transport | dedicated preview websocket |
| Imported effects | 27 effects cataloged; ship by dependency batch |
| Legacy parity | mandatory first gate |

## 3. Repo truths that shape the design

### 3.1 Current runtime truths

| Topic | Current truth |
|---|---|
| live canvas | `10 x 172` |
| electrical packing | `5 x 344` active outputs |
| internal live render width | `40` by default |
| UI tabs | `Live`, `Effects`, `Media`, `Audio`, `Diag`, `System` |
| frontend | static HTML + vanilla JS |
| state websocket | `/ws`, JSON-only |
| scene list | `/api/scenes/list` returns name-keyed object |
| existing atomic-save pattern | `StateManager` |

### 3.2 Current contradictions to clean up

| Issue | Final action |
|---|---|
| stale GRB comments/fallbacks | normalize to current BGR live path |
| legacy mapper ignores config | replace with compiled runtime packer |
| diagnostics clear only resets Teensy pattern | use setup session snapshot/restore |
| hardcoded output shape in renderer | use compiled plan dimensions |
| imported-effect plan under-modeled in review docs | add audio adapter and batch gating |

### 3.3 Physical vs electrical semantics

Keep this distinction explicit:

- physical strip length = `172`
- electrical LEDs per active output = `344`

Never seed physical strip length from the electrical value.

## 4. Three hard truths

### 4.1 Secure context is required for browser camera setup

Do not assume iPhone/Safari camera capture works reliably on plain HTTP.

Keep manual setup fallback.

### 4.2 DotStar is not a drop-in choice

It is a different signaling family and is out of scope on the current OctoWS2811 path.

### 4.3 Single-camera geometry is front projection only

Use it honestly for overlays, preview alignment, and geometry-aware effects.
Do not claim full cylindrical reconstruction.

## 5. Source-of-truth plan

### 5.1 File ownership

| File | Owns | Mutable in setup UI |
|---|---|---:|
| `hardware.yaml` | controller + hardware envelope | no |
| `installation.yaml` | actual installed strips | yes |
| `spatial_map.json` | optional front-projection solve | yes |
| `effects.yaml` | curated effect defaults | indirect |
| `state.json` | runtime state and presets | yes |

### 5.2 Persist only real inputs

Persist:

- enabled
- logical_order
- output_channel
- output_slot
- direction
- installed_led_count
- color_order
- chipset
- geometry mode / spatial profile

Derive:

- protocol family
- output offsets
- swizzle tuples
- compiled channel plan
- preview coordinates
- status strings

## 6. Final config shapes

### 6.1 `hardware.yaml`

Use the current pillar geometry section and add an immutable controller block:

```yaml
controller:
  output_backend: octows2811
  signal_family: ws281x_800khz
  controller_wire_order: BGR
  active_outputs: 5
  total_outputs: 8
  electrical_leds_per_output: 344
  physical_leds_per_strip: 172
```

### 6.2 `installation.yaml`

```yaml
schema_version: 1
profile_name: default
geometry_mode: canonical_grid
spatial_profile_id: default
strips:
  - id: 0
    label: S0
    enabled: true
    logical_order: 0
    output_channel: 0
    output_slot: 0
    direction: bottom_to_top
    installed_led_count: 172
    color_order: BGR
    chipset: WS2812B
```

### 6.3 `spatial_map.json`

Store normalized front-projection UV coordinates per strip plus fit metadata.

## 7. Migration rule

If `installation.yaml` does not exist, synthesize it from current repo truth so the migrated profile reproduces current output exactly.

Seed:

- 10 strips
- channel pairs `[0,1] [2,3] [4,5] [6,7] [8,9]`
- directions from current even/odd layout
- `installed_led_count = 172`
- `color_order = BGR`
- controller wire order BGR

## 8. Runtime implementation call

### 8.1 Add a compiled runtime output plan

Use these runtime objects:

- `ControllerProfile`
- `CompiledStripPlan`
- `CompiledOutputPlan`

### 8.2 Replace handwritten color-order tables

Derive the precontroller swizzle by permutation simulation across controller order × strip-native order.

That same simulator is also used by the RGB-order wizard.

### 8.3 Keep wire semantics fixed

Per-strip variable lengths are compiled into padded channel-major bytes.

Do not create variable-length wire payloads.

## 9. Setup subsystem

### 9.1 Placement

Setup lives under `System`.

### 9.2 Required panels

| Panel | Purpose |
|---|---|
| Installation Summary | current install health |
| Strip Inventory | manual edits |
| RGB Order Wizard | camera-assisted order detection |
| Geometry Wizard | camera-assisted front-projection solve |
| Commit / Cancel | explicit apply or restore |

### 9.3 Setup session rules

Setup must:

- snapshot the prior live context
- stage edits separately from active installation
- drive temporary patterns through a setup-only pattern runner
- restore the snapshot on cancel
- persist only on commit

## 10. Setup routes

Add `pi/app/api/routes/setup.py` with at least:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/setup/installation` | active installation |
| `POST` | `/api/setup/session/start` | start session |
| `GET` | `/api/setup/session/status` | staged state |
| `PUT` | `/api/setup/session/installation` | staged edits |
| `POST` | `/api/setup/session/pattern` | setup pattern runner |
| `POST` | `/api/setup/session/cancel` | cancel + restore |
| `POST` | `/api/setup/session/commit` | persist + compile + hot-apply |
| `POST` | `/api/setup/rgb-order/analyze` | analyze strip capture set |
| `POST` | `/api/setup/geometry/analyze` | analyze capture batch |
| `POST` | `/api/setup/geometry/solve` | solve/validate map |
| `GET` | `/api/setup/spatial-map` | fetch map |
| `POST` | `/api/setup/spatial-map` | save map |

## 11. RGB-order wizard

### 11.1 Capture path

- browser shows live preview
- browser captures still frames for dark / red / green / blue
- browser uploads those frames to backend
- backend isolates ROI, scores channels, infers candidate order and confidence

### 11.2 Critical rule

Wizard patterns must bypass compiled color-order compensation.

### 11.3 Confidence gating

Auto-fill only when:

- ROI is bright and compact
- channel separation is strong
- one candidate order is clearly correct
- repeatability is acceptable

Otherwise defer to manual review.

## 12. Geometry wizard

### 12.1 Default strategy

Use anchor-fit first:

1. identify visible strips
2. light anchors at `0, 25, 50, 75, 100%`
3. fit centerline/polyline per strip
4. interpolate positions
5. validate with samples
6. dense-scan only failed strips

### 12.2 Storage truth

The saved map is a front-projection profile, not a replacement for canonical strip order.

### 12.3 Runtime usage

Immediate uses:

- preview alignment
- simulator overlay
- geometry-aware imported effects

Legacy effects stay canonical until explicitly upgraded.

## 13. Effect catalog and UI polish

### 13.1 Add metadata service

Add `pi/app/api/routes/effects.py` and a catalog service that merges:

- registry membership
- explicit metadata
- docstring fallback
- defaults from `effects.yaml`

### 13.2 Keep `/api/scenes/list` compatible

Do not break current frontend loading.
Add richer fields to the existing shape where safe.

### 13.3 Fix critical controls

Replace `B` / `R` with `Blackout` / `Resume`.
Add `data-tooltip` long-press help for mobile.

## 14. Imported effects

### 14.1 Inventory

The uploaded simulator defines 27 effects:

- 5 Classic
- 12 Ambient
- 10 Sound-reactive

### 14.2 Porting shape

Create repo-native effect modules and shared helpers.
Do not ship Pygame or desktop-only shell code.

### 14.3 Audio adapter

Required adapter surface:

- `volume`, `mids`, `highs`
- `bands`
- `beat_energy`
- `beat_count`, `bar_beat`, `phrase_beat`, `is_downbeat`, `is_phrase`, `beat_phase`
- `buildup`, `breakdown`, `drop`
- `time_s`

### 14.4 Batch gate

| Batch | Ship condition |
|---|---|
| B1 | helper + non-audio porting ready |
| B2 | advanced musical-state adapter ready |
| B3 | full band/phrase/beat-energy surface ready |

## 15. Simulator and preview

### 15.1 Transport choice

Use a dedicated preview websocket: `/api/preview/ws`.

Keep the current `/ws` JSON-only.

### 15.2 Preview rules

- preview effect instance is separate from live effect instance
- live LEDs continue to show the active scene
- simulator shows preview frames only
- preview auto-expires or stops explicitly

### 15.3 Frame format

Use a small header:

- message type
- frame id
- width
- height
- encoding
- raw RGB payload

## 16. Build safety checklist

Do not forget these repo-specific constraints:

- UI root is `pi/app/ui/static/index.html`
- `server.py` must mount new routers explicitly
- `AppDeps` must be extended in lockstep with new services
- `ws.create_router(deps)` currently returns `(router, broadcast_state)`
- current `/api/scenes/list` shape must remain compatible
- renderer hardcoded output arrays must be removed

## 17. Tests

Minimum required tests:

- legacy profile parity vs old mapper
- installation schema + migration
- swizzle roundtrip
- setup session restore
- preview/live isolation
- audio adapter aliases and band shape
- imported effect render tests
- RGB-order confidence logic
- geometry-fit validation
- physical vs electrical semantics guardrail

## 18. Acceptance criteria

| Area | Done when |
|---|---|
| legacy safety | untouched installs behave exactly as before |
| setup | manual setup works before camera features |
| RGB wizard | detects or safely defers with manual override |
| geometry | front-projection map is honest and usable |
| simulator | preview runs without changing live LEDs |
| imported effects | 27 effects cataloged and shipped by batch gates |
| UI clarity | no critical single-letter mystery controls remain |
| SSOT | no duplicated editable truth for controller, strip, or geometry state |

## 19. Required touchpoints

At minimum expect to touch:

- `pi/app/main.py`
- `pi/app/api/server.py`
- `pi/app/api/deps.py`
- `pi/app/api/schemas.py`
- `pi/app/api/routes/scenes.py`
- new `pi/app/api/routes/setup.py`
- new `pi/app/api/routes/effects.py`
- new `pi/app/api/routes/preview.py`
- `pi/app/core/renderer.py`
- `pi/app/core/state.py` or adjacent config helpers
- `pi/app/ui/static/index.html`
- `pi/app/ui/static/js/app.js`
- `pi/app/ui/static/css/app.css`
- `pi/app/mapping/cylinder.py`
- new runtime-plan and runtime-mapper modules
- `pi/scripts/generate_teensy_config.py`
- `teensy/firmware/include/config.h`
- `docs/current-contracts.md`
- `docs/MASTER_SPEC.md`

## 20. Recommended execution order

1. normalize truth and add immutable controller block
2. add installation config and migration
3. add compiled runtime packer and parity tests
4. add setup session service and manual setup UI
5. add catalog metadata and UI cleanup
6. add audio adapter foundation
7. add RGB-order wizard
8. add geometry wizard
9. port imported effects by batch
10. add simulator/preview transport
11. sync docs and run full test suite

That order gives the best chance of reaching a clean first-pass implementation without rework.
