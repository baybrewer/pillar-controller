# 11 — Test Plan and Acceptance

This packet is only successful if it preserves current behavior first, then extends it safely.

## 1. Golden parity gate

Before any new runtime setup behavior is allowed to replace the old mapper:

> migrated default installation profile → new runtime packer == current hardcoded mapper output

That is the first hard gate.

## 2. Required automated tests

| Test file | Purpose |
|---|---|
| `test_installation_schema.py` | load, validate, migrate `installation.yaml` |
| `test_legacy_profile_seed.py` | default migration from current repo truth |
| `test_output_plan_compile.py` | offsets, swizzles, direction, validation |
| `test_runtime_mapper_parity.py` | new vs legacy output parity |
| `test_color_order_roundtrip.py` | permutation-derived swizzle correctness |
| `test_setup_api.py` | start/status/update/cancel/commit flows |
| `test_setup_session_restore.py` | restore live context on cancel |
| `test_effect_catalog.py` | rich catalog + scenes-list compatibility |
| `test_preview_api.py` | preview start/stop/status/websocket |
| `test_preview_isolation.py` | live and preview effect state separation |
| `test_audio_adapter_aliases.py` | `level→volume`, `mid→mids`, `high→highs` |
| `test_audio_band_shape.py` | 10-band view and normalization |
| `test_audio_snapshot_schema.py` | advanced musical-state adapter surface |
| `test_imported_effects.py` | imported effect render and parameter behavior |
| `test_rgb_order_detection.py` | ROI scoring + low-confidence fallback |
| `test_geometry_fit.py` | anchor-fit and dense-fallback math |
| `test_spatial_map_schema.py` | load/save/validation of `spatial_map.json` |
| `test_caps_semantics.py` | no confusion between `344` electrical and `172` physical |

## 3. Manual checks

### 3.1 Setup

- System > Setup is reachable
- strip count/order edits work without camera
- cancel restores the previous live scene
- commit hot-applies simple config changes safely

### 3.2 RGB wizard

- browser preview opens when secure context is available
- a strip can be retaken without rerunning all strips
- low-confidence strips remain manual-review items
- apply writes staged strip orders, not direct hardware edits

### 3.3 Geometry wizard

- anchor captures work with a fixed phone
- visible strips get solved
- hidden strips stay clearly marked as inferred/canonical
- validation overlay is understandable

### 3.4 Simulator

- Sim tab connects preview websocket
- preview effect differs from live LEDs
- leaving the tab stops the preview stream
- reconnect works

### 3.5 Imported effects

- batch B1 effects all render
- batch B2/B3 only ship once audio adapter tests pass
- imported effect descriptions appear in the UI

## 4. Acceptance criteria

| Area | Done when |
|---|---|
| legacy safety | untouched installs render exactly as before |
| strip config | per-strip enable/count/order are real runtime behavior |
| setup safety | setup cancel restores prior live context |
| RGB wizard | auto-detects or safely defers with manual override |
| geometry | stores honest front-projection geometry and documents limits |
| simulator | previews effect behavior without changing live LEDs |
| imported effects | 27 effects cataloged; ship by dependency batch |
| UI clarity | no critical single-letter mystery buttons remain |
| SSOT | no duplicated editable truths for controller, strip, or geometry state |

## 5. Commands

```bash
python -m compileall pi/app
PYTHONPATH=. pytest tests/ -q
```

If controller envelope changes:

```bash
python pi/scripts/generate_teensy_config.py
```

## 6. Release gate

Do not call the work complete until:

- parity gate passes
- all new tests pass
- current existing test suite still passes
- docs are updated to match runtime truth
