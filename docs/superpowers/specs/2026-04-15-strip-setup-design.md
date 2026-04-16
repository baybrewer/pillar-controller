# Strip Setup — Live Channel Config

## Goal

Replace the session-based setup system with a live channel configuration UI. Each of the 8 OctoWS2811 channels gets a color order and LED count setting. Changes apply immediately — no sessions, no commit workflow.

## Current State

- Setup is session-based: start session → snapshot live context → stage edits → validate → compile → commit → restore context
- `SetupSessionService` manages the lifecycle with deep-copy, snapshot/restore, and pattern testing
- `installation.yaml` is strip-oriented (10 strips with per-strip config: direction, logical_order, output_channel, output_slot, etc.)
- Setup routes in `pi/app/api/routes/setup.py` expose session start/cancel/commit and pattern endpoints
- `compile_output_plan()` bridges installation + controller profile → frozen runtime plan
- Color order swizzle logic in `runtime_plan.py` handles per-strip color order vs controller wire order

## Design

### UI (Setup Tab)

A table of 8 channels (0–7). Each row has:
- **Channel** — label (0–7), non-editable
- **Color Order** — dropdown: RGB, RBG, GRB, GBR, BRG, BGR
- **LED Count** — number input, 0–1100 (0 = unused/disabled)

No start/commit buttons. Each change fires immediately via POST. A brief status indicator ("Saved" / "Error") confirms.

### API

Two endpoints replace the entire session-based setup:

**`GET /api/setup/channels`**
Returns current config for all 8 channels:
```json
{
  "channels": [
    {"channel": 0, "color_order": "BGR", "led_count": 344},
    {"channel": 1, "color_order": "BGR", "led_count": 344},
    ...
    {"channel": 7, "color_order": "BGR", "led_count": 0}
  ]
}
```

**`POST /api/setup/channels/{n}`** (auth required)
Update a single channel:
```json
{"color_order": "GRB", "led_count": 300}
```

Response: `{"status": "ok", "channels": [...all 8...]}` (returns full state for UI sync)

Validation:
- `n` must be 0–7
- `color_order` must be one of: RGB, RBG, GRB, GBR, BRG, BGR
- `led_count` must be 0–1100 (integer)
- On validation failure: 422 with error message

### Backend Flow

On each POST:
1. Validate input
2. Update the in-memory channel config
3. Recompile output plan (`compile_output_plan`)
4. Hot-apply plan to renderer
5. Persist to `installation.yaml`
6. Return updated full config

### Data Model

`installation.yaml` becomes channel-oriented:

```yaml
schema_version: 2
channels:
  - channel: 0
    color_order: BGR
    led_count: 344
  - channel: 1
    color_order: BGR
    led_count: 344
  - channel: 2
    color_order: BGR
    led_count: 344
  - channel: 3
    color_order: BGR
    led_count: 344
  - channel: 4
    color_order: BGR
    led_count: 344
  - channel: 5
    color_order: BGR
    led_count: 0
  - channel: 6
    color_order: BGR
    led_count: 0
  - channel: 7
    color_order: BGR
    led_count: 0
```

Migration: if an existing strip-oriented `installation.yaml` (schema_version 1 or missing) is found, synthesize the channel config from the strip data. If no file exists, synthesize defaults from `hardware.yaml` (5 active channels at 344 LEDs each, BGR, rest at 0).

### What Gets Removed

- `SetupSessionService` class and module (`pi/app/setup/session.py`)
- Session-based routes (start, cancel, commit, status, pattern, staged installation)
- Wizard stub endpoints (rgb-order/analyze, geometry/analyze, geometry/solve)
- `SetupSessionService` instantiation in `main.py`

### What Stays

- `hardware.yaml` — immutable controller envelope (unchanged)
- `hardware_constants.py` — Python SSOT for geometry (unchanged)
- `compile_output_plan()` — recompile on each channel change
- `runtime_plan.py` — color order swizzle logic (unchanged)
- `cylinder.py` — mapping (unchanged)
- Spatial map endpoints can stay if used elsewhere, or be removed if not

### Files Changed

- `pi/app/api/routes/setup.py` — rewrite: two endpoints (GET channels, POST channel)
- `pi/app/api/schemas.py` — add `ChannelConfigRequest` model
- `pi/app/config/installation.py` — simplify to channel-oriented model, add migration
- `pi/app/main.py` — remove SetupSessionService instantiation, simplify init
- `pi/app/ui/static/index.html` — replace setup tab content
- `pi/app/ui/static/js/app.js` — replace setup tab JS
- `pi/app/ui/static/css/app.css` — add channel config table styles

### Files Removed

- `pi/app/setup/session.py` — session service no longer needed

## Not In Scope

- LED mapping / pixel coordinates (separate project)
- Test patterns (removed with session system, can be re-added later)
- Strip-level config (direction, logical order, etc.) — channels only for now
- Per-strip color order within a channel (all LEDs on a channel share one color order)
