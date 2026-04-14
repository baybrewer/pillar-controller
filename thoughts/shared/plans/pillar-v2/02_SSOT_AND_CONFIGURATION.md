# 02 — SSOT and Configuration

This document defines the final configuration boundary.

## 1. File ownership model

| File | Owner | Mutable from setup UI? | Notes |
|---|---|---:|---|
| `pi/config/hardware.yaml` | hardware/controller envelope | No | generator input; mostly stable |
| `pi/config/installation.yaml` | actual installed strips and selected geometry profile | Yes | new mutable setup truth |
| `pi/config/spatial_map.json` | solved front-projection geometry | Yes | optional calibration output |
| `pi/config/effects.yaml` | curated defaults and ordering | Indirect | not direct per-session edit state |
| `pi/config/system.yaml` | appliance/runtime system config | Limited | existing behavior |
| `pi/config/state.json` | ephemeral runtime state, presets, brightness, fps | Yes | existing `StateManager` pattern |

## 2. Why `installation.yaml` exists

The review docs proposed setup-time writes back into `hardware.yaml`.

That is the wrong boundary for this repo because `hardware.yaml` is already tied to:

- generator-derived Teensy constants
- cross-language geometry validation
- current hardcoded mapper assumptions
- docs that treat it as hardware SSOT

A mutable installation file prevents setup workflows from colliding with firmware-envelope truth.

## 3. Final schemas

### 3.1 `hardware.yaml`

Keep the current pillar geometry envelope and add a controller block to remove color-order ambiguity.

```yaml
pillar:
  strips: 10
  leds_per_strip: 172
  total_leds: 1720
  channels:
    count: 5
    leds_per_channel: 344
    pairs:
      - channel: 0
        strips: [0, 1]
      - channel: 1
        strips: [2, 3]
      - channel: 2
        strips: [4, 5]
      - channel: 3
        strips: [6, 7]
      - channel: 4
        strips: [8, 9]
  wiring:
    even_strip_direction: bottom_to_top
    odd_strip_direction: top_to_bottom
    seam_position: [9, 0]

controller:
  output_backend: octows2811
  signal_family: ws281x_800khz
  controller_wire_order: BGR
  active_outputs: 5
  total_outputs: 8
  electrical_leds_per_output: 344
  physical_leds_per_strip: 172
```

Migration rule:

- if legacy `pillar.color_order` exists, migrate it into `controller.controller_wire_order`
- then remove or ignore the legacy field after normalization

### 3.2 `installation.yaml`

```yaml
schema_version: 1
profile_name: default
geometry_mode: canonical_grid   # canonical_grid | front_projection
spatial_profile_id: default     # used only when geometry_mode = front_projection
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
  - id: 1
    label: S1
    enabled: true
    logical_order: 1
    output_channel: 0
    output_slot: 1
    direction: top_to_bottom
    installed_led_count: 172
    color_order: BGR
    chipset: WS2812B
```

Persist only real input truths here.

Do **not** persist:

- `protocol_family`
- output offsets
- status strings
- compiled swizzles
- preview coordinates
- total active counts
- firmware flags

### 3.3 `spatial_map.json`

```json
{
  "schema_version": 1,
  "profile_id": "default",
  "coordinate_space": "front_projection_uv",
  "camera_resolution": [1280, 720],
  "visible_strips": [0, 1, 2, 3, 4, 5],
  "strips": [
    {
      "id": 0,
      "anchors": [[0.12, 0.98], [0.12, 0.74], [0.12, 0.50], [0.12, 0.25], [0.12, 0.02]],
      "positions": [[0.12, 0.99], [0.12, 0.985], "..."],
      "fit_method": "anchor_polyline_v1",
      "visibility": "direct"
    }
  ],
  "bounds": {
    "x_min": 0.0,
    "x_max": 1.0,
    "y_min": 0.0,
    "y_max": 1.0
  }
}
```

This file stores front-projection coordinates, not fake 360° geometry.

## 4. Derived runtime artifacts

| Artifact | Built from | Stored as |
|---|---|---|
| controller profile | `hardware.yaml` | immutable runtime object |
| installation model | `installation.yaml` | mutable runtime object |
| compiled output plan | hardware + installation | runtime cache |
| color swizzle lookup | controller profile + strip color orders | runtime cache |
| projection lookup | spatial map | runtime cache |

## 5. Migration behavior

### 5.1 First boot after upgrade

If `installation.yaml` does not exist:

1. load `hardware.yaml`
2. synthesize default strip rows from current repo truth
3. seed all strips with `installed_led_count = 172`
4. seed all strips with `color_order = BGR`
5. seed `output_channel` / `output_slot` from current adjacent-pair layout
6. write `installation.yaml` atomically

### 5.2 Legacy parity seed

Default migration must reproduce current output exactly.

That means the seeded installation profile must match:

- 10 strips
- 5 active outputs
- paired strips per channel
- current directions
- current controller wire order BGR
- current per-strip native order BGR

## 6. Validation rules

| Field | Validation |
|---|---|
| `installed_led_count` | `0 <= value <= controller.physical_leds_per_strip` |
| `color_order` | one of 6 RGB permutations |
| `chipset` | one-wire WS281x-compatible families only on current path |
| `output_channel` | `0 <= value < controller.active_outputs` |
| `output_slot` | `0` or `1` on current hardware |
| `logical_order` | unique per enabled strip |
| `geometry_mode` | `canonical_grid` or `front_projection` |

## 7. Write strategy

Reuse the existing `StateManager` atomic save pattern:

- validate full document
- write to temp file in config dir
- `os.replace` into place
- mark runtime compiler dirty
- hot-swap compiled runtime plan only after validation succeeds

## 8. Required code changes

| File | Change |
|---|---|
| `pi/app/main.py` | load `installation.yaml` and optional `spatial_map.json` |
| `pi/app/api/deps.py` | add setup/config/preview services |
| `pi/app/hardware_constants.py` | stop being the only mutable truth; expose controller profile helpers |
| new `pi/app/config/installation.py` | schema load/save/migrate helpers |
| new `pi/app/config/spatial_map.py` | load/save validation helpers |

## 9. Definition of done

- setup edits never mutate `hardware.yaml`
- fresh migration preserves legacy behavior
- installation writes are atomic
- controller-envelope truth is no longer ambiguous
- the runtime compiler consumes installation truth, not ad hoc globals
