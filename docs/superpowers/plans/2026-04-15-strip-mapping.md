# Strip Mapping — Live Strip-to-Channel Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken channel-only setup with a live strip mapping table where each strip is assigned to a channel with direction, offset, LED count, and color order. Changes compile and hot-apply immediately. Includes a per-strip test pattern.

**Architecture:** New `StripMapping`/`StripInstallation` data model in installation.py (schema v3) with migration from v1 and v2. A new `compile_strip_plan()` function bridges the strip model to the existing `CompiledStripPlan`/`CompiledOutputPlan` + `map_frame_compiled()` pipeline. CRUD API routes with immediate compile+apply. Frontend strip table with live editing.

**Tech Stack:** Python (FastAPI, PyYAML, dataclasses, numpy), HTML/CSS/JS

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `pi/app/config/installation.py` | Rewrite | StripMapping/StripInstallation model, migration v1/v2→v3, load/save |
| `pi/app/mapping/runtime_plan.py` | Modify | Add `compile_strip_plan()`, remove `compile_channel_plan()` |
| `pi/app/api/routes/setup.py` | Rewrite | CRUD strip endpoints + test pattern |
| `pi/app/api/schemas.py` | Modify | Add `StripConfigRequest` |
| `pi/app/main.py` | Modify | Use strip model, re-enable apply_output_plan |
| `pi/app/core/renderer.py` | Modify | Add test strip pattern injection |
| `pi/app/ui/static/index.html` | Modify | Strip table HTML |
| `pi/app/ui/static/js/app.js` | Modify | Strip table JS |
| `pi/app/ui/static/css/app.css` | Modify | Strip table styles |
| `pi/tests/test_strip_mapping.py` | Create | Tests for model, migration, plan compilation |

---

### Task 1: Strip Data Model + Migration + Tests

**Files:**
- Rewrite: `pi/app/config/installation.py`
- Create: `pi/tests/test_strip_mapping.py`

- [ ] **Step 1: Write tests**

```python
# pi/tests/test_strip_mapping.py
"""Tests for strip mapping data model and migration."""

import pytest
import tempfile
from pathlib import Path

from app.config.installation import (
  StripMapping, StripInstallation, VALID_COLOR_ORDERS, VALID_DIRECTIONS,
  synthesize_default_strips, load_installation, save_installation,
  migrate_v1_to_strips, migrate_v2_to_strips,
)


class TestStripMapping:
  def test_default_strips(self):
    inst = synthesize_default_strips()
    assert len(inst.strips) == 10
    # Paired: strips 0,1 on ch0; 2,3 on ch1; etc.
    for i, s in enumerate(inst.strips):
      assert s.channel == i // 2
      assert s.offset == (i % 2) * 172
      assert s.led_count == 172
      assert s.color_order == 'BGR'
    # Even strips bottom_to_top, odd top_to_bottom
    assert inst.strips[0].direction == 'bottom_to_top'
    assert inst.strips[1].direction == 'top_to_bottom'

  def test_validate_valid(self):
    inst = synthesize_default_strips()
    assert inst.validate() == []

  def test_validate_bad_color_order(self):
    inst = synthesize_default_strips()
    inst.strips[0].color_order = 'XYZ'
    errors = inst.validate()
    assert any('color_order' in e for e in errors)

  def test_validate_led_count_zero(self):
    inst = synthesize_default_strips()
    inst.strips[0].led_count = 0
    errors = inst.validate()
    assert any('led_count' in e for e in errors)

  def test_validate_overlap(self):
    inst = synthesize_default_strips()
    # Put strip 2 on same channel+offset as strip 0
    inst.strips[2].channel = 0
    inst.strips[2].offset = 0
    errors = inst.validate()
    assert any('overlap' in e.lower() for e in errors)

  def test_validate_exceeds_channel(self):
    inst = synthesize_default_strips()
    inst.strips[0].offset = 1000
    inst.strips[0].led_count = 200  # 1000+200 = 1200 > 1100
    errors = inst.validate()
    assert any('exceed' in e.lower() or '1100' in e for e in errors)


class TestMigration:
  def test_migrate_v1(self):
    """Old strip-oriented format with output_channel/output_slot."""
    old_data = {
      'schema_version': 1,
      'strips': [
        {'id': 0, 'output_channel': 0, 'output_slot': 0, 'installed_led_count': 172,
         'color_order': 'BGR', 'direction': 'bottom_to_top', 'enabled': True},
        {'id': 1, 'output_channel': 0, 'output_slot': 1, 'installed_led_count': 172,
         'color_order': 'BGR', 'direction': 'top_to_bottom', 'enabled': True},
      ],
    }
    inst = migrate_v1_to_strips(old_data)
    assert inst.schema_version == 3
    assert len(inst.strips) == 2
    assert inst.strips[0].channel == 0
    assert inst.strips[0].offset == 0
    assert inst.strips[1].channel == 0
    assert inst.strips[1].offset == 172  # slot 1 * 172

  def test_migrate_v2(self):
    """Channel-only format → synthesize paired strips."""
    old_data = {
      'schema_version': 2,
      'channels': [
        {'channel': 0, 'color_order': 'GRB', 'led_count': 344},
        {'channel': 1, 'color_order': 'BGR', 'led_count': 344},
        {'channel': 2, 'color_order': 'BGR', 'led_count': 0},
      ],
    }
    inst = migrate_v2_to_strips(old_data)
    assert inst.schema_version == 3
    # 2 active channels × 2 strips each = 4 strips
    assert len(inst.strips) == 4
    assert inst.strips[0].channel == 0
    assert inst.strips[0].color_order == 'GRB'
    assert inst.strips[1].channel == 0
    assert inst.strips[1].offset == 172


class TestPersistence:
  def test_save_and_load(self):
    with tempfile.TemporaryDirectory() as tmp:
      config_dir = Path(tmp)
      inst = synthesize_default_strips()
      inst.strips[0].color_order = 'RGB'
      inst.strips[0].led_count = 100
      save_installation(inst, config_dir)

      loaded = load_installation(config_dir)
      assert loaded.schema_version == 3
      assert loaded.strips[0].color_order == 'RGB'
      assert loaded.strips[0].led_count == 100
      assert len(loaded.strips) == 10
```

- [ ] **Step 2: Implement strip model**

Replace `pi/app/config/installation.py` entirely:

```python
"""
Installation config — strip-to-channel mapping.

Manages installation.yaml: per-strip channel assignment, direction,
offset, LED count, and color order. Changes apply live.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

from ..hardware_constants import (
  STRIPS, LEDS_PER_STRIP, CHANNELS, CONTROLLER_WIRE_ORDER,
  ACTIVE_OUTPUTS,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3
MAX_LEDS_PER_CHANNEL = 1100

VALID_COLOR_ORDERS = frozenset(["RGB", "RBG", "GRB", "GBR", "BRG", "BGR"])
VALID_DIRECTIONS = frozenset(["bottom_to_top", "top_to_bottom"])


@dataclass
class StripMapping:
  id: int
  channel: int = 0
  offset: int = 0
  direction: str = "bottom_to_top"
  led_count: int = 172
  color_order: str = "BGR"

  def validate(self) -> list[str]:
    errors = []
    if not 0 <= self.channel < 8:
      errors.append(f"Strip {self.id}: channel {self.channel} out of range [0, 7]")
    if self.offset < 0:
      errors.append(f"Strip {self.id}: offset must be >= 0")
    if not 1 <= self.led_count <= MAX_LEDS_PER_CHANNEL:
      errors.append(f"Strip {self.id}: led_count {self.led_count} out of range [1, {MAX_LEDS_PER_CHANNEL}]")
    if self.offset + self.led_count > MAX_LEDS_PER_CHANNEL:
      errors.append(f"Strip {self.id}: offset + led_count ({self.offset + self.led_count}) exceeds {MAX_LEDS_PER_CHANNEL}")
    if self.color_order not in VALID_COLOR_ORDERS:
      errors.append(f"Strip {self.id}: invalid color_order '{self.color_order}'")
    if self.direction not in VALID_DIRECTIONS:
      errors.append(f"Strip {self.id}: invalid direction '{self.direction}'")
    return errors


@dataclass
class StripInstallation:
  schema_version: int = SCHEMA_VERSION
  strips: list[StripMapping] = field(default_factory=list)

  def validate(self) -> list[str]:
    errors = []
    for s in self.strips:
      errors.extend(s.validate())
    # Check overlapping LED ranges on same channel
    by_channel: dict[int, list[StripMapping]] = {}
    for s in self.strips:
      by_channel.setdefault(s.channel, []).append(s)
    for ch, strips in by_channel.items():
      for i, a in enumerate(strips):
        for b in strips[i + 1:]:
          a_end = a.offset + a.led_count
          b_end = b.offset + b.led_count
          if a.offset < b_end and b.offset < a_end:
            errors.append(
              f"Overlap on channel {ch}: strip {a.id} [{a.offset}:{a_end}] "
              f"and strip {b.id} [{b.offset}:{b_end}]"
            )
    return errors

  def to_dict(self) -> dict:
    return {
      'schema_version': self.schema_version,
      'strips': [asdict(s) for s in self.strips],
    }

  def strips_api_list(self) -> list[dict]:
    return [asdict(s) for s in self.strips]

  def next_id(self) -> int:
    if not self.strips:
      return 0
    return max(s.id for s in self.strips) + 1

  def renumber_ids(self):
    for i, s in enumerate(self.strips):
      s.id = i


def synthesize_default_strips() -> StripInstallation:
  """Create default 10-strip serpentine layout matching legacy hardware."""
  strips = []
  for i in range(STRIPS):
    strips.append(StripMapping(
      id=i,
      channel=i // 2,
      offset=(i % 2) * LEDS_PER_STRIP,
      direction='bottom_to_top' if i % 2 == 0 else 'top_to_bottom',
      led_count=LEDS_PER_STRIP,
      color_order=CONTROLLER_WIRE_ORDER,
    ))
  return StripInstallation(strips=strips)


def migrate_v1_to_strips(data: dict) -> StripInstallation:
  """Migrate v1 (old strip-oriented with output_channel/output_slot)."""
  strips = []
  for s in data.get('strips', []):
    if not s.get('enabled', True):
      continue
    strips.append(StripMapping(
      id=len(strips),
      channel=s.get('output_channel', 0),
      offset=s.get('output_slot', 0) * LEDS_PER_STRIP,
      direction=s.get('direction', 'bottom_to_top'),
      led_count=s.get('installed_led_count', LEDS_PER_STRIP),
      color_order=s.get('color_order', CONTROLLER_WIRE_ORDER),
    ))
  return StripInstallation(schema_version=SCHEMA_VERSION, strips=strips)


def migrate_v2_to_strips(data: dict) -> StripInstallation:
  """Migrate v2 (channel-only) → synthesize paired strips per active channel."""
  strips = []
  for ch in data.get('channels', []):
    led_count = ch.get('led_count', 0)
    if led_count == 0:
      continue
    ch_num = ch.get('channel', 0)
    color_order = ch.get('color_order', CONTROLLER_WIRE_ORDER)
    # Synthesize 2 strips per channel (paired serpentine)
    half = led_count // 2
    strips.append(StripMapping(
      id=len(strips),
      channel=ch_num,
      offset=0,
      direction='bottom_to_top',
      led_count=half,
      color_order=color_order,
    ))
    strips.append(StripMapping(
      id=len(strips),
      channel=ch_num,
      offset=half,
      direction='top_to_bottom',
      led_count=led_count - half,
      color_order=color_order,
    ))
  return StripInstallation(schema_version=SCHEMA_VERSION, strips=strips)


def load_installation(config_dir: Path) -> StripInstallation:
  """Load installation.yaml, migrating from v1/v2 or synthesizing defaults."""
  path = config_dir / "installation.yaml"
  if path.exists():
    with open(path) as f:
      data = yaml.safe_load(f) or {}

    version = data.get('schema_version', 0)
    if version >= 3:
      return _parse_strips(data)
    if version == 2:
      logger.info("Migrating v2 channel installation.yaml to v3 strip format")
      inst = migrate_v2_to_strips(data)
      save_installation(inst, config_dir)
      return inst
    if 'strips' in data:
      logger.info("Migrating v1 strip installation.yaml to v3 format")
      inst = migrate_v1_to_strips(data)
      save_installation(inst, config_dir)
      return inst

  inst = synthesize_default_strips()
  save_installation(inst, config_dir)
  logger.info("Synthesized default strip installation.yaml")
  return inst


def _parse_strips(data: dict) -> StripInstallation:
  strips = []
  for s in data.get('strips', []):
    strips.append(StripMapping(
      id=s.get('id', len(strips)),
      channel=s.get('channel', 0),
      offset=s.get('offset', 0),
      direction=s.get('direction', 'bottom_to_top'),
      led_count=s.get('led_count', LEDS_PER_STRIP),
      color_order=s.get('color_order', CONTROLLER_WIRE_ORDER),
    ))
  return StripInstallation(
    schema_version=data.get('schema_version', SCHEMA_VERSION),
    strips=strips,
  )


def save_installation(config: StripInstallation, config_dir: Path):
  path = config_dir / "installation.yaml"
  config_dir.mkdir(parents=True, exist_ok=True)
  data = config.to_dict()
  fd, tmp_path = tempfile.mkstemp(dir=str(config_dir), suffix='.tmp')
  try:
    with os.fdopen(fd, 'w') as f:
      yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    os.replace(tmp_path, str(path))
    logger.info("Saved installation.yaml")
  except Exception:
    try:
      os.unlink(tmp_path)
    except OSError:
      pass
    raise
```

- [ ] **Step 3: Run tests**

Run: `cd pi && source .venv/bin/activate && PYTHONPATH=. pytest tests/test_strip_mapping.py -v`
Expected: all 9 tests PASS

- [ ] **Step 4: Commit**

```bash
git add pi/app/config/installation.py pi/tests/test_strip_mapping.py
git commit -m "feat: strip mapping data model with v1/v2 migration"
```

---

### Task 2: compile_strip_plan + Re-enable Output Plan

**Files:**
- Modify: `pi/app/mapping/runtime_plan.py`
- Modify: `pi/app/main.py`

- [ ] **Step 1: Add compile_strip_plan to runtime_plan.py**

Remove the `compile_channel_plan` function (the entire function). Add this new function at the end of the file:

```python
def compile_strip_plan(installation, controller: ControllerProfile) -> CompiledOutputPlan:
  """Compile a strip-mapping installation into an output plan.

  Each StripMapping becomes a CompiledStripPlan. The output plan always uses
  controller.active_outputs for channel count and controller.electrical_leds_per_output
  for LEDs per channel — these are fixed by the Teensy firmware.
  """
  compiled_strips = []
  for i, strip in enumerate(installation.strips):
    swizzle = derive_precontroller_swizzle(
      controller.controller_wire_order,
      strip.color_order,
    )
    compiled_strips.append(CompiledStripPlan(
      strip_id=strip.id,
      enabled=True,
      logical_order=i,  # strip index = logical column
      output_channel=strip.channel,
      output_slot=0,
      output_offset=strip.offset,
      direction=strip.direction,
      installed_led_count=strip.led_count,
      color_order=strip.color_order,
      precontroller_swizzle=swizzle,
    ))

  logical_width = len(compiled_strips)
  return CompiledOutputPlan(
    controller=controller,
    strips=tuple(compiled_strips),
    logical_width=logical_width,
    logical_height=controller.physical_leds_per_strip,
    channels=controller.active_outputs,
    leds_per_channel=controller.electrical_leds_per_output,
  )
```

- [ ] **Step 2: Update main.py**

Change the import line from:
```python
from .mapping.runtime_plan import load_controller_profile, compile_channel_plan
```
to:
```python
from .mapping.runtime_plan import load_controller_profile, compile_strip_plan
```

Replace the installation/plan block (approximately lines 175-187) with:
```python
  # Installation config — mutable strip mapping
  installation = load_installation(config_dir)
  spatial_map = load_spatial_map(config_dir)
  controller_profile = load_controller_profile(config.get('hardware'))
  compiled_plan = compile_strip_plan(installation, controller_profile)
  logger.info(f"Installation: {len(installation.strips)} strips")
  logger.info(f"Compiled plan: {compiled_plan.channels}ch x {compiled_plan.leds_per_channel}leds, {compiled_plan.logical_width} logical cols")

  # Apply compiled plan — enables plan-driven mapper with per-strip color/direction
  renderer.apply_output_plan(compiled_plan)
  if spatial_map:
    logger.info(f"Spatial map: {spatial_map.profile_id}, {len(spatial_map.visible_strips)} visible strips")
```

- [ ] **Step 3: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/ -x -q --ignore=tests/test_matrix_rain_perf.py --ignore=tests/test_migrations.py`

- [ ] **Step 4: Commit**

```bash
git add pi/app/mapping/runtime_plan.py pi/app/main.py
git commit -m "feat: compile_strip_plan bridges strip model to output plan"
```

---

### Task 3: Setup API — CRUD Strip Endpoints + Test Pattern

**Files:**
- Rewrite: `pi/app/api/routes/setup.py`
- Modify: `pi/app/api/schemas.py`
- Modify: `pi/app/core/renderer.py`

- [ ] **Step 1: Add StripConfigRequest to schemas.py**

Replace the `ChannelConfigRequest` class with:

```python
class StripConfigRequest(BaseModel):
    channel: Optional[int] = None
    offset: Optional[int] = None
    direction: Optional[str] = None
    led_count: Optional[int] = None
    color_order: Optional[str] = None
```

- [ ] **Step 2: Add test strip support to renderer**

In `pi/app/core/renderer.py`, add to `__init__` (after `self._output_plan = None`):

```python
    self._test_strip_id: Optional[int] = None
    self._test_strip_until: float = 0.0
```

Add a method after `apply_output_plan`:

```python
  def set_test_strip(self, strip_id: Optional[int], duration: float = 5.0):
    """Activate a test pattern on a single strip for identification."""
    if strip_id is not None:
      self._test_strip_id = strip_id
      self._test_strip_until = time.monotonic() + duration
    else:
      self._test_strip_id = None
      self._test_strip_until = 0.0
```

In `_render_frame`, after the line `logical_frame = self._gamma_lut[logical_frame]` (line 254) and before the plan/legacy mapper block, add:

```python
      # Test strip pattern: override one logical column with gradient
      if self._test_strip_id is not None:
        if time.monotonic() < self._test_strip_until:
          logical_frame[:] = 0  # black out everything
          plan = self._output_plan
          if plan:
            for strip in plan.strips:
              if strip.strip_id == self._test_strip_id:
                col = strip.logical_order
                if col < logical_frame.shape[0]:
                  h = logical_frame.shape[1]
                  # Red at bottom, blue at top gradient
                  for y in range(h):
                    t = y / max(h - 1, 1)
                    logical_frame[col, y] = [int(255 * (1 - t)), 0, int(255 * t)]
                break
        else:
          self._test_strip_id = None
```

- [ ] **Step 3: Rewrite setup routes**

Replace `pi/app/api/routes/setup.py` entirely:

```python
"""
Setup API routes — live strip-to-channel mapping.

Each strip edit validates, recompiles the output plan, hot-applies
to the renderer, and persists to installation.yaml.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import StripConfigRequest
from ...config.installation import (
  StripMapping, StripInstallation, save_installation,
  VALID_COLOR_ORDERS, VALID_DIRECTIONS, MAX_LEDS_PER_CHANNEL,
)
from ...mapping.runtime_plan import compile_strip_plan

logger = logging.getLogger(__name__)


def _recompile_and_apply(deps):
  """Validate, recompile, hot-apply, persist."""
  errors = deps.installation.validate()
  if errors:
    raise HTTPException(422, f"Validation failed: {'; '.join(errors)}")
  plan = compile_strip_plan(deps.installation, deps.controller_profile)
  deps.renderer.apply_output_plan(plan)
  save_installation(deps.installation, deps.config_dir)


def create_router(deps, require_auth, broadcast_state) -> APIRouter:
    router = APIRouter(prefix="/api/setup", tags=["setup"])

    @router.get("/strips")
    async def get_strips():
        return {"strips": deps.installation.strips_api_list()}

    @router.post("/strips/{strip_id}", dependencies=[Depends(require_auth)])
    async def update_strip(strip_id: int, req: StripConfigRequest):
        strip = next((s for s in deps.installation.strips if s.id == strip_id), None)
        if strip is None:
            raise HTTPException(404, f"Strip {strip_id} not found")

        if req.channel is not None:
            if not 0 <= req.channel < 8:
                raise HTTPException(422, "channel must be 0-7")
            strip.channel = req.channel
        if req.offset is not None:
            if req.offset < 0:
                raise HTTPException(422, "offset must be >= 0")
            strip.offset = req.offset
        if req.direction is not None:
            if req.direction not in VALID_DIRECTIONS:
                raise HTTPException(422, f"direction must be one of: {', '.join(sorted(VALID_DIRECTIONS))}")
            strip.direction = req.direction
        if req.led_count is not None:
            if not 1 <= req.led_count <= MAX_LEDS_PER_CHANNEL:
                raise HTTPException(422, f"led_count must be 1-{MAX_LEDS_PER_CHANNEL}")
            strip.led_count = req.led_count
        if req.color_order is not None:
            if req.color_order not in VALID_COLOR_ORDERS:
                raise HTTPException(422, f"color_order must be one of: {', '.join(sorted(VALID_COLOR_ORDERS))}")
            strip.color_order = req.color_order

        _recompile_and_apply(deps)
        logger.info(f"Strip {strip_id} updated: ch{strip.channel}+{strip.offset} {strip.direction} {strip.led_count}LEDs {strip.color_order}")
        return {"status": "ok", "strips": deps.installation.strips_api_list()}

    @router.post("/strips", dependencies=[Depends(require_auth)])
    async def add_strip(req: StripConfigRequest):
        new_id = deps.installation.next_id()
        strip = StripMapping(
            id=new_id,
            channel=req.channel if req.channel is not None else 0,
            offset=req.offset if req.offset is not None else 0,
            direction=req.direction if req.direction is not None else 'bottom_to_top',
            led_count=req.led_count if req.led_count is not None else 172,
            color_order=req.color_order if req.color_order is not None else 'BGR',
        )
        deps.installation.strips.append(strip)

        try:
            _recompile_and_apply(deps)
        except HTTPException:
            deps.installation.strips.pop()
            raise

        logger.info(f"Strip {new_id} added: ch{strip.channel}+{strip.offset}")
        return {"status": "ok", "strips": deps.installation.strips_api_list()}

    @router.delete("/strips/{strip_id}", dependencies=[Depends(require_auth)])
    async def delete_strip(strip_id: int):
        strip = next((s for s in deps.installation.strips if s.id == strip_id), None)
        if strip is None:
            raise HTTPException(404, f"Strip {strip_id} not found")

        deps.installation.strips.remove(strip)
        deps.installation.renumber_ids()

        _recompile_and_apply(deps)
        logger.info(f"Strip {strip_id} deleted, {len(deps.installation.strips)} remaining")
        return {"status": "ok", "strips": deps.installation.strips_api_list()}

    @router.post("/strips/{strip_id}/test", dependencies=[Depends(require_auth)])
    async def test_strip(strip_id: int):
        strip = next((s for s in deps.installation.strips if s.id == strip_id), None)
        if strip is None:
            raise HTTPException(404, f"Strip {strip_id} not found")
        deps.renderer.set_test_strip(strip_id)
        return {"status": "ok", "strip_id": strip_id, "duration": 5}

    return router
```

- [ ] **Step 4: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/ -x -q --ignore=tests/test_matrix_rain_perf.py --ignore=tests/test_migrations.py`

- [ ] **Step 5: Commit**

```bash
git add pi/app/api/routes/setup.py pi/app/api/schemas.py pi/app/core/renderer.py
git commit -m "feat: CRUD strip mapping API with test pattern and live apply"
```

---

### Task 4: Frontend — Strip Mapping Table

**Files:**
- Modify: `pi/app/ui/static/index.html` (setup section)
- Modify: `pi/app/ui/static/js/app.js` (setup section)
- Modify: `pi/app/ui/static/css/app.css`

- [ ] **Step 1: Replace setup section HTML**

In `pi/app/ui/static/index.html`, replace the `<div id="system-setup" ...>` block with:

```html
          <!-- Setup section -->
          <div id="system-setup" class="system-section hidden">
            <div class="help-panel collapsed" data-tab="system-setup">
              <button class="help-toggle" aria-expanded="false">
                <span class="help-icon">?</span> How to use this page
              </button>
              <div class="help-content" hidden>
                <p>Map LED strips to OctoWS2811 output channels.</p>
                <p>Each strip is placed on a channel at an LED offset. Set direction to match wiring (bottom-to-top or top-to-bottom). Color order must match your LED chipset (usually BGR for WS2812B). Use the Test button to light up a strip for identification. Changes apply immediately.</p>
              </div>
            </div>
            <h3>Strip Mapping</h3>
            <div id="strip-status" class="status-msg"></div>
            <table id="strip-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Ch</th>
                  <th>Offset</th>
                  <th>Dir</th>
                  <th>LEDs</th>
                  <th>Color</th>
                  <th></th>
                </tr>
              </thead>
              <tbody id="strip-rows"></tbody>
            </table>
            <button id="add-strip-btn" class="action-btn secondary">Add Strip</button>
          </div>
```

- [ ] **Step 2: Replace setup CSS**

In `pi/app/ui/static/css/app.css`, find and replace the `#channel-table` styles (from the previous task) with strip table styles:

```css
#strip-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
}

#strip-table th {
  text-align: left;
  padding: 6px 4px;
  font-size: 11px;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border);
}

#strip-table td {
  padding: 4px;
  border-bottom: 1px solid var(--border);
}

#strip-table select,
#strip-table input[type="number"] {
  width: 100%;
  padding: 6px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 13px;
}

#strip-table input[type="number"] {
  width: 70px;
}

#strip-table .strip-id {
  font-weight: bold;
  text-align: center;
  font-size: 14px;
}

#strip-table .strip-actions {
  display: flex;
  gap: 4px;
}

#strip-table .strip-actions button {
  padding: 4px 8px;
  font-size: 11px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface2);
  color: var(--text);
  cursor: pointer;
}

#strip-table .strip-actions .test-btn {
  color: var(--accent);
  border-color: var(--accent);
}

#strip-table .strip-actions .del-btn {
  color: var(--danger);
  border-color: var(--danger);
}

#add-strip-btn {
  margin-top: 12px;
}
```

- [ ] **Step 3: Replace setup JavaScript**

In `pi/app/ui/static/js/app.js`, replace the `// --- Setup ---` section (everything from `// --- Setup ---` to `// --- Brightness ---`) with:

```javascript
// --- Setup ---

async function loadStripConfig() {
  const data = await api('GET', '/api/setup/strips');
  if (!data || !data.strips) return;
  renderStripTable(data.strips);
}

function renderStripTable(strips) {
  const tbody = document.getElementById('strip-rows');
  tbody.innerHTML = '';

  const colorOrders = ['RGB','RBG','GRB','GBR','BRG','BGR'];
  const directions = [
    { value: 'bottom_to_top', label: '\u2191 Up' },
    { value: 'top_to_bottom', label: '\u2193 Down' },
  ];

  for (const s of strips) {
    const tr = document.createElement('tr');
    tr.dataset.stripId = s.id;

    const colorOpts = colorOrders.map(o =>
      `<option value="${o}" ${o === s.color_order ? 'selected' : ''}>${o}</option>`
    ).join('');

    const dirOpts = directions.map(d =>
      `<option value="${d.value}" ${d.value === s.direction ? 'selected' : ''}>${d.label}</option>`
    ).join('');

    tr.innerHTML = `
      <td class="strip-id">${s.id}</td>
      <td><input type="number" data-strip="${s.id}" data-field="channel" value="${s.channel}" min="0" max="7" step="1"></td>
      <td><input type="number" data-strip="${s.id}" data-field="offset" value="${s.offset}" min="0" max="1100" step="1"></td>
      <td><select data-strip="${s.id}" data-field="direction">${dirOpts}</select></td>
      <td><input type="number" data-strip="${s.id}" data-field="led_count" value="${s.led_count}" min="1" max="1100" step="1"></td>
      <td><select data-strip="${s.id}" data-field="color_order">${colorOpts}</select></td>
      <td class="strip-actions">
        <button class="test-btn" data-strip="${s.id}">Test</button>
        <button class="del-btn" data-strip="${s.id}">\u2715</button>
      </td>
    `;
    tbody.appendChild(tr);
  }

  // Change handlers — debounced POST
  tbody.querySelectorAll('select, input[type="number"]').forEach(el => {
    let debounce = null;
    el.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => updateStrip(el), 300);
    });
    el.addEventListener('change', () => {
      clearTimeout(debounce);
      updateStrip(el);
    });
  });

  // Test buttons
  tbody.querySelectorAll('.test-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      api('POST', `/api/setup/strips/${btn.dataset.strip}/test`);
      showStripStatus(`Testing strip ${btn.dataset.strip}...`);
    });
  });

  // Delete buttons
  tbody.querySelectorAll('.del-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const result = await api('DELETE', `/api/setup/strips/${btn.dataset.strip}`);
      if (result && result.strips) {
        renderStripTable(result.strips);
        showStripStatus('Strip removed');
      }
    });
  });
}

async function updateStrip(el) {
  const stripId = parseInt(el.dataset.strip);
  const field = el.dataset.field;
  const value = (el.type === 'number') ? parseInt(el.value) : el.value;

  const body = {};
  body[field] = value;

  const result = await api('POST', `/api/setup/strips/${stripId}`, body);
  if (result && result.status === 'ok') {
    showStripStatus(`Strip ${stripId} updated`);
  } else {
    showStripStatus('Error updating strip', true);
  }
}

function showStripStatus(msg, isError = false) {
  const el = document.getElementById('strip-status');
  el.textContent = msg;
  el.className = isError ? 'status-msg error' : 'status-msg';
  setTimeout(() => { el.textContent = ''; }, 3000);
}

function initSetup() {
  document.getElementById('add-strip-btn').addEventListener('click', async () => {
    const result = await api('POST', '/api/setup/strips', {});
    if (result && result.strips) {
      renderStripTable(result.strips);
      showStripStatus('Strip added');
    }
  });
}
```

Also find the subnav click handler line:
```javascript
if (btn.dataset.section === 'system-setup') loadChannelConfig();
```
Replace `loadChannelConfig()` with `loadStripConfig()`.

- [ ] **Step 4: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/ -x -q --ignore=tests/test_matrix_rain_perf.py --ignore=tests/test_migrations.py`

- [ ] **Step 5: Commit**

```bash
git add pi/app/ui/static/index.html pi/app/ui/static/js/app.js pi/app/ui/static/css/app.css
git commit -m "feat: strip mapping table UI with test pattern and live apply"
```

---

### Task 5: Clean Up + Delete Old Tests

**Files:**
- Delete: `pi/tests/test_channel_config.py` (tests the removed ChannelConfig model)
- Modify: `pi/app/mapping/runtime_plan.py` (remove dead compile_channel_plan if still present)

- [ ] **Step 1: Remove old channel config tests**

```bash
rm pi/tests/test_channel_config.py
```

- [ ] **Step 2: Remove compile_channel_plan if still in runtime_plan.py**

Search `pi/app/mapping/runtime_plan.py` for `compile_channel_plan`. If found, delete the entire function.

- [ ] **Step 3: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/ -x -q --ignore=tests/test_matrix_rain_perf.py --ignore=tests/test_migrations.py`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove channel-only model and tests"
```

---

### Task 6: Deploy and Verify

- [ ] **Step 1: Deploy**

```bash
bash pi/scripts/deploy.sh ledfanatic.local
```

- [ ] **Step 2: Verify strips API**

```bash
ssh jim@ledfanatic.local "sleep 3 && curl -s http://localhost:80/api/setup/strips | python3 -m json.tool | head -30"
```

Expected: 10 strips with channel/offset/direction/led_count/color_order matching the legacy layout.

- [ ] **Step 3: Verify effects display**

Check logs for no render errors:
```bash
ssh jim@ledfanatic.local "sudo journalctl -u pillar --no-pager -n 10"
```

Visually confirm the pillar is displaying effects.

- [ ] **Step 4: Test a strip update**

```bash
ssh jim@ledfanatic.local "curl -s -X POST http://localhost:80/api/setup/strips/0 -H 'Content-Type: application/json' -d '{\"color_order\": \"RGB\"}'"
```

Verify the colors change on strip 0. Then reset:
```bash
ssh jim@ledfanatic.local "curl -s -X POST http://localhost:80/api/setup/strips/0 -H 'Content-Type: application/json' -d '{\"color_order\": \"BGR\"}'"
```

- [ ] **Step 5: Test the test pattern**

```bash
ssh jim@ledfanatic.local "curl -s -X POST http://localhost:80/api/setup/strips/0/test"
```

Verify strip 0 shows a red→blue gradient for 5 seconds.
