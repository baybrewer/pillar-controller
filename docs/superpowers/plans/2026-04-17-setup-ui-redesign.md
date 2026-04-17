# Setup UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the strip/line/card-based Setup UI with a flat segment table, SVG grid preview, and geometry-first data model. Mobile responsive.

**Architecture:** Flatten `StripConfig` + `LineConfig` into a single `SegmentConfig` (start, end, output, color_order). The pixel map becomes a flat list of segments. Output offsets are auto-calculated. The UI is a flat table with an SVG grid preview showing segment paths, arrows, and daisy-chain connections. API simplifies to GET + apply + validate.

**Tech Stack:** Python 3.11, FastAPI, NumPy, YAML, vanilla JS + SVG

---

## File Structure

### Modified Files
| File | Change |
|------|--------|
| `pi/app/config/pixel_map.py` | Replace StripConfig/LineConfig with SegmentConfig. Flat segment list. Auto-calculated offsets. Schema v2. |
| `pi/app/api/routes/pixel_map.py` | Simplify to GET + apply + validate + teensy-status. Remove per-strip CRUD. |
| `pi/app/mapping/packer.py` | Adapt to new CompiledPixelMap (no more strip.id lookups). |
| `pi/app/core/renderer.py` | Update test-strip for flat segments. |
| `pi/config/pixel_map.yaml` | Convert to flat segment format. |
| `pi/app/ui/static/index.html` | New Setup section HTML. |
| `pi/app/ui/static/js/app.js` | Rewrite setup functions: SVG renderer, flat table, mobile cards. |
| `pi/app/ui/static/css/app.css` | Segment table + mobile card styles. |
| `pi/tests/test_pixel_map.py` | Update for flat segment model. |
| `pi/tests/test_packer.py` | Update for new CompiledPixelMap. |

---

### Task 1: Flatten Data Model

**Files:**
- Modify: `pi/app/config/pixel_map.py`
- Modify: `pi/tests/test_pixel_map.py`

- [ ] **Step 1: Write tests for the new SegmentConfig model**

```python
# Replace imports and _simple_map helper in pi/tests/test_pixel_map.py

from app.config.pixel_map import (
    CompiledPixelMap, PixelMapConfig, SegmentConfig,
    compile_pixel_map, load_pixel_map, save_pixel_map, validate_pixel_map,
)

def _simple_map() -> PixelMapConfig:
    """2-column, 3-row grid. 2 segments on output 0."""
    return PixelMapConfig(
        segments=[
            SegmentConfig(start=(0, 0), end=(0, 2), output=0, color_order='BGR'),
            SegmentConfig(start=(1, 2), end=(1, 0), output=0, color_order='BGR'),
        ],
    )

class TestSegmentLedCount:
    def test_vertical_up(self):
        s = SegmentConfig(start=(0, 0), end=(0, 5), output=0)
        assert s.led_count() == 6

    def test_vertical_down(self):
        s = SegmentConfig(start=(1, 5), end=(1, 0), output=0)
        assert s.led_count() == 6

    def test_horizontal(self):
        s = SegmentConfig(start=(0, 3), end=(5, 3), output=0)
        assert s.led_count() == 6

    def test_diagonal_rejected(self):
        s = SegmentConfig(start=(0, 0), end=(3, 4), output=0)
        with pytest.raises(ValueError, match="axis-aligned"):
            s.led_count()

class TestFlatValidation:
    def test_valid_map(self):
        assert validate_pixel_map(_simple_map()) == []

    def test_duplicate_grid_position(self):
        cfg = PixelMapConfig(segments=[
            SegmentConfig(start=(0, 0), end=(0, 2), output=0),
            SegmentConfig(start=(0, 0), end=(0, 2), output=1),  # same positions
        ])
        errors = validate_pixel_map(cfg)
        assert any('duplicate' in e.lower() for e in errors)

    def test_output_overflow(self):
        cfg = PixelMapConfig(segments=[
            SegmentConfig(start=(0, 0), end=(0, 1199), output=0),
            SegmentConfig(start=(1, 0), end=(1, 100), output=0),  # total 1300 > 1200
        ])
        errors = validate_pixel_map(cfg)
        assert any('exceed' in e.lower() or 'overflow' in e.lower() for e in errors)

    def test_output_range(self):
        cfg = PixelMapConfig(segments=[
            SegmentConfig(start=(0, 0), end=(0, 5), output=9),
        ])
        errors = validate_pixel_map(cfg)
        assert any('output' in e.lower() for e in errors)

class TestFlatCompilation:
    def test_grid_dimensions(self):
        compiled = compile_pixel_map(_simple_map())
        assert compiled.width == 2
        assert compiled.height == 3

    def test_forward_lut(self):
        compiled = compile_pixel_map(_simple_map())
        # (0,0) = segment 0, LED 0
        assert compiled.forward_lut[0, 0, 0] == 0  # segment_index
        assert compiled.forward_lut[0, 0, 1] == 0  # led_index within segment

    def test_reverse_lut(self):
        compiled = compile_pixel_map(_simple_map())
        # segment 0, LED 0 → (0, 0)
        x, y, swizzle = compiled.reverse_lut[0][0]
        assert (x, y) == (0, 0)

    def test_output_config(self):
        compiled = compile_pixel_map(_simple_map())
        # Both segments on output 0: total 6 LEDs
        assert compiled.output_config[0] == 6

    def test_auto_offset(self):
        compiled = compile_pixel_map(_simple_map())
        # Segment 0: offset 0, 3 LEDs. Segment 1: offset 3, 3 LEDs.
        assert compiled.segment_offsets[0] == 0
        assert compiled.segment_offsets[1] == 3

class TestFlatLoadSave:
    def test_round_trip(self, tmp_path):
        cfg = _simple_map()
        save_pixel_map(cfg, tmp_path)
        loaded = load_pixel_map(tmp_path)
        assert len(loaded.segments) == 2
        assert loaded.segments[0].output == 0
        assert loaded.segments[0].start == (0, 0)
        assert loaded.segments[0].color_order == 'BGR'

    def test_schema_version_2(self, tmp_path):
        cfg = _simple_map()
        save_pixel_map(cfg, tmp_path)
        with open(tmp_path / 'pixel_map.yaml') as f:
            data = yaml.safe_load(f)
        assert data['schema_version'] == 2

class TestMixedColorOrder:
    def test_different_orders_per_segment(self):
        cfg = PixelMapConfig(segments=[
            SegmentConfig(start=(0, 0), end=(0, 2), output=0, color_order='BGR'),
            SegmentConfig(start=(1, 0), end=(1, 2), output=0, color_order='GRB'),
        ])
        compiled = compile_pixel_map(cfg)
        # Segment 0 LEDs get BGR swizzle (2,1,0)
        _, _, sw0 = compiled.reverse_lut[0][0]
        assert sw0 == (2, 1, 0)
        # Segment 1 LEDs get GRB swizzle (1,0,2)
        _, _, sw1 = compiled.reverse_lut[1][0]
        assert sw1 == (1, 0, 2)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd pi && PYTHONPATH=. .venv/bin/pytest tests/test_pixel_map.py -v
```
Expected: ImportError (SegmentConfig doesn't exist yet) or test failures

- [ ] **Step 3: Rewrite pixel_map.py with flat segment model**

Replace the data model:

```python
@dataclass
class SegmentConfig:
    """A run of LEDs along a single axis mapped to a Teensy output."""
    start: tuple[int, int]   # (x, y) grid position of first LED
    end: tuple[int, int]     # (x, y) grid position of last LED
    output: int              # Teensy output pin (0-7)
    color_order: str = 'BGR'

    def _validate_axis_aligned(self) -> tuple[int, int]:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        if dx != 0 and dy != 0:
            raise ValueError(
                f"Segment must be axis-aligned, got start={self.start} end={self.end}"
            )
        return dx, dy

    def led_count(self) -> int:
        dx, dy = self._validate_axis_aligned()
        return abs(dx) + abs(dy) + 1

    def positions(self) -> list[tuple[int, int]]:
        dx, dy = self._validate_axis_aligned()
        count = self.led_count()
        sx = 0 if dx == 0 else (1 if dx > 0 else -1)
        sy = 0 if dy == 0 else (1 if dy > 0 else -1)
        x, y = self.start
        result = []
        for _ in range(count):
            result.append((x, y))
            x += sx
            y += sy
        return result
```

Replace PixelMapConfig:
```python
@dataclass
class PixelMapConfig:
    origin: str = "bottom-left"
    teensy_outputs: int = 8
    teensy_max_leds_per_output: int = 1200
    teensy_wire_order: str = "BGR"
    teensy_signal_family: str = "ws281x_800khz"
    teensy_octo_pins: list[int] = field(default_factory=lambda: [2, 14, 7, 8, 6, 20, 21, 5])
    segments: list[SegmentConfig] = field(default_factory=list)
    pixel_overrides: dict[str, tuple[int, int]] = field(default_factory=dict)
```

Replace CompiledPixelMap:
```python
@dataclass
class CompiledPixelMap:
    width: int
    height: int
    origin: str
    forward_lut: np.ndarray       # (width, height, 2) int16 — [segment_index, led_index]
    reverse_lut: list[list]       # reverse_lut[segment_index][led_index] → (x, y, swizzle)
    output_config: list[int]      # LEDs per output pin [0..7]
    segment_offsets: list[int]    # auto-calculated offset for each segment on its output
    segments: list[SegmentConfig]
    total_mapped_leds: int
    teensy_outputs: int
    teensy_max_leds_per_output: int
```

Key changes to `compile_pixel_map`:
- No strip IDs — iterate segments by list index
- `forward_lut[x, y] = [segment_index, led_index_within_segment]`
- `reverse_lut[segment_index][led_index] = (x, y, swizzle)`
- `output_config = [0] * 8` — for each output, sum LED counts of segments on it
- `segment_offsets` — auto-calculated: for each segment, offset = sum of LED counts of prior segments on the same output

Key changes to `validate_pixel_map`:
- No strip ID checks — segments don't have IDs
- Output overflow: for each output, sum LED counts of all segments on it, check ≤ max
- Overlapping output ranges: not applicable (offsets auto-calculated, can't overlap)

Key changes to `_parse_config` / `_serialize_config`:
- Parse `segments:` list instead of `strips:` list
- Schema version 2
- Backward compat: if `strips:` key exists and `segments:` doesn't, migrate strips → segments

- [ ] **Step 4: Run tests**

```bash
cd pi && PYTHONPATH=. .venv/bin/pytest tests/test_pixel_map.py -v
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add pi/app/config/pixel_map.py pi/tests/test_pixel_map.py
git commit -m "refactor: flatten data model — SegmentConfig replaces StripConfig + LineConfig"
```

---

### Task 2: Update Packer for Flat Segments

**Files:**
- Modify: `pi/app/mapping/packer.py`
- Modify: `pi/tests/test_packer.py`

- [ ] **Step 1: Update test helpers**

```python
# pi/tests/test_packer.py — update imports and helpers
from app.config.pixel_map import PixelMapConfig, SegmentConfig, compile_pixel_map
from app.mapping.packer import pack_frame

def _simple_compiled():
    """2x3 grid, 2 segments on output 0, BGR order."""
    cfg = PixelMapConfig(segments=[
        SegmentConfig(start=(0, 0), end=(0, 2), output=0, color_order='BGR'),
        SegmentConfig(start=(1, 2), end=(1, 0), output=0, color_order='BGR'),
    ])
    return compile_pixel_map(cfg)
```

Keep existing test cases, update assertions for new CompiledPixelMap structure.

- [ ] **Step 2: Update packer.py**

The packer iterates `reverse_lut[segment_index]` instead of `reverse_lut[strip.id]`. Use `segment_offsets` for byte position calculation:

```python
def pack_frame(frame: np.ndarray, pixel_map: CompiledPixelMap) -> bytes:
    output_config = pixel_map.output_config
    total_bytes = sum(n * 3 for n in output_config)
    buf = bytearray(total_bytes)

    # Byte offsets per output pin
    pin_offsets = []
    offset = 0
    for n in output_config:
        pin_offsets.append(offset)
        offset += n * 3

    # Pack each segment
    for seg_idx, segment in enumerate(pixel_map.segments):
        seg_reverse = pixel_map.reverse_lut[seg_idx]
        pin = segment.output
        seg_offset = pixel_map.segment_offsets[seg_idx]
        base = pin_offsets[pin] + seg_offset * 3

        for led_idx in range(len(seg_reverse)):
            entry = seg_reverse[led_idx]
            if entry is None:
                continue
            x, y, swizzle = entry
            if x >= frame.shape[0] or y >= frame.shape[1]:
                continue
            rgb = frame[x, y]
            pos = base + led_idx * 3
            buf[pos] = rgb[swizzle[0]]
            buf[pos + 1] = rgb[swizzle[1]]
            buf[pos + 2] = rgb[swizzle[2]]

    return bytes(buf)
```

- [ ] **Step 3: Run tests**

```bash
cd pi && PYTHONPATH=. .venv/bin/pytest tests/test_packer.py tests/test_pixel_map.py -v
```

- [ ] **Step 4: Commit**

```bash
git add pi/app/mapping/packer.py pi/tests/test_packer.py
git commit -m "refactor: packer uses flat segment model with auto-calculated offsets"
```

---

### Task 3: Update Renderer + Default Config

**Files:**
- Modify: `pi/app/core/renderer.py`
- Modify: `pi/config/pixel_map.yaml`

- [ ] **Step 1: Update test-strip rendering in renderer.py**

Replace the strip-based test pattern with segment-based:

```python
# In _render_frame, replace the test-strip block:
if self._test_strip_id is not None:
    if time.monotonic() < self._test_strip_until:
        logical_frame[:] = 0
        # _test_strip_id is now a segment index
        if self._test_strip_id < len(self.pixel_map.segments):
            segment = self.pixel_map.segments[self._test_strip_id]
            for pos in segment.positions():
                x, y = pos
                if x < logical_frame.shape[0] and y < logical_frame.shape[1]:
                    # Gradient along the segment
                    positions = segment.positions()
                    idx = positions.index(pos)
                    frac = idx / max(len(positions) - 1, 1)
                    logical_frame[x, y] = [int(255 * (1 - frac)), 0, int(255 * frac)]
    else:
        self._test_strip_id = None
```

Also update `apply_pixel_map` — no more `self.pixel_map.strips` references.

- [ ] **Step 2: Convert default pixel_map.yaml to flat segment format**

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

  - start: [3, 171]
    end: [3, 0]
    output: 1
    color_order: BGR

  - start: [4, 0]
    end: [4, 171]
    output: 2
    color_order: BGR

  - start: [5, 171]
    end: [5, 0]
    output: 2
    color_order: BGR

  - start: [6, 0]
    end: [6, 171]
    output: 3
    color_order: BGR

  - start: [7, 171]
    end: [7, 0]
    output: 3
    color_order: BGR

  - start: [8, 0]
    end: [8, 171]
    output: 4
    color_order: BGR

  - start: [9, 171]
    end: [9, 0]
    output: 4
    color_order: BGR
```

- [ ] **Step 3: Run full test suite**

```bash
cd pi && PYTHONPATH=. .venv/bin/pytest tests/ -v 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add pi/app/core/renderer.py pi/config/pixel_map.yaml
git commit -m "refactor: renderer + default config use flat segment model"
```

---

### Task 4: Simplify API Routes

**Files:**
- Modify: `pi/app/api/routes/pixel_map.py`

- [ ] **Step 1: Rewrite the API routes**

Replace all per-strip CRUD with simple GET + apply + validate:

```python
class SegmentRequest(BaseModel):
    start: list[int]      # [x, y]
    end: list[int]        # [x, y]
    output: int           # 0-7
    color_order: str = 'BGR'

class PixelMapApplyRequest(BaseModel):
    origin: str = 'bottom-left'
    segments: list[SegmentRequest]

def create_router(deps, require_auth) -> APIRouter:
    router = APIRouter(prefix="/api/pixel-map", tags=["pixel-map"])

    @router.get("/")
    async def get_pixel_map():
        compiled = deps.compiled_pixel_map
        cfg = deps.pixel_map_config
        return {
            'origin': cfg.origin,
            'grid': {
                'width': compiled.width,
                'height': compiled.height,
                'total_mapped_leds': compiled.total_mapped_leds,
            },
            'output_config': compiled.output_config,
            'segments': [
                {
                    'start': list(s.start),
                    'end': list(s.end),
                    'output': s.output,
                    'color_order': s.color_order,
                    'led_count': s.led_count(),
                    'offset': compiled.segment_offsets[i],
                }
                for i, s in enumerate(cfg.segments)
            ],
        }

    @router.post("/apply")
    async def apply_pixel_map(req: PixelMapApplyRequest, auth=Depends(require_auth)):
        staged = PixelMapConfig(
            origin=req.origin,
            teensy_outputs=deps.pixel_map_config.teensy_outputs,
            teensy_max_leds_per_output=deps.pixel_map_config.teensy_max_leds_per_output,
            teensy_wire_order=deps.pixel_map_config.teensy_wire_order,
            teensy_signal_family=deps.pixel_map_config.teensy_signal_family,
            teensy_octo_pins=deps.pixel_map_config.teensy_octo_pins,
            segments=[
                SegmentConfig(
                    start=tuple(s.start),
                    end=tuple(s.end),
                    output=s.output,
                    color_order=s.color_order,
                )
                for s in req.segments
            ],
        )
        errors = validate_pixel_map(staged)
        if errors:
            raise HTTPException(422, detail=errors)
        compiled = compile_pixel_map(staged)
        config_ok = await deps.transport.send_config(compiled.output_config)
        if not config_ok:
            raise HTTPException(502, "Teensy rejected CONFIG or timed out")
        deps.pixel_map_config = staged
        deps.compiled_pixel_map = compiled
        deps.renderer.apply_pixel_map(compiled)
        save_pixel_map(staged, deps.config_dir)
        return await get_pixel_map()

    @router.post("/validate")
    async def validate_map(req: PixelMapApplyRequest):
        staged = PixelMapConfig(
            origin=req.origin,
            segments=[
                SegmentConfig(start=tuple(s.start), end=tuple(s.end),
                              output=s.output, color_order=s.color_order)
                for s in req.segments
            ],
        )
        errors = validate_pixel_map(staged)
        return {'valid': len(errors) == 0, 'errors': errors}

    @router.get("/teensy-status")
    async def teensy_status():
        return {
            'connected': deps.transport.connected,
            'caps': deps.transport.caps,
            'output_config': deps.compiled_pixel_map.output_config,
            'last_config_ack': deps.transport._last_config_ack,
        }

    return router
```

- [ ] **Step 2: Run tests**

```bash
cd pi && PYTHONPATH=. .venv/bin/pytest tests/ -v 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
git add pi/app/api/routes/pixel_map.py
git commit -m "refactor: simplify pixel map API — GET + apply + validate, no per-strip CRUD"
```

---

### Task 5: Rebuild Setup UI

**Files:**
- Modify: `pi/app/ui/static/index.html`
- Modify: `pi/app/ui/static/js/app.js`
- Modify: `pi/app/ui/static/css/app.css`

- [ ] **Step 1: Replace Setup HTML**

In the `system-setup` section of index.html, replace everything between the help panel and the wiring tests with:

```html
<!-- Grid Preview -->
<div id="pm-grid-container">
  <div class="pm-grid-header">
    <span id="pm-grid-info" class="text-dim"></span>
    <div class="pm-origin-row">
      <label>Origin:</label>
      <select id="pm-origin-select">
        <option value="bottom-left">Bottom Left</option>
        <option value="top-left">Top Left</option>
      </select>
    </div>
  </div>
  <div class="pm-svg-wrap">
    <svg id="pm-grid-svg" xmlns="http://www.w3.org/2000/svg"></svg>
  </div>
</div>

<!-- Segment Table -->
<div class="pm-segments-header">
  <span class="pm-label">Segments</span>
  <button id="pm-add-segment-btn" class="action-btn primary">+ Add Segment</button>
</div>
<div id="pm-segment-table-wrap">
  <table id="pm-segment-table" class="pm-table">
    <thead>
      <tr>
        <th></th>
        <th>Start X</th><th>Start Y</th>
        <th>End X</th><th>End Y</th>
        <th>LEDs</th>
        <th>Out</th>
        <th>Color</th>
        <th></th>
      </tr>
    </thead>
    <tbody id="pm-segment-tbody"></tbody>
  </table>
</div>
<!-- Mobile: segments render as cards via CSS -->
<div id="pm-segment-cards" class="pm-cards-mobile"></div>

<!-- Summary + Actions -->
<div class="pm-summary-bar">
  <span id="pm-summary-text"></span>
  <div class="pm-actions">
    <button id="pm-validate-btn" class="action-btn secondary">Validate</button>
    <button id="pm-apply-btn" class="action-btn primary">Apply</button>
  </div>
</div>
<div id="pm-status" class="status-msg"></div>
```

- [ ] **Step 2: Rewrite JS setup functions in app.js**

Replace the entire pixel map setup section (around lines 879–1200) with:

Key functions:
- `loadPixelMap()` — GET /api/pixel-map/, populate table + SVG
- `renderGridSVG(data)` — draw SVG with segment paths, arrows, daisy-chains
- `renderSegmentTable(data)` — flat table, one row per segment, geometry columns first
- `renderSegmentCards(data)` — mobile card layout (hidden on desktop)
- `addSegmentRow()` — append row with defaults
- `collectSegments()` — read all rows into array
- `applyPixelMap()` — POST /api/pixel-map/apply with full segment list
- `validatePixelMap()` — POST /api/pixel-map/validate

SVG rendering: for each segment, draw a thick colored line from start to end with:
- Circle at start position
- Arrow at end position
- Dashed line connecting consecutive segments on the same output

Color uses golden-angle HSL: `hsl(segIndex * 137.508 % 360, 75%, 55%)`

- [ ] **Step 3: Add CSS for table + mobile cards**

```css
/* Segment table */
.pm-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pm-table th { padding: 6px; color: #888; text-align: center; border-bottom: 1px solid #333; }
.pm-table td { padding: 4px; text-align: center; }
.pm-table input[type="number"] {
  width: 42px; background: #333; border: 1px solid #444;
  color: #ccc; padding: 2px; border-radius: 3px; text-align: center; font-size: 12px;
}
.pm-table select { background: #333; border: 1px solid #444; color: #ccc; padding: 2px; border-radius: 3px; font-size: 12px; }

/* Mobile cards */
.pm-cards-mobile { display: none; }
@media (max-width: 600px) {
  #pm-segment-table-wrap { display: none; }
  .pm-cards-mobile { display: block; }
  .pm-card {
    background: #222; border-radius: 8px; padding: 10px;
    margin-bottom: 6px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  }
  .pm-card-geo { font-size: 14px; flex: 1; }
  .pm-card-wire { font-size: 12px; color: #888; }
}

/* Summary bar */
.pm-summary-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 12px; background: #222; border-radius: 6px; margin-top: 12px;
}

/* SVG container */
.pm-svg-wrap { background: #111; border-radius: 6px; padding: 12px; }
#pm-grid-svg { width: 100%; height: auto; }
```

- [ ] **Step 4: Test manually**

```bash
cd pi && PILLAR_DEV=1 python -m app.main
```

Open browser, go to Setup tab:
- Grid SVG shows segment paths with arrows
- Flat table shows all segments
- Add/delete segments works
- Apply sends to API
- Mobile view shows cards (resize browser to <600px)

- [ ] **Step 5: Commit**

```bash
git add pi/app/ui/static/
git commit -m "feat: redesigned Setup UI — flat segment table, SVG grid preview, mobile cards"
```

---

### Task 6: Update Default Config on Pi + Deploy

- [ ] **Step 1: Run full test suite**

```bash
cd pi && PYTHONPATH=. .venv/bin/pytest tests/ -v 2>&1 | tail -10
```

- [ ] **Step 2: Copy new pixel_map.yaml to Pi**

```bash
scp pi/config/pixel_map.yaml jim@ledfanatic.local:/tmp/pixel_map.yaml
ssh jim@ledfanatic.local "sudo cp /tmp/pixel_map.yaml /opt/pillar/config/pixel_map.yaml && sudo chown pillar:pillar /opt/pillar/config/pixel_map.yaml && sudo chmod 644 /opt/pillar/config/pixel_map.yaml"
```

- [ ] **Step 3: Deploy**

```bash
bash pi/scripts/deploy.sh ledfanatic.local
```

- [ ] **Step 4: Verify**

- Open http://ledfanatic.local in browser
- Go to Setup tab — should show flat segment table + SVG preview
- Verify LEDs are running an effect (CONFIG ACK in logs)
- Test on phone — should show card layout

- [ ] **Step 5: Commit any fixes**

```bash
git add -A && git commit -m "fix: deployment integration fixes"
```

---

## Self-Review

**Spec coverage:**
- Flat segment model (SegmentConfig) → Task 1
- Auto-calculated offsets → Task 1 (compile_pixel_map)
- Schema version 2 → Task 1
- Updated packer → Task 2
- SVG grid preview with arrows/daisy-chains → Task 5
- Flat segment table (geometry first) → Task 5
- Mobile responsive cards → Task 5
- Simplified API (GET + apply + validate) → Task 4
- Default pixel_map.yaml conversion → Task 3
- Renderer test-strip update → Task 3
- Deploy + verify → Task 6

**Type consistency:** SegmentConfig used consistently across all tasks. CompiledPixelMap.segment_offsets used in both packer (Task 2) and API response (Task 4).
