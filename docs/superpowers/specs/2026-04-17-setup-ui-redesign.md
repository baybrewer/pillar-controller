# Setup UI Redesign: Geometry-First Flat Segments

## Goal

Replace the broken strip/line/card-based Setup UI with a flat segment table and SVG grid preview. Geometry comes first (where are the LEDs?), wiring is secondary (which output?). One concept: **segment**. Mobile responsive.

## Data Model Changes

### Before (current)
```yaml
strips:
  - id: 0
    output: 0
    output_offset: 0
    lines:
      - start: [0, 0]
        end: [0, 171]
        color_order: BGR
      - start: [1, 171]
        end: [1, 0]
        color_order: BGR
```

Strips contain lines. Lines are the segments. Strips group by some concept of physical strip. Output offset is per-strip.

### After (new)
```yaml
segments:
  - start: [0, 0]
    end: [0, 171]
    output: 0
    color_order: BGR

  - start: [1, 171]
    end: [1, 0]
    output: 0
    color_order: BGR

  - start: [2, 0]
    end: [2, 171]
    output: 1
    color_order: BGR
```

Flat list of segments. No strips, no nesting. Each segment defines its grid position and which output drives it. Output offset is auto-calculated: segments on the same output are ordered by their position in the list, and their offsets stack sequentially (first segment on output 0 starts at offset 0, second segment on output 0 starts at offset = first segment's LED count, etc.).

### pixel_map.yaml schema

```yaml
schema_version: 2
origin: bottom-left

teensy:
  outputs: 8
  max_leds_per_output: 1200
  controller_wire_order: BGR
  signal_family: ws281x_800khz
  octo_pins: [2, 14, 7, 8, 6, 20, 21, 5]

segments:
  - start: [0, 0]
    end: [0, 171]
    output: 0
    color_order: BGR

  - start: [1, 171]
    end: [1, 0]
    output: 0
    color_order: BGR

  - start: [2, 0]
    end: [2, 171]
    output: 1
    color_order: BGR
```

### SegmentConfig dataclass

```python
@dataclass
class SegmentConfig:
    start: tuple[int, int]   # (x, y) grid position of first LED
    end: tuple[int, int]     # (x, y) grid position of last LED
    output: int              # Teensy output pin (0-7)
    color_order: str = 'BGR'
```

Replaces `StripConfig` + `LineConfig`. `led_count()` and `positions()` methods stay (axis-aligned, inclusive endpoints).

### PixelMapConfig changes

```python
@dataclass
class PixelMapConfig:
    origin: str = "bottom-left"
    teensy_outputs: int = 8
    teensy_max_leds_per_output: int = 1200
    teensy_wire_order: str = "BGR"
    teensy_signal_family: str = "ws281x_800khz"
    teensy_octo_pins: list[int] = field(default_factory=...)
    segments: list[SegmentConfig] = field(default_factory=list)
    pixel_overrides: dict[str, tuple[int, int]] = field(default_factory=dict)
```

`pixel_overrides` moves from per-strip to top-level (keyed by `"output-ledindex"`).

### Output offset calculation

Auto-derived during compilation. For each output pin (0-7), iterate segments in list order, accumulate LED counts:

```python
output_offsets = {}  # (output, segment_index) -> offset
for output in range(8):
    offset = 0
    for seg in segments:
        if seg.output == output:
            output_offsets[id(seg)] = offset
            offset += seg.led_count()
```

No manual offset entry. Order in the list = order on the wire.

### CompiledPixelMap changes

Same structure — forward LUT, reverse LUT, output config. Just built from flat segments instead of nested strips/lines.

### Validation rules (unchanged)

- Segments must be axis-aligned (no diagonal)
- No two LEDs may map to the same (x, y)
- Total LEDs per output must not exceed `max_leds_per_output`
- Output must be in range [0, 7]
- Color order must be valid (RGB, RBG, GRB, GBR, BRG, BGR)
- Non-negative coordinates

## Setup UI

### Grid Preview (SVG)

Dynamic SVG rendered from the segment list:

- Each segment drawn as a thick colored line at its grid position
- Start dot (circle) marks the first LED of each segment
- Direction arrow (triangle) at the end shows LED flow direction
- Dashed lines connect segments on the same output (daisy-chain visualization)
- X/Y axis labels on edges
- Segment colors use golden-angle HSL spacing for maximum distinction
- Respects origin setting (bottom-left vs top-left)

### Segment Table

Flat table, one row per segment. Column order: geometry first, wiring second.

| | Start X | Start Y | End X | End Y | LEDs | Out | Color | |
|---|---------|---------|-------|-------|------|-----|-------|-|
| [dot] | 0 | 0 | 0 | 171 | 172 | [0] | [BGR] | x |

- Color swatch dot matches grid preview color
- Start X, Start Y, End X, End Y are editable number inputs
- LEDs is auto-calculated (read-only)
- Out is a dropdown (0-7)
- Color is a dropdown (BGR, RGB, GRB, etc.)
- Delete button (x) removes the row
- "Add Segment" button appends a new row with defaults

### Mobile Layout

On screens narrower than 600px, each segment row becomes a stacked card:

```
[color dot] (0,0) → (0,171)  172 LEDs
Out: 0  Color: BGR  [×]
```

Uses CSS `@media (max-width: 600px)` to switch between table and card layout.

### Summary Bar

Below the table:

```
10 segments · 5 outputs · 1720 LEDs · Grid 10×172
[Validate] [Apply]
```

### Controls

- **Origin selector** — dropdown next to grid preview header
- **Validate button** — calls `/api/pixel-map/validate`, displays errors inline
- **Apply button** — calls `/api/pixel-map/apply`, sends CONFIG to Teensy, refreshes grid preview
- **Add Segment** — appends a row with defaults (next unused x column, output 0, BGR)

### Debounced saves

No auto-save on input change. User explicitly clicks Apply. Validate is optional (Apply validates first anyway).

## API Changes

### Endpoints (simplified)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/pixel-map/` | GET | Return full config: segments, grid dimensions, output config |
| `POST /api/pixel-map/apply` | POST | Replace all segments. Body: `{segments: [...], origin: "..."}`. Validates, compiles, sends CONFIG (await ACK), saves. |
| `POST /api/pixel-map/validate` | POST | Validate without applying. Body: `{segments: [...]}`. Returns errors. |
| `GET /api/pixel-map/teensy-status` | GET | Teensy connection + config status |

No per-strip CRUD. The UI sends the entire segment list on Apply. Simpler, fewer race conditions.

### Request/Response

```python
class SegmentRequest(BaseModel):
    start: list[int]      # [x, y]
    end: list[int]        # [x, y]
    output: int           # 0-7
    color_order: str = 'BGR'

class PixelMapApplyRequest(BaseModel):
    origin: str = 'bottom-left'
    segments: list[SegmentRequest]
```

## Modified Files

| File | Change |
|------|--------|
| `pi/app/config/pixel_map.py` | Replace StripConfig/LineConfig with SegmentConfig. Flat segment list. Auto-calculated offsets. Schema version 2. |
| `pi/app/api/routes/pixel_map.py` | Simplify to GET + apply + validate. Remove per-strip CRUD. |
| `pi/config/pixel_map.yaml` | Convert to flat segment format |
| `pi/app/ui/static/index.html` | New Setup section: SVG preview + flat table |
| `pi/app/ui/static/js/app.js` | Rewrite setup functions: SVG grid renderer, flat table editor, mobile cards |
| `pi/app/ui/static/css/app.css` | Segment table styles, mobile card styles, SVG container |
| `pi/app/mapping/packer.py` | Adapt to new CompiledPixelMap from flat segments |
| `pi/app/core/renderer.py` | Update test-strip pattern for flat segments |
| `pi/tests/test_pixel_map.py` | Update tests for flat segment model |
| `pi/tests/test_packer.py` | Update tests |

## Non-Goals

- Per-pixel visual editor (click grid cells) — future
- Drag-and-drop segment reordering — future
- Import/export (JSON paste, Pixelblaze format) — future
- 3D coordinate support — future
