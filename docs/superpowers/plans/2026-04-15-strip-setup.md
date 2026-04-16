# Strip Setup — Live Channel Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the session-based setup system with a live 8-channel config UI (color order + LED count per channel), applied immediately on each edit.

**Architecture:** New channel-oriented data model in installation.py with migration from old strip format. Simplified setup routes (GET/POST channels). Frontend table with dropdowns/inputs that POST on change. Each POST validates, recompiles output plan, hot-applies to renderer, and persists.

**Tech Stack:** Python (FastAPI, PyYAML, dataclasses), HTML/CSS/JS

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `pi/app/config/installation.py` | Rewrite | Channel-oriented data model, migration, load/save |
| `pi/app/api/routes/setup.py` | Rewrite | Two endpoints: GET channels, POST channel update |
| `pi/app/api/schemas.py` | Modify | Add `ChannelConfigRequest` |
| `pi/app/main.py` | Modify | Remove SetupSessionService, simplify init |
| `pi/app/ui/static/index.html` | Modify | Replace setup section HTML |
| `pi/app/ui/static/js/app.js` | Modify | Replace setup JS |
| `pi/app/ui/static/css/app.css` | Modify | Add channel table styles |
| `pi/tests/test_channel_config.py` | Create | Tests for channel model and migration |

---

### Task 1: Channel-Oriented Data Model + Migration

**Files:**
- Modify: `pi/app/config/installation.py`
- Create: `pi/tests/test_channel_config.py`

- [ ] **Step 1: Write tests for new channel model**

```python
# pi/tests/test_channel_config.py
"""Tests for channel-oriented installation config."""

import pytest
import tempfile
from pathlib import Path

from app.config.installation import (
  ChannelConfig, ChannelInstallation, VALID_COLOR_ORDERS,
  synthesize_default_channels, load_installation, save_installation,
  migrate_strip_to_channel,
)


class TestChannelConfig:
  def test_default_channels(self):
    inst = synthesize_default_channels()
    assert len(inst.channels) == 8
    # First 5 active (344 LEDs), last 3 unused (0 LEDs)
    for i in range(5):
      assert inst.channels[i].led_count == 344
      assert inst.channels[i].color_order == 'BGR'
    for i in range(5, 8):
      assert inst.channels[i].led_count == 0

  def test_validate_valid(self):
    inst = synthesize_default_channels()
    errors = inst.validate()
    assert errors == []

  def test_validate_bad_color_order(self):
    inst = synthesize_default_channels()
    inst.channels[0].color_order = 'XYZ'
    errors = inst.validate()
    assert any('color_order' in e for e in errors)

  def test_validate_led_count_range(self):
    inst = synthesize_default_channels()
    inst.channels[0].led_count = 1200
    errors = inst.validate()
    assert any('led_count' in e for e in errors)

  def test_validate_led_count_zero_ok(self):
    inst = synthesize_default_channels()
    inst.channels[7].led_count = 0
    errors = inst.validate()
    assert errors == []


class TestMigration:
  def test_migrate_strip_format(self):
    """Old strip-oriented data should migrate to channel-oriented."""
    old_data = {
      'schema_version': 1,
      'strips': [
        {'id': 0, 'output_channel': 0, 'output_slot': 0, 'installed_led_count': 172, 'color_order': 'BGR', 'enabled': True},
        {'id': 1, 'output_channel': 0, 'output_slot': 1, 'installed_led_count': 172, 'color_order': 'BGR', 'enabled': True},
        {'id': 2, 'output_channel': 1, 'output_slot': 0, 'installed_led_count': 172, 'color_order': 'GRB', 'enabled': True},
        {'id': 3, 'output_channel': 1, 'output_slot': 1, 'installed_led_count': 172, 'color_order': 'GRB', 'enabled': True},
      ],
    }
    inst = migrate_strip_to_channel(old_data)
    assert inst.schema_version == 2
    assert len(inst.channels) == 8
    # Channel 0: two strips of 172 = 344 LEDs, BGR
    assert inst.channels[0].led_count == 344
    assert inst.channels[0].color_order == 'BGR'
    # Channel 1: two strips of 172 = 344 LEDs, GRB (takes first strip's color order)
    assert inst.channels[1].led_count == 344
    assert inst.channels[1].color_order == 'GRB'
    # Channels 2-7: unused
    for i in range(2, 8):
      assert inst.channels[i].led_count == 0


class TestPersistence:
  def test_save_and_load(self):
    with tempfile.TemporaryDirectory() as tmp:
      config_dir = Path(tmp)
      inst = synthesize_default_channels()
      inst.channels[2].color_order = 'RGB'
      inst.channels[2].led_count = 500
      save_installation(inst, config_dir)

      loaded = load_installation(config_dir)
      assert loaded.channels[2].color_order == 'RGB'
      assert loaded.channels[2].led_count == 500
      assert loaded.schema_version == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pi && source .venv/bin/activate && PYTHONPATH=. pytest tests/test_channel_config.py -v`
Expected: FAIL — `ChannelConfig`, `ChannelInstallation`, etc. don't exist yet

- [ ] **Step 3: Implement channel-oriented data model**

Replace the contents of `pi/app/config/installation.py` with:

```python
"""
Installation config — channel-oriented LED configuration.

Manages installation.yaml: per-channel color order and LED count.
hardware.yaml stays the immutable controller envelope.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

from ..hardware_constants import (
  CHANNELS, LEDS_PER_CHANNEL, CONTROLLER_WIRE_ORDER,
  ACTIVE_OUTPUTS, TOTAL_OUTPUTS,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2
MAX_LEDS_PER_CHANNEL = 1100

VALID_COLOR_ORDERS = frozenset(["RGB", "RBG", "GRB", "GBR", "BRG", "BGR"])


@dataclass
class ChannelConfig:
  channel: int
  color_order: str = "BGR"
  led_count: int = 0

  def validate(self) -> list[str]:
    errors = []
    if not 0 <= self.channel < 8:
      errors.append(f"Channel {self.channel}: channel number out of range [0, 7]")
    if self.color_order not in VALID_COLOR_ORDERS:
      errors.append(f"Channel {self.channel}: invalid color_order '{self.color_order}'")
    if not 0 <= self.led_count <= MAX_LEDS_PER_CHANNEL:
      errors.append(f"Channel {self.channel}: led_count {self.led_count} out of range [0, {MAX_LEDS_PER_CHANNEL}]")
    return errors


@dataclass
class ChannelInstallation:
  schema_version: int = SCHEMA_VERSION
  channels: list[ChannelConfig] = field(default_factory=list)

  def validate(self) -> list[str]:
    errors = []
    for ch in self.channels:
      errors.extend(ch.validate())
    return errors

  def to_dict(self) -> dict:
    return {
      'schema_version': self.schema_version,
      'channels': [asdict(ch) for ch in self.channels],
    }

  def channels_api_dict(self) -> list[dict]:
    """Return channel list for API response."""
    return [asdict(ch) for ch in self.channels]


def synthesize_default_channels() -> ChannelInstallation:
  """Create default 8-channel config matching current hardware layout.

  First ACTIVE_OUTPUTS channels get LEDS_PER_CHANNEL LEDs each.
  Remaining channels get 0 (unused).
  """
  channels = []
  for i in range(8):
    led_count = LEDS_PER_CHANNEL if i < ACTIVE_OUTPUTS else 0
    channels.append(ChannelConfig(
      channel=i,
      color_order=CONTROLLER_WIRE_ORDER,
      led_count=led_count,
    ))
  return ChannelInstallation(channels=channels)


def migrate_strip_to_channel(data: dict) -> ChannelInstallation:
  """Migrate old strip-oriented installation.yaml to channel-oriented format.

  Aggregates strips by output_channel: sums LED counts, takes color_order
  from first strip in each channel.
  """
  channels = {i: ChannelConfig(channel=i) for i in range(8)}

  for s in data.get('strips', []):
    ch_num = s.get('output_channel', 0)
    if 0 <= ch_num < 8:
      ch = channels[ch_num]
      if s.get('enabled', True):
        ch.led_count += s.get('installed_led_count', 0)
        # Take color order from first strip we see on this channel
        if ch.color_order == 'BGR' or ch.led_count == s.get('installed_led_count', 0):
          ch.color_order = s.get('color_order', CONTROLLER_WIRE_ORDER)

  return ChannelInstallation(
    schema_version=SCHEMA_VERSION,
    channels=[channels[i] for i in range(8)],
  )


def load_installation(config_dir: Path) -> ChannelInstallation:
  """Load installation.yaml, migrating or synthesizing as needed."""
  path = config_dir / "installation.yaml"
  if path.exists():
    with open(path) as f:
      data = yaml.safe_load(f) or {}

    # Schema v2 = channel-oriented (current)
    if data.get('schema_version', 0) >= 2:
      return _parse_channels(data)

    # Schema v1 or unversioned = strip-oriented (legacy) — migrate
    if 'strips' in data:
      logger.info("Migrating strip-oriented installation.yaml to channel format")
      inst = migrate_strip_to_channel(data)
      save_installation(inst, config_dir)
      return inst

  # First boot: synthesize defaults
  inst = synthesize_default_channels()
  save_installation(inst, config_dir)
  logger.info("Synthesized default channel installation.yaml")
  return inst


def _parse_channels(data: dict) -> ChannelInstallation:
  """Parse channel-oriented installation.yaml."""
  channels = []
  for ch in data.get('channels', []):
    channels.append(ChannelConfig(
      channel=ch.get('channel', len(channels)),
      color_order=ch.get('color_order', CONTROLLER_WIRE_ORDER),
      led_count=ch.get('led_count', 0),
    ))
  # Pad to 8 channels if fewer
  while len(channels) < 8:
    channels.append(ChannelConfig(channel=len(channels)))
  return ChannelInstallation(
    schema_version=data.get('schema_version', SCHEMA_VERSION),
    channels=channels,
  )


def save_installation(config: ChannelInstallation, config_dir: Path):
  """Atomically save installation.yaml."""
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pi && PYTHONPATH=. pytest tests/test_channel_config.py -v`
Expected: all tests PASS

- [ ] **Step 5: Run full test suite**

Run: `cd pi && PYTHONPATH=. pytest tests/ -x -q --ignore=tests/test_matrix_rain_perf.py --ignore=tests/test_migrations.py`

Some existing tests may import from installation.py (the old `StripConfig`, `InstallationConfig`, `synthesize_default_installation`). If any fail, those imports need to be updated. The key consumers are:
- `pi/app/mapping/runtime_plan.py` — `compile_output_plan` takes an installation object and reads `.strips`. This will need a compatibility adapter or update in Task 2.
- `pi/app/main.py` — imports `load_installation`. Same function name so should work, but return type changed.
- `pi/app/setup/session.py` — will be deleted in Task 3.

For now, if tests fail due to old imports, note which ones and proceed — they'll be fixed in subsequent tasks.

- [ ] **Step 6: Commit**

```bash
git add pi/app/config/installation.py pi/tests/test_channel_config.py
git commit -m "feat: channel-oriented installation config with migration from strip format"
```

---

### Task 2: Update compile_output_plan for Channel Model

**Files:**
- Modify: `pi/app/mapping/runtime_plan.py`
- Modify: `pi/app/main.py`

The `compile_output_plan` function currently iterates over `installation.strips` (list of StripConfig). With the new channel model, installation has `.channels` (list of ChannelConfig). We need to bridge this: synthesize strip-like data from channels for the output plan compiler.

- [ ] **Step 1: Update compile_output_plan to accept ChannelInstallation**

In `pi/app/mapping/runtime_plan.py`, add a new function after the existing `compile_output_plan`:

```python
def compile_channel_plan(installation, controller: ControllerProfile) -> CompiledOutputPlan:
  """Compile a channel-oriented installation into an output plan.

  Each channel becomes one CompiledStripPlan entry. The channel's LED count
  is used directly (no strip pairing).
  """
  strips = []
  for ch in installation.channels:
    if ch.led_count == 0:
      continue
    swizzle = derive_precontroller_swizzle(
      controller.controller_wire_order,
      ch.color_order,
    )
    strips.append(CompiledStripPlan(
      strip_id=ch.channel,
      enabled=True,
      logical_order=ch.channel,
      output_channel=ch.channel,
      output_slot=0,
      output_offset=0,
      direction='bottom_to_top',
      installed_led_count=ch.led_count,
      color_order=ch.color_order,
      precontroller_swizzle=swizzle,
    ))

  active_channels = len(strips)
  max_leds = max((s.installed_led_count for s in strips), default=0)

  return CompiledOutputPlan(
    controller=controller,
    strips=tuple(strips),
    logical_width=active_channels,
    logical_height=max_leds,
    channels=active_channels,
    leds_per_channel=max_leds,
  )
```

- [ ] **Step 2: Update main.py to use new function**

In `pi/app/main.py`, change the import and call. Find:
```python
from .config.installation import load_installation, save_installation
```
And the `compile_output_plan` import. Update to:
```python
from .config.installation import load_installation, save_installation
```

Find the line:
```python
compiled_plan = compile_output_plan(installation, controller_profile)
```
Replace with:
```python
from .mapping.runtime_plan import compile_channel_plan
compiled_plan = compile_channel_plan(installation, controller_profile)
```

Also remove the `SetupSessionService` import and instantiation block (lines ~211-219) and the `setup_session_service` parameter from `create_app()`. Don't remove the `setup_session_service=` kwarg from `create_app` if it's used — check first and remove it from both caller and function signature.

- [ ] **Step 3: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/ -x -q --ignore=tests/test_matrix_rain_perf.py --ignore=tests/test_migrations.py`

- [ ] **Step 4: Commit**

```bash
git add pi/app/mapping/runtime_plan.py pi/app/main.py
git commit -m "feat: compile_channel_plan for channel-oriented installation"
```

---

### Task 3: Setup API Routes — Live Channel Config

**Files:**
- Rewrite: `pi/app/api/routes/setup.py`
- Modify: `pi/app/api/schemas.py`

- [ ] **Step 1: Add ChannelConfigRequest schema**

In `pi/app/api/schemas.py`, add:

```python
class ChannelConfigRequest(BaseModel):
    color_order: Optional[str] = None
    led_count: Optional[int] = None
```

- [ ] **Step 2: Rewrite setup routes**

Replace `pi/app/api/routes/setup.py` entirely:

```python
"""
Setup API routes — live channel configuration.

Each channel edit validates, recompiles the output plan, hot-applies
to the renderer, and persists to installation.yaml. No sessions.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import ChannelConfigRequest
from ...config.installation import (
  ChannelInstallation, save_installation, VALID_COLOR_ORDERS, MAX_LEDS_PER_CHANNEL,
)
from ...mapping.runtime_plan import compile_channel_plan

logger = logging.getLogger(__name__)


def create_router(deps, require_auth, broadcast_state) -> APIRouter:
    router = APIRouter(prefix="/api/setup", tags=["setup"])

    @router.get("/channels")
    async def get_channels():
        return {"channels": deps.installation.channels_api_dict()}

    @router.post("/channels/{n}", dependencies=[Depends(require_auth)])
    async def update_channel(n: int, req: ChannelConfigRequest):
        if not 0 <= n <= 7:
            raise HTTPException(400, f"Channel must be 0-7, got {n}")

        ch = deps.installation.channels[n]

        if req.color_order is not None:
            if req.color_order not in VALID_COLOR_ORDERS:
                raise HTTPException(422, f"Invalid color_order: {req.color_order}. Must be one of: {', '.join(sorted(VALID_COLOR_ORDERS))}")
            ch.color_order = req.color_order

        if req.led_count is not None:
            if not 0 <= req.led_count <= MAX_LEDS_PER_CHANNEL:
                raise HTTPException(422, f"led_count must be 0-{MAX_LEDS_PER_CHANNEL}, got {req.led_count}")
            ch.led_count = req.led_count

        # Recompile and hot-apply
        plan = compile_channel_plan(deps.installation, deps.controller_profile)
        deps.renderer.apply_output_plan(plan)

        # Persist
        save_installation(deps.installation, deps.config_dir)

        logger.info(f"Channel {n} updated: {ch.color_order}, {ch.led_count} LEDs")
        return {"status": "ok", "channels": deps.installation.channels_api_dict()}

    return router
```

- [ ] **Step 3: Update AppDeps to include installation, controller_profile, config_dir**

Check `pi/app/api/deps.py` for the `AppDeps` class. Add `installation`, `controller_profile`, and `config_dir` fields if not already present. These need to be passed from `main.py` through `create_app()`.

In `pi/app/api/server.py`, update `create_app` to accept and pass these. In `main.py`, pass them when calling `create_app`.

- [ ] **Step 4: Update server.py router wiring**

In `pi/app/api/server.py`, the setup router currently gets `deps, require_auth, broadcast_state`. Update the `setup.create_router(...)` call to match the new signature. Remove the old session-service dependency.

- [ ] **Step 5: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/ -x -q --ignore=tests/test_matrix_rain_perf.py --ignore=tests/test_migrations.py`

- [ ] **Step 6: Commit**

```bash
git add pi/app/api/routes/setup.py pi/app/api/schemas.py pi/app/api/deps.py pi/app/api/server.py pi/app/main.py
git commit -m "feat: live channel config API — GET/POST channels with immediate apply"
```

---

### Task 4: Frontend — Channel Config Table

**Files:**
- Modify: `pi/app/ui/static/index.html` (setup section, lines ~281-307)
- Modify: `pi/app/ui/static/js/app.js` (setup section, lines ~729-975)
- Modify: `pi/app/ui/static/css/app.css` (add channel table styles)

- [ ] **Step 1: Replace setup HTML**

In `pi/app/ui/static/index.html`, replace the `<!-- Setup section -->` div (lines ~281-307) with:

```html
          <!-- Setup section -->
          <div id="system-setup" class="system-section hidden">
            <div class="help-panel collapsed" data-tab="system-setup">
              <button class="help-toggle" aria-expanded="false">
                <span class="help-icon">?</span> How to use this page
              </button>
              <div class="help-content" hidden>
                <p>Configure your OctoWS2811 output channels.</p>
                <p>Each channel can drive up to 1100 LEDs. Set the color order to match your LED strips (usually BGR for WS2812B). Set LED count to 0 for unused channels. Changes apply immediately.</p>
              </div>
            </div>
            <h3>Channel Configuration</h3>
            <div id="channel-status" class="status-msg"></div>
            <table id="channel-table">
              <thead>
                <tr>
                  <th>Ch</th>
                  <th>Color Order</th>
                  <th>LED Count</th>
                </tr>
              </thead>
              <tbody id="channel-rows"></tbody>
            </table>
          </div>
```

- [ ] **Step 2: Add channel table CSS**

In `pi/app/ui/static/css/app.css`, find the existing strip-card styles (search for `.strip-card`). Remove all `.strip-card`, `.strip-card-header`, `.strip-card-body`, `.strip-field`, `.strip-summary`, `.expand-icon`, `.has-errors`, `.invalid` styles. Add:

```css
#channel-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
}

#channel-table th {
  text-align: left;
  padding: 8px;
  font-size: 12px;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border);
}

#channel-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
}

#channel-table tr.unused td {
  opacity: 0.4;
}

#channel-table select,
#channel-table input[type="number"] {
  width: 100%;
  padding: 8px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 14px;
}

#channel-table .ch-label {
  font-weight: bold;
  font-size: 16px;
  text-align: center;
}

.status-msg {
  font-size: 13px;
  color: var(--success);
  min-height: 20px;
  margin-bottom: 8px;
}

.status-msg.error {
  color: var(--danger);
}
```

- [ ] **Step 3: Replace setup JavaScript**

In `pi/app/ui/static/js/app.js`, replace the entire `// --- Setup ---` section (lines ~729-975, from `// --- Setup ---` to just before `// --- Brightness ---`) with:

```javascript
// --- Setup ---

async function loadChannelConfig() {
  const data = await api('GET', '/api/setup/channels');
  if (!data || !data.channels) return;

  const tbody = document.getElementById('channel-rows');
  tbody.innerHTML = '';

  const colorOrders = ['RGB','RBG','GRB','GBR','BRG','BGR'];

  for (const ch of data.channels) {
    const tr = document.createElement('tr');
    if (ch.led_count === 0) tr.className = 'unused';
    tr.dataset.channel = ch.channel;

    const colorOpts = colorOrders.map(o =>
      `<option value="${o}" ${o === ch.color_order ? 'selected' : ''}>${o}</option>`
    ).join('');

    tr.innerHTML = `
      <td class="ch-label">${ch.channel}</td>
      <td><select data-channel="${ch.channel}" data-field="color_order">${colorOpts}</select></td>
      <td><input type="number" data-channel="${ch.channel}" data-field="led_count" value="${ch.led_count}" min="0" max="1100" step="1"></td>
    `;
    tbody.appendChild(tr);
  }

  // Attach change handlers
  tbody.querySelectorAll('select, input').forEach(el => {
    let debounce = null;
    el.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => updateChannel(el), 200);
    });
    el.addEventListener('change', () => {
      clearTimeout(debounce);
      updateChannel(el);
    });
  });
}

async function updateChannel(el) {
  const ch = parseInt(el.dataset.channel);
  const field = el.dataset.field;
  const value = field === 'led_count' ? parseInt(el.value) : el.value;

  const body = {};
  body[field] = value;

  const status = document.getElementById('channel-status');
  const result = await api('POST', `/api/setup/channels/${ch}`, body);
  if (result && result.status === 'ok') {
    status.textContent = `Channel ${ch} updated`;
    status.className = 'status-msg';
    // Update unused styling
    const row = el.closest('tr');
    if (row) {
      const ledInput = row.querySelector('[data-field="led_count"]');
      const count = ledInput ? parseInt(ledInput.value) : 0;
      row.classList.toggle('unused', count === 0);
    }
    // Clear status after 2s
    setTimeout(() => { status.textContent = ''; }, 2000);
  } else {
    status.textContent = 'Error saving channel config';
    status.className = 'status-msg error';
  }
}

function initSetup() {
  // Load channels when setup section becomes visible
  // (loaded via subnav click handler that already exists)
}
```

Also update the subnav click handler. Find the line (around line 722):
```javascript
if (btn.dataset.section === 'system-setup') loadSetupStatus();
```
Replace with:
```javascript
if (btn.dataset.section === 'system-setup') loadChannelConfig();
```

- [ ] **Step 4: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/ -x -q --ignore=tests/test_matrix_rain_perf.py --ignore=tests/test_migrations.py`

- [ ] **Step 5: Commit**

```bash
git add pi/app/ui/static/index.html pi/app/ui/static/js/app.js pi/app/ui/static/css/app.css
git commit -m "feat: channel config table UI — live color order and LED count per channel"
```

---

### Task 5: Clean Up — Remove Session System

**Files:**
- Delete: `pi/app/setup/session.py`
- Modify: `pi/app/main.py` (remove session service imports/usage)
- Modify: `pi/app/api/server.py` (remove session service from create_app if still referenced)

- [ ] **Step 1: Remove session service file**

```bash
rm pi/app/setup/session.py
```

If `pi/app/setup/__init__.py` imports from session.py, update it. If the directory is now empty except for `__init__.py`, leave it (the setup package may be used for future mapping work).

- [ ] **Step 2: Remove any remaining session references in main.py and server.py**

Search for `SetupSessionService`, `setup_session_service`, `setup_service` in main.py and server.py. Remove all imports, instantiation, and passing. The `create_app` function should no longer accept or use `setup_session_service`.

- [ ] **Step 3: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/ -x -q --ignore=tests/test_matrix_rain_perf.py --ignore=tests/test_migrations.py`

If any tests import from `setup.session` or test the old session flow, delete those test files.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove session-based setup system"
```

---

### Task 6: Deploy and Verify

**Files:** None (deployment only)

- [ ] **Step 1: Deploy to Pi**

```bash
bash pi/scripts/deploy.sh ledfanatic.local
```

- [ ] **Step 2: Verify channel config API**

```bash
ssh jim@ledfanatic.local "curl -s http://localhost:80/api/setup/channels | python3 -m json.tool"
```

Expected: 8 channels with color_order and led_count for each.

- [ ] **Step 3: Test live update**

```bash
ssh jim@ledfanatic.local "curl -s -X POST http://localhost:80/api/setup/channels/0 -H 'Content-Type: application/json' -d '{\"color_order\": \"RGB\", \"led_count\": 300}' | python3 -m json.tool"
```

Expected: `{"status": "ok", "channels": [...]}` with channel 0 showing RGB and 300.

Verify it persisted:
```bash
ssh jim@ledfanatic.local "sudo cat /opt/pillar/config/installation.yaml"
```

- [ ] **Step 4: Reset to correct values**

```bash
ssh jim@ledfanatic.local "curl -s -X POST http://localhost:80/api/setup/channels/0 -H 'Content-Type: application/json' -d '{\"color_order\": \"BGR\", \"led_count\": 344}'"
```

- [ ] **Step 5: Open UI and verify**

Open the UI in a browser. Go to System > Setup. Verify the channel table renders with 8 rows. Change a color order dropdown and confirm the status shows "Channel N updated".
