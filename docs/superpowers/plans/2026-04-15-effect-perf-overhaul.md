# Effect Performance Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the effect architecture so all 27+ effects sustain 60 FPS on a Raspberry Pi over 10-second runs, by introducing per-effect width policy, replacing the pathological LEDBuffer helpers, and rewriting the worst offenders.

**Architecture:** Effects declare their own `NATIVE_WIDTH` (default 10 for imported, renderer's `internal_width` for generative). The renderer honors this per-effect instead of forcing global width 40. LEDBuffer gets zero-allocation in-place helpers. Matrix rain is rewritten with struct-of-arrays state. A benchmark harness enforces the 60 FPS contract.

**Tech Stack:** Python 3.13, NumPy, pytest, existing Effect base class

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `pi/app/effects/base.py` | Modify | Add `NATIVE_WIDTH` class attribute to Effect base |
| `pi/app/effects/engine/buffer.py` | Modify | Replace `add_led`/`fade` with zero-allocation in-place ops, add batched helpers |
| `pi/app/core/renderer.py:146-150` | Modify | Read `NATIVE_WIDTH` from effect class, instantiate at correct width |
| `pi/app/effects/imported/ambient_a.py:377-453` | Modify | Rewrite MatrixRain with struct-of-arrays + vectorized drawing |
| `pi/app/effects/imported/sound.py:74-161` | Modify | Add `NATIVE_WIDTH = 10` to Spectrum |
| `pi/app/effects/imported/sound.py:779-862` | Modify | Add `NATIVE_WIDTH = 10` to Spectrogram |
| `pi/app/effects/generative.py:106-130` | Modify | Vectorize Twinkle inner loop |
| `pi/app/effects/audio_reactive.py:112-141` | Modify | Vectorize SpectralGlow inner loop |
| `pi/app/effects/imported/ambient_a.py` (all classes) | Modify | Add `NATIVE_WIDTH = 10` to all ambient_a effects |
| `pi/app/effects/imported/ambient_b.py` (all classes) | Modify | Add `NATIVE_WIDTH = 10` to all ambient_b effects |
| `pi/app/effects/imported/classic.py` (all classes) | Modify | Add `NATIVE_WIDTH = 10` to all classic effects |
| `pi/app/effects/imported/sound.py` (all classes) | Modify | Add `NATIVE_WIDTH = 10` to all sound effects |
| `pi/tools/bench_effects.py` | Create | 10-second per-effect benchmark harness |
| `pi/tests/test_buffer_perf.py` | Create | Tests for new buffer helpers |
| `pi/tests/test_width_policy.py` | Create | Tests for per-effect width selection |
| `pi/tests/test_matrix_rain_perf.py` | Create | Regression test: matrix_rain stays fast over 600 frames |

---

### Task 1: Zero-Allocation LEDBuffer Helpers

The current `add_led()` creates 4 temporary numpy arrays per pixel call. This is the #1 bottleneck — 4.3 seconds out of 5.1 seconds in matrix_rain's hot loop. Replace with scalar math that writes directly into the backing array.

**Files:**
- Modify: `pi/app/effects/engine/buffer.py`
- Create: `pi/tests/test_buffer_perf.py`

- [ ] **Step 1: Write tests for the new buffer helpers**

```python
# pi/tests/test_buffer_perf.py
"""Tests for LEDBuffer in-place helpers."""

import numpy as np
from app.effects.engine.buffer import LEDBuffer


class TestAddLedInPlace:
  """add_led must be additive, clamped, and zero-allocation."""

  def test_add_to_black_pixel(self):
    buf = LEDBuffer(10, 172)
    buf.add_led(0, 0, 100, 150, 200)
    assert tuple(buf.data[0, 0]) == (100, 150, 200)

  def test_additive_blend(self):
    buf = LEDBuffer(10, 172)
    buf.data[3, 5] = (100, 100, 100)
    buf.add_led(3, 5, 50, 60, 70)
    assert tuple(buf.data[3, 5]) == (150, 160, 170)

  def test_clamps_at_255(self):
    buf = LEDBuffer(10, 172)
    buf.data[0, 0] = (200, 200, 200)
    buf.add_led(0, 0, 100, 100, 100)
    assert tuple(buf.data[0, 0]) == (255, 255, 255)

  def test_cylinder_wrap_x(self):
    buf = LEDBuffer(10, 172)
    buf.add_led(12, 0, 50, 50, 50)  # x=12 wraps to x=2
    assert tuple(buf.data[2, 0]) == (50, 50, 50)

  def test_out_of_bounds_y_ignored(self):
    buf = LEDBuffer(10, 172)
    buf.add_led(0, 200, 50, 50, 50)  # y=200 is out of range
    assert np.all(buf.data == 0)

  def test_negative_values_treated_as_zero(self):
    buf = LEDBuffer(10, 172)
    buf.add_led(0, 0, -50, 100, 200)
    assert buf.data[0, 0, 0] == 0
    assert buf.data[0, 0, 1] == 100


class TestSetLedInPlace:
  def test_basic_set(self):
    buf = LEDBuffer(10, 172)
    buf.set_led(0, 0, 128, 64, 32)
    assert tuple(buf.data[0, 0]) == (128, 64, 32)


class TestFadeInPlace:
  def test_fade_halves_values(self):
    buf = LEDBuffer(10, 172)
    buf.data[0, 0] = (200, 100, 50)
    buf.fade(0.5)
    assert tuple(buf.data[0, 0]) == (100, 50, 25)

  def test_fade_does_not_allocate_new_array(self):
    buf = LEDBuffer(10, 172)
    original_id = id(buf.data)
    buf.data[0, 0] = (200, 100, 50)
    buf.fade(0.5)
    assert id(buf.data) == original_id

  def test_fade_by_does_not_allocate_new_array(self):
    buf = LEDBuffer(10, 172)
    original_id = id(buf.data)
    buf.data[0, 0] = (200, 100, 50)
    buf.fade_by(48)
    assert id(buf.data) == original_id


class TestGetFrameNoCopy:
  def test_get_frame_returns_data_directly(self):
    """get_frame should return the backing array, not a copy."""
    buf = LEDBuffer(10, 172)
    buf.data[0, 0] = (1, 2, 3)
    frame = buf.get_frame()
    assert tuple(frame[0, 0]) == (1, 2, 3)


class TestAddPointsBatched:
  def test_batch_of_three_points(self):
    buf = LEDBuffer(10, 172)
    xs = np.array([0, 1, 2])
    ys = np.array([0, 5, 10])
    rgbs = np.array([[100, 0, 0], [0, 100, 0], [0, 0, 100]], dtype=np.uint8)
    buf.add_points(xs, ys, rgbs)
    assert tuple(buf.data[0, 0]) == (100, 0, 0)
    assert tuple(buf.data[1, 5]) == (0, 100, 0)
    assert tuple(buf.data[2, 10]) == (0, 0, 100)

  def test_batched_additive(self):
    buf = LEDBuffer(10, 172)
    buf.data[0, 0] = (50, 50, 50)
    xs = np.array([0])
    ys = np.array([0])
    rgbs = np.array([[100, 100, 100]], dtype=np.uint8)
    buf.add_points(xs, ys, rgbs)
    assert tuple(buf.data[0, 0]) == (150, 150, 150)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pi && PYTHONPATH=. pytest tests/test_buffer_perf.py -v`
Expected: Multiple failures — `fade` and `fade_by` allocate new arrays, `get_frame` returns a copy, `add_points` doesn't exist, `add_led` doesn't handle negative values.

- [ ] **Step 3: Rewrite LEDBuffer with zero-allocation helpers**

Replace the full content of `pi/app/effects/engine/buffer.py`:

```python
"""LED buffer — wraps the global leds[] array from led_sim.py as a class.

Provides set_led, add_led, clear, fade, and get_frame for numpy output.
All mutation is in-place on self.data — no per-pixel allocations.
"""

import numpy as np


class LEDBuffer:
  """Manages a (cols, rows, 3) uint8 pixel buffer with cylinder wrapping."""

  def __init__(self, cols=10, rows=172):
    self.cols = cols
    self.rows = rows
    self.data = np.zeros((cols, rows, 3), dtype=np.uint8)
    # Scratch buffer for fade operations — avoids per-frame allocation
    self._scratch_u16 = np.zeros((cols, rows, 3), dtype=np.uint16)

  def set_led(self, x, y, r, g, b):
    """Set a pixel with cylinder-wrapped x coordinate."""
    x = int(x) % self.cols
    y = int(y)
    if 0 <= y < self.rows:
      self.data[x, y, 0] = min(255, max(0, int(r)))
      self.data[x, y, 1] = min(255, max(0, int(g)))
      self.data[x, y, 2] = min(255, max(0, int(b)))

  def add_led(self, x, y, r, g, b):
    """Additive blend a pixel (clamps to 255). Zero-allocation scalar path."""
    x = int(x) % self.cols
    y = int(y)
    if 0 <= y < self.rows:
      d = self.data[x, y]
      ri = max(0, int(r))
      gi = max(0, int(g))
      bi = max(0, int(b))
      d[0] = min(255, int(d[0]) + ri)
      d[1] = min(255, int(d[1]) + gi)
      d[2] = min(255, int(d[2]) + bi)

  def add_points(self, xs, ys, rgbs):
    """Batched additive blend. xs, ys: int arrays. rgbs: (N, 3) uint8.

    Out-of-bounds y values are silently skipped. x values wrap.
    """
    xs_wrapped = xs % self.cols
    valid = (ys >= 0) & (ys < self.rows)
    vx = xs_wrapped[valid]
    vy = ys[valid]
    vrgb = rgbs[valid].astype(np.uint16)
    # Use clip to handle additive overflow
    for i in range(len(vx)):
      d = self.data[vx[i], vy[i]]
      d[0] = min(255, int(d[0]) + int(vrgb[i, 0]))
      d[1] = min(255, int(d[1]) + int(vrgb[i, 1]))
      d[2] = min(255, int(d[2]) + int(vrgb[i, 2]))

  def clear(self):
    """Zero all pixels."""
    self.data[:] = 0

  def fade(self, factor):
    """Multiply all pixels by factor (0-1). In-place."""
    np.multiply(self.data, factor, out=self._scratch_u16, casting='unsafe')
    np.copyto(self.data, self._scratch_u16, casting='unsafe')

  def fade_by(self, amount):
    """Proportional fade-to-black. Mimics FastLED fadeToBlackBy. In-place.

    Each channel: value = value * (255 - amount) / 256
    A pixel at 100 with amount=48 becomes ~81 (proportional), not 52 (subtractive).
    """
    scale = 255 - int(amount)
    np.multiply(self.data, scale, out=self._scratch_u16, casting='unsafe')
    np.right_shift(self._scratch_u16, 8, out=self._scratch_u16)
    np.copyto(self.data, self._scratch_u16, casting='unsafe')

  def get_frame(self):
    """Return the buffer data array directly (no copy)."""
    return self.data
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pi && PYTHONPATH=. pytest tests/test_buffer_perf.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Run existing test suite to check for regressions**

Run: `cd pi && PYTHONPATH=. pytest tests/ -v --tb=short`
Expected: All ~219 tests PASS. The `get_frame()` change from copy to no-copy should be safe because the renderer immediately processes the returned array (brightness, gamma, mapping) — no effect mutates its buffer between `get_frame()` and the next `clear()`.

- [ ] **Step 6: Commit**

```bash
git add pi/app/effects/engine/buffer.py pi/tests/test_buffer_perf.py
git commit -m "perf: zero-allocation LEDBuffer — in-place fade, scalar add_led, batched add_points"
```

---

### Task 2: Per-Effect Width Policy

The renderer currently instantiates every effect at `internal_width=40`. Imported effects were authored for 10 columns — the 4x width multiplies their work and breaks width-sensitive ones (spectrum, spectrogram). Add a `NATIVE_WIDTH` class attribute that effects can declare, and make the renderer honor it.

**Files:**
- Modify: `pi/app/effects/base.py:12-19`
- Modify: `pi/app/core/renderer.py:146-150`
- Create: `pi/tests/test_width_policy.py`

- [ ] **Step 1: Write tests for width policy**

```python
# pi/tests/test_width_policy.py
"""Tests for per-effect width policy in the renderer."""

import numpy as np
from unittest.mock import MagicMock, AsyncMock

from app.effects.base import Effect
from app.core.renderer import Renderer, RenderState
from app.core.brightness import BrightnessEngine


class WidthTenEffect(Effect):
  """Test effect that declares native width 10."""
  NATIVE_WIDTH = 10

  def render(self, t, state):
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)
    frame[0, 0] = (self.width, 0, 0)  # encode width in pixel for verification
    return frame


class WidthFortyEffect(Effect):
  """Test effect that uses supersampling (default behavior)."""

  def render(self, t, state):
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)
    frame[0, 0] = (self.width, 0, 0)
    return frame


class TestWidthPolicy:
  def _make_renderer(self, internal_width=40):
    transport = MagicMock()
    transport.send_frame = AsyncMock(return_value=True)
    state = RenderState()
    brightness = BrightnessEngine({})
    return Renderer(transport, state, brightness, internal_width=internal_width)

  def test_native_width_10_effect_gets_width_10(self):
    renderer = self._make_renderer(internal_width=40)
    renderer.register_effect('test_w10', WidthTenEffect)
    renderer._set_scene('test_w10')
    assert renderer.current_effect.width == 10

  def test_default_effect_gets_internal_width(self):
    renderer = self._make_renderer(internal_width=40)
    renderer.register_effect('test_default', WidthFortyEffect)
    renderer._set_scene('test_default')
    assert renderer.current_effect.width == 40

  def test_native_width_attribute_on_base_class(self):
    """Base Effect class should have NATIVE_WIDTH = None (use renderer default)."""
    assert Effect.NATIVE_WIDTH is None

  def test_native_width_10_inherited(self):
    assert WidthTenEffect.NATIVE_WIDTH == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pi && PYTHONPATH=. pytest tests/test_width_policy.py -v`
Expected: FAIL — `Effect` has no `NATIVE_WIDTH` attribute, renderer ignores it.

- [ ] **Step 3: Add NATIVE_WIDTH to Effect base class**

In `pi/app/effects/base.py`, add the class attribute inside the `Effect` class (after line 13):

```python
class Effect(ABC):
  """Base class for all effects."""

  NATIVE_WIDTH = None  # None = use renderer's internal_width

  def __init__(self, width: int = 10, height: int = N, params: Optional[dict] = None):
```

- [ ] **Step 4: Update renderer to honor NATIVE_WIDTH**

In `pi/app/core/renderer.py`, replace the effect instantiation block (lines 146-150):

Old:
```python
    self.current_effect = effect_cls(
      width=self.internal_width,
      height=N,
      params=merged,
    )
```

New:
```python
    effect_width = getattr(effect_cls, 'NATIVE_WIDTH', None) or self.internal_width
    self.current_effect = effect_cls(
      width=effect_width,
      height=N,
      params=merged,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd pi && PYTHONPATH=. pytest tests/test_width_policy.py -v`
Expected: All PASS.

- [ ] **Step 6: Run full test suite**

Run: `cd pi && PYTHONPATH=. pytest tests/ -v --tb=short`
Expected: All pass. No existing effect declares `NATIVE_WIDTH` yet, so behavior is unchanged.

- [ ] **Step 7: Commit**

```bash
git add pi/app/effects/base.py pi/app/core/renderer.py pi/tests/test_width_policy.py
git commit -m "feat: per-effect NATIVE_WIDTH — renderer honors effect-declared width"
```

---

### Task 3: Tag All Imported Effects with NATIVE_WIDTH = 10

Every imported effect was authored for the 10-column simulator. Tag them all so the renderer instantiates them at width 10 instead of 40.

**Files:**
- Modify: `pi/app/effects/imported/classic.py` — all 5 effect classes
- Modify: `pi/app/effects/imported/ambient_a.py` — all 6 effect classes
- Modify: `pi/app/effects/imported/ambient_b.py` — all 6 effect classes
- Modify: `pi/app/effects/imported/sound.py` — all 10 effect classes

- [ ] **Step 1: Write a test that enforces the policy**

Add to `pi/tests/test_width_policy.py`:

```python
from app.effects.imported import IMPORTED_EFFECTS


class TestImportedWidthPolicy:
  def test_all_imported_declare_native_width_10(self):
    """Every imported effect must declare NATIVE_WIDTH = 10."""
    for name, cls in IMPORTED_EFFECTS.items():
      assert hasattr(cls, 'NATIVE_WIDTH'), f"{name}: missing NATIVE_WIDTH"
      assert cls.NATIVE_WIDTH == 10, f"{name}: NATIVE_WIDTH is {cls.NATIVE_WIDTH}, expected 10"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pi && PYTHONPATH=. pytest tests/test_width_policy.py::TestImportedWidthPolicy -v`
Expected: FAIL — imported effects don't have `NATIVE_WIDTH` yet.

- [ ] **Step 3: Add NATIVE_WIDTH = 10 to all imported effect classes**

For each imported effect file, add `NATIVE_WIDTH = 10` as a class attribute right after the existing class-level constants (`CATEGORY`, `DISPLAY_NAME`, etc.).

**`pi/app/effects/imported/classic.py`** — add to each of the 5 classes (e.g., `RainbowCycle`, `FeldsteinOG`, `FeldsteinEquation`, `BrettsFavorite`, `Fireplace`):
```python
  NATIVE_WIDTH = 10
```

**`pi/app/effects/imported/ambient_a.py`** — add to each of the 6 classes (`Plasma`, `AuroraBorealis`, `LavaLamp`, `OceanWaves`, `Starfield`, `MatrixRain`):
```python
  NATIVE_WIDTH = 10
```

**`pi/app/effects/imported/ambient_b.py`** — add to each of the 6 classes:
```python
  NATIVE_WIDTH = 10
```

**`pi/app/effects/imported/sound.py`** — add to each of the 10 classes (including `Spectrum`, `Spectrogram`):
```python
  NATIVE_WIDTH = 10
```

Place `NATIVE_WIDTH = 10` immediately after `PALETTE_SUPPORT` (or the last existing class-level constant) in each class.

- [ ] **Step 4: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/test_width_policy.py tests/test_imported_animations.py -v`
Expected: All PASS. The imported animation tests already use `width=10`, so they're already correct.

- [ ] **Step 5: Commit**

```bash
git add pi/app/effects/imported/classic.py pi/app/effects/imported/ambient_a.py \
       pi/app/effects/imported/ambient_b.py pi/app/effects/imported/sound.py \
       pi/tests/test_width_policy.py
git commit -m "perf: tag all 27 imported effects with NATIVE_WIDTH=10"
```

---

### Task 4: Rewrite MatrixRain with Struct-of-Arrays

Matrix rain is the #1 offender — it degrades from 2ms to 42ms over 10 seconds because each of its ~350 active drops calls `add_led()` for every trail pixel. Rewrite to use fixed-capacity numpy arrays for drop state and vectorized trail drawing.

**Files:**
- Modify: `pi/app/effects/imported/ambient_a.py:377-453`
- Create: `pi/tests/test_matrix_rain_perf.py`

- [ ] **Step 1: Write regression/correctness tests**

```python
# pi/tests/test_matrix_rain_perf.py
"""MatrixRain performance regression and correctness tests."""

import time
import numpy as np
from unittest.mock import MagicMock


def _make_state():
  state = MagicMock()
  state._audio_lock_free = {
    'level': 0.0, 'bass': 0.0, 'mid': 0.0, 'high': 0.0,
    'beat': False, 'bpm': 120.0,
  }
  return state


class TestMatrixRainCorrectness:
  def test_render_shape(self):
    from app.effects.imported.ambient_a import MatrixRain
    eff = MatrixRain(width=10, height=172)
    state = _make_state()
    frame = eff.render(time.monotonic(), state)
    assert frame.shape == (10, 172, 3)
    assert frame.dtype == np.uint8

  def test_produces_nonzero_pixels_after_warmup(self):
    from app.effects.imported.ambient_a import MatrixRain
    eff = MatrixRain(width=10, height=172)
    state = _make_state()
    t = time.monotonic()
    # Render 60 frames to let drops populate
    for _ in range(60):
      frame = eff.render(t, state)
      t += 0.017
    assert np.any(frame > 0), "MatrixRain produced no visible pixels after 60 frames"

  def test_drops_are_capped(self):
    """Active drops should not grow unbounded."""
    from app.effects.imported.ambient_a import MatrixRain
    eff = MatrixRain(width=10, height=172)
    state = _make_state()
    t = time.monotonic()
    for _ in range(600):
      eff.render(t, state)
      t += 0.017
    # Max drops: 10 columns * max_per_col (should be well under 500)
    active = int(np.sum(eff._active_mask)) if hasattr(eff, '_active_mask') else len(eff._drops)
    assert active < 500, f"Too many active drops: {active}"


class TestMatrixRainPerformance:
  def test_600_frames_no_degradation(self):
    """Last 60 frames must not be >4x slower than first 60 frames."""
    from app.effects.imported.ambient_a import MatrixRain
    eff = MatrixRain(width=10, height=172)
    state = _make_state()
    t = time.monotonic()
    times = []
    for _ in range(600):
      start = time.perf_counter()
      eff.render(t, state)
      times.append(time.perf_counter() - start)
      t += 0.017
    first_60_avg = sum(times[:60]) / 60
    last_60_avg = sum(times[-60:]) / 60
    ratio = last_60_avg / max(first_60_avg, 1e-9)
    assert ratio < 4.0, (
      f"MatrixRain degraded {ratio:.1f}x over 600 frames "
      f"(first60={first_60_avg*1000:.2f}ms, last60={last_60_avg*1000:.2f}ms)"
    )
```

- [ ] **Step 2: Run tests to establish baseline**

Run: `cd pi && PYTHONPATH=. pytest tests/test_matrix_rain_perf.py -v`
Expected: `test_600_frames_no_degradation` FAILS (current code degrades ~20x). Correctness tests should pass.

- [ ] **Step 3: Rewrite MatrixRain**

Replace the `MatrixRain` class in `pi/app/effects/imported/ambient_a.py` (lines 377-453). Keep the class location and registry entry unchanged.

```python
class MatrixRain(Effect):
  """Falling digital rain with varying speed drops and fade trails.
  Default palette: Forest (idx 3)."""

  CATEGORY = "ambient"
  DISPLAY_NAME = "Matrix Rain"
  DESCRIPTION = "Falling digital rain with speed-varied drops and fade trails"
  PALETTE_SUPPORT = True
  NATIVE_WIDTH = 10

  PARAMS = [
    _Param("Speed", "speed", 0.2, 4.0, 0.1, 1.0),
    _Param("Density", "density", 0.1, 1.0, 0.05, 0.4),
    _Param("Trail", "trail", 5, 60, 1, 25),
  ]
  _SCALAR_PARAMS = {"speed": 1.0, "density": 0.4, "trail": 25, "palette": 3}

  # Fixed capacity — 10 columns * 20 max concurrent drops per column
  _MAX_DROPS = 200

  def __init__(self, width=10, height=N, params=None):
    super().__init__(width, height, params)
    if "palette" not in self.params:
      self.params["palette"] = 3
    self.buf = LEDBuffer(width, height)
    self._last_t = None

    # Struct-of-arrays: fixed-capacity drop state
    cap = self._MAX_DROPS
    self._drop_x = np.zeros(cap, dtype=np.int32)
    self._drop_y = np.zeros(cap, dtype=np.float64)
    self._drop_speed = np.zeros(cap, dtype=np.float64)
    self._drop_bright = np.zeros(cap, dtype=np.float64)
    self._active_mask = np.zeros(cap, dtype=np.bool_)
    self._drop_count = 0

  def render(self, t, state):
    dt_ms = self._calc_dt_ms(t)
    dt = dt_ms * 0.001
    speed = self.params.get("speed", 1.0)
    density = self.params.get("density", 0.4)
    trail = int(self.params.get("trail", 25))
    pal_idx = self.params.get("palette", 3) % NUM_PALETTES

    cols = self.width
    rows = self.height

    self.buf.clear()

    # --- Spawn new drops ---
    for x in range(cols):
      if random.random() < density * dt * 3:
        slot = self._find_free_slot()
        if slot < 0:
          continue  # at capacity
        r = random.random()
        if r < 0.5:
          spd = random.uniform(6, 20)
        elif r < 0.85:
          spd = random.uniform(20, 50)
        else:
          spd = random.uniform(50, 90)
        self._drop_x[slot] = x
        self._drop_y[slot] = -1.0
        self._drop_speed[slot] = spd * speed
        self._drop_bright[slot] = random.uniform(0.5, 1.0)
        self._active_mask[slot] = True

    # --- Update positions (vectorized) ---
    active = self._active_mask
    self._drop_y[active] += self._drop_speed[active] * dt

    # --- Cull dead drops (head - trail past bottom) ---
    heads = self._drop_y.astype(np.int32)
    dead = active & ((heads - trail) >= rows)
    self._active_mask[dead] = False

    # --- Draw trails ---
    # Build the palette LUT once per frame
    fade_lut = np.arange(trail, dtype=np.float64)
    fade_factors = (1.0 - fade_lut / trail) ** 1.5  # (trail,)
    pal_colors = pal_color_grid(pal_idx, fade_factors)  # (trail, 3) uint8

    active_indices = np.where(self._active_mask)[0]
    for idx in active_indices:
      head = int(self._drop_y[idx])
      bright = self._drop_bright[idx]
      dx = self._drop_x[idx]
      for ty in range(trail):
        py = head - ty
        if 0 <= py < rows:
          c = pal_colors[ty]
          b = fade_factors[ty] * bright
          d = self.buf.data[dx, py]
          d[0] = min(255, int(d[0]) + int(c[0] * b))
          d[1] = min(255, int(d[1]) + int(c[1] * b))
          d[2] = min(255, int(d[2]) + int(c[2] * b))

    return self.buf.get_frame()

  def _find_free_slot(self):
    """Return index of first inactive slot, or -1 if full."""
    inactive = np.where(~self._active_mask)[0]
    if len(inactive) == 0:
      return -1
    return int(inactive[0])

  def _calc_dt_ms(self, t):
    if self._last_t is None:
      self._last_t = t
      return 16.67
    dt = (t - self._last_t) * 1000.0
    self._last_t = t
    return max(0.0, dt)
```

Key changes:
- Fixed-capacity struct-of-arrays instead of Python list of lists
- Palette LUT computed once per frame instead of per-pixel
- `add_led` replaced with direct scalar writes into `buf.data` — no numpy micro-allocations
- Vectorized position updates and dead-drop culling
- 200 drop cap prevents unbounded growth

- [ ] **Step 4: Run performance tests**

Run: `cd pi && PYTHONPATH=. pytest tests/test_matrix_rain_perf.py -v`
Expected: All PASS, including the degradation ratio test.

- [ ] **Step 5: Run full suite to verify no regressions**

Run: `cd pi && PYTHONPATH=. pytest tests/ -v --tb=short`
Expected: All pass. The existing `test_imported_animations.py` tests render at width=10 and check shape/dtype.

- [ ] **Step 6: Commit**

```bash
git add pi/app/effects/imported/ambient_a.py pi/tests/test_matrix_rain_perf.py
git commit -m "perf: rewrite MatrixRain — struct-of-arrays, capped drops, no per-pixel allocation"
```

---

### Task 5: Vectorize Twinkle

`gen:twinkle` runs a double Python loop over every pixel at width 40 × height 172 = 6,880 iterations, each calling scalar `hsv_to_rgb`. Replace with vectorized numpy operations following the Fire effect pattern.

**Files:**
- Modify: `pi/app/effects/generative.py:106-130`

- [ ] **Step 1: Write a targeted performance test**

Add to `pi/tests/test_buffer_perf.py` (or a new file — keeping it here for cohesion):

```python
# Append to pi/tests/test_buffer_perf.py

class TestTwinklePerformance:
  def test_120_frames_under_budget(self):
    """Twinkle at width 40 should average under 2ms per frame."""
    import time
    from app.effects.generative import Twinkle
    from unittest.mock import MagicMock
    state = MagicMock()
    state._audio_lock_free = {'level': 0.0, 'bass': 0.0, 'mid': 0.0, 'high': 0.0, 'beat': False, 'bpm': 0.0}
    eff = Twinkle(width=40, height=172)
    t = time.monotonic()
    times = []
    for _ in range(120):
      start = time.perf_counter()
      frame = eff.render(t, state)
      times.append(time.perf_counter() - start)
      t += 0.017
    avg_ms = sum(times) / len(times) * 1000
    assert frame.shape == (40, 172, 3)
    assert frame.dtype == np.uint8
    # Should be well under 2ms after vectorization (was ~3.5ms with loops)
    assert avg_ms < 2.0, f"Twinkle avg {avg_ms:.2f}ms exceeds 2ms budget"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pi && PYTHONPATH=. pytest tests/test_buffer_perf.py::TestTwinklePerformance -v`
Expected: FAIL — current loop-based Twinkle exceeds 2ms at width 40.

- [ ] **Step 3: Vectorize Twinkle**

Replace the `Twinkle` class in `pi/app/effects/generative.py` (lines 106-130):

```python
class Twinkle(Effect):
  """Random twinkling stars."""

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._rng = np.random.default_rng(42)
    self._stars = self._rng.random((self.width, self.height)) * 2 * math.pi

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    speed = self.params.get('speed', 1.0)
    density = self.params.get('density', 0.05)

    brightness = (np.sin(self._stars * 3.0 + elapsed * speed * 2.0) + 1.0) / 2.0
    mask = self._rng.random((self.width, self.height)) < density

    # Combine: pixel is visible if bright enough OR randomly selected
    visible = (brightness > 0.7) | mask

    # Vectorized hue: varies by row position and time
    y_coords = np.arange(self.height, dtype=np.float64) / self.height * 0.3
    hue = (elapsed * 0.02 + y_coords[np.newaxis, :]) % 1.0  # (width, height)

    # Vectorized HSV->RGB using the existing helper
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)
    rgb = _hsv_array_to_rgb(hue, 0.3, 1.0)  # (width, height, 3) uint8 at full brightness
    # Apply per-pixel brightness
    scaled = (rgb.astype(np.float32) * brightness[..., np.newaxis]).astype(np.uint8)
    frame[visible] = scaled[visible]

    return frame
```

- [ ] **Step 4: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/test_buffer_perf.py::TestTwinklePerformance tests/ -v --tb=short`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add pi/app/effects/generative.py pi/tests/test_buffer_perf.py
git commit -m "perf: vectorize Twinkle — eliminate double pixel loop"
```

---

### Task 6: Vectorize SpectralGlow

`audio:spectral_glow` has a double loop: outer over columns, inner over fill height. The inner loop calls scalar `hsv_to_rgb` per pixel. Vectorize using the same `_hsv_array_to_rgb` pattern.

**Files:**
- Modify: `pi/app/effects/audio_reactive.py:112-141`

- [ ] **Step 1: Write a performance test**

Add to `pi/tests/test_buffer_perf.py`:

```python
class TestSpectralGlowPerformance:
  def test_120_frames_under_budget(self):
    """SpectralGlow at width 40 should average under 1.5ms per frame."""
    import time
    from app.effects.audio_reactive import SpectralGlow
    from unittest.mock import MagicMock
    state = MagicMock()
    state.audio_bass = 0.8
    state.audio_mid = 0.6
    state.audio_high = 0.4
    eff = SpectralGlow(width=40, height=172)
    t = time.monotonic()
    times = []
    for _ in range(120):
      start = time.perf_counter()
      frame = eff.render(t, state)
      times.append(time.perf_counter() - start)
      t += 0.017
    avg_ms = sum(times) / len(times) * 1000
    assert frame.shape == (40, 172, 3)
    assert frame.dtype == np.uint8
    assert avg_ms < 1.5, f"SpectralGlow avg {avg_ms:.2f}ms exceeds 1.5ms budget"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pi && PYTHONPATH=. pytest tests/test_buffer_perf.py::TestSpectralGlowPerformance -v`
Expected: FAIL — current implementation ~2ms.

- [ ] **Step 3: Vectorize SpectralGlow**

Replace the `SpectralGlow` class in `pi/app/effects/audio_reactive.py` (lines 112-141):

```python
class SpectralGlow(Effect):
  """Columns glow based on spectral energy."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)

    bands = [state.audio_bass, state.audio_mid, state.audio_high]

    # Compute per-column fill heights via interpolation
    col_pos = np.arange(self.width, dtype=np.float64) / self.width * (len(bands) - 1)
    band_idx = np.minimum(col_pos.astype(np.int32), len(bands) - 2)
    frac = col_pos - band_idx
    band_arr = np.array(bands, dtype=np.float64)
    levels = band_arr[band_idx] * (1 - frac) + band_arr[band_idx + 1] * frac
    fill_heights = (levels * self.height).astype(np.int32)  # (width,)

    # Per-column hue
    hue_base = (np.arange(self.width, dtype=np.float64) / self.width + elapsed * 0.05) % 1.0

    # Build a mask of which pixels are lit: pixel (x, y) is lit if y < fill_heights[x]
    y_grid = np.arange(self.height, dtype=np.int32)[np.newaxis, :]  # (1, height)
    fill_grid = fill_heights[:, np.newaxis]  # (width, 1)
    lit_mask = y_grid < fill_grid  # (width, height)

    # Compute brightness fade: 1.0 - y/height * 0.5
    y_frac = np.arange(self.height, dtype=np.float64) / self.height
    fade = 1.0 - y_frac * 0.5  # (height,)

    # Vectorized HSV->RGB for the full grid
    hue_grid = np.broadcast_to(hue_base[:, np.newaxis], (self.width, self.height))

    from .base import _hsv_array_to_rgb  # import is at module level in practice
    rgb = _hsv_array_to_rgb(hue_grid, 0.8, 1.0)  # (width, height, 3)

    # Apply fade as brightness
    rgb_faded = (rgb.astype(np.float32) * fade[np.newaxis, :, np.newaxis]).astype(np.uint8)

    frame[lit_mask] = rgb_faded[lit_mask]
    return frame
```

Note: The `from .base import _hsv_array_to_rgb` should be added at the top of `audio_reactive.py` with the other imports. Check if `_hsv_array_to_rgb` is already importable from `generative.py` — it's defined in `generative.py` as a module-level function. If it's not in `base.py`, import from `generative`:

```python
from .generative import _hsv_array_to_rgb
```

- [ ] **Step 4: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/test_buffer_perf.py::TestSpectralGlowPerformance tests/ -v --tb=short`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add pi/app/effects/audio_reactive.py pi/tests/test_buffer_perf.py
git commit -m "perf: vectorize SpectralGlow — eliminate per-pixel HSV loop"
```

---

### Task 7: Benchmark Harness

Add a CLI tool that runs any effect for 600 frames (10 seconds at 60 FPS) through the full pipeline and reports timing metrics. This is both a development tool and an on-device acceptance gate.

**Files:**
- Create: `pi/tools/bench_effects.py`

- [ ] **Step 1: Create the benchmark harness**

```python
# pi/tools/bench_effects.py
"""Effect benchmark harness — 10-second full-pipeline timing.

Usage:
  python -m tools.bench_effects                     # all effects
  python -m tools.bench_effects --effect matrix_rain # single effect
  python -m tools.bench_effects --frames 120        # quick pass
"""

import argparse
import sys
import time

import numpy as np
from unittest.mock import MagicMock

from app.effects.generative import EFFECTS
from app.effects.audio_reactive import AUDIO_EFFECTS
from app.effects.imported import IMPORTED_EFFECTS
from app.mapping.cylinder import downsample_width, map_frame_fast, serialize_channels, N
from app.core.renderer import _build_gamma_lut


def _make_state():
  """Synthetic render state with 128 BPM audio."""
  state = MagicMock()
  state._audio_lock_free = {
    'level': 0.5, 'bass': 0.6, 'mid': 0.4, 'high': 0.3,
    'beat': False, 'bpm': 128.0,
  }
  state.audio_level = 0.5
  state.audio_bass = 0.6
  state.audio_mid = 0.4
  state.audio_high = 0.3
  state.audio_beat = False
  state.audio_bpm = 128.0
  state.current_scene = 'bench'
  state.blackout = False
  return state


def bench_one(name, effect_cls, frames, gamma_lut, state):
  """Benchmark a single effect through the full pipeline."""
  native_w = getattr(effect_cls, 'NATIVE_WIDTH', None) or 40
  try:
    eff = effect_cls(width=native_w, height=N)
  except Exception as e:
    return {'name': name, 'error': str(e)}

  t = time.monotonic()
  render_times = []
  post_times = []

  for i in range(frames):
    # Toggle beat every 28 frames (~128 BPM at 60 FPS)
    if i % 28 == 0:
      state.audio_beat = True
      state._audio_lock_free['beat'] = True
    else:
      state.audio_beat = False
      state._audio_lock_free['beat'] = False

    # Render
    r_start = time.perf_counter()
    try:
      internal_frame = eff.render(t, state)
    except Exception as e:
      return {'name': name, 'error': str(e)}
    r_end = time.perf_counter()

    # Post-processing pipeline
    p_start = r_end
    if internal_frame.shape[0] != 10:
      logical = downsample_width(internal_frame, 10)
    else:
      logical = internal_frame
    logical = (logical * 0.8).astype(np.uint8)  # brightness
    logical = gamma_lut[logical]
    channel_data = map_frame_fast(logical)
    _ = serialize_channels(channel_data)
    p_end = time.perf_counter()

    render_times.append(r_end - r_start)
    post_times.append(p_end - p_start)
    t += 1.0 / 60

  render_ms = [x * 1000 for x in render_times]
  post_ms = [x * 1000 for x in post_times]
  total_ms = [r + p for r, p in zip(render_ms, post_ms)]

  return {
    'name': name,
    'width': native_w,
    'frames': frames,
    'render_avg_ms': np.mean(render_ms),
    'render_p95_ms': np.percentile(render_ms, 95),
    'post_avg_ms': np.mean(post_ms),
    'total_avg_ms': np.mean(total_ms),
    'total_p95_ms': np.percentile(total_ms, 95),
    'total_max_ms': np.max(total_ms),
    'first60_ms': np.mean(total_ms[:60]) if frames >= 60 else np.mean(total_ms),
    'last60_ms': np.mean(total_ms[-60:]) if frames >= 60 else np.mean(total_ms),
    'implied_fps': 1000.0 / np.mean(total_ms) if np.mean(total_ms) > 0 else 9999,
  }


def main():
  parser = argparse.ArgumentParser(description='Effect benchmark harness')
  parser.add_argument('--effect', type=str, help='Single effect name to benchmark')
  parser.add_argument('--frames', type=int, default=600, help='Number of frames (default: 600)')
  parser.add_argument('--csv', action='store_true', help='Output as CSV')
  args = parser.parse_args()

  all_effects = {**EFFECTS, **AUDIO_EFFECTS, **IMPORTED_EFFECTS}
  gamma_lut = _build_gamma_lut(2.2)
  state = _make_state()

  if args.effect:
    if args.effect not in all_effects:
      print(f"Unknown effect: {args.effect}")
      print(f"Available: {', '.join(sorted(all_effects.keys()))}")
      sys.exit(1)
    targets = {args.effect: all_effects[args.effect]}
  else:
    targets = all_effects

  results = []
  for name, cls in sorted(targets.items()):
    result = bench_one(name, cls, args.frames, gamma_lut, state)
    results.append(result)
    if not args.csv:
      if 'error' in result:
        print(f"  {name}: ERROR — {result['error']}")
      else:
        status = "OK" if result['total_p95_ms'] < 16.7 else "SLOW"
        print(f"  {name}: avg={result['total_avg_ms']:.2f}ms "
              f"p95={result['total_p95_ms']:.2f}ms "
              f"first60={result['first60_ms']:.2f}ms "
              f"last60={result['last60_ms']:.2f}ms "
              f"[{status}]")

  if args.csv:
    print("name,width,render_avg_ms,total_avg_ms,total_p95_ms,total_max_ms,"
          "first60_ms,last60_ms,implied_fps,error")
    for r in results:
      if 'error' in r:
        print(f"{r['name']},,,,,,,,{r['error']}")
      else:
        print(f"{r['name']},{r['width']},{r['render_avg_ms']:.3f},"
              f"{r['total_avg_ms']:.3f},{r['total_p95_ms']:.3f},"
              f"{r['total_max_ms']:.3f},{r['first60_ms']:.3f},"
              f"{r['last60_ms']:.3f},{r['implied_fps']:.1f},")

  # Summary
  if not args.csv:
    slow = [r for r in results if 'error' not in r and r['total_p95_ms'] >= 16.7]
    errors = [r for r in results if 'error' in r]
    print(f"\n{len(results)} effects benchmarked, "
          f"{len(slow)} slow (p95 >= 16.7ms), "
          f"{len(errors)} errors")


if __name__ == '__main__':
  main()
```

- [ ] **Step 2: Verify it runs**

Run: `cd pi && PYTHONPATH=. python -m tools.bench_effects --effect fire --frames 120`
Expected: Prints timing for `fire` effect, shows "OK" status.

Run: `cd pi && PYTHONPATH=. python -m tools.bench_effects --effect matrix_rain --frames 600`
Expected: Shows timing for `matrix_rain`. After Task 4, last60 should be within 4x of first60.

- [ ] **Step 3: Commit**

```bash
git add pi/tools/bench_effects.py
git commit -m "feat: add effect benchmark harness — 10-second full-pipeline timing"
```

---

### Task 8: Spectrum and Spectrogram Width Fix Verification

After Task 3 tagged these with `NATIVE_WIDTH = 10`, they should no longer crash. This task verifies the fix and adds explicit regression tests.

**Files:**
- Modify: `pi/tests/test_width_policy.py`

- [ ] **Step 1: Add regression tests**

Append to `pi/tests/test_width_policy.py`:

```python
import time


class TestBrokenWidthEffects:
  """Spectrum and Spectrogram must not crash at their native width."""

  def test_spectrum_renders_at_width_10(self):
    from app.effects.imported.sound import Spectrum
    state = MagicMock()
    state._audio_lock_free = {
      'level': 0.5, 'bass': 0.6, 'mid': 0.4, 'high': 0.3,
      'beat': False, 'bpm': 128.0,
    }
    eff = Spectrum(width=10, height=172)
    t = time.monotonic()
    for _ in range(10):
      frame = eff.render(t, state)
      assert frame.shape == (10, 172, 3)
      t += 0.017

  def test_spectrogram_renders_at_width_10(self):
    from app.effects.imported.sound import Spectrogram
    state = MagicMock()
    state._audio_lock_free = {
      'level': 0.5, 'bass': 0.6, 'mid': 0.4, 'high': 0.3,
      'beat': False, 'bpm': 128.0,
    }
    eff = Spectrogram(width=10, height=172)
    t = time.monotonic()
    for _ in range(10):
      frame = eff.render(t, state)
      assert frame.shape == (10, 172, 3)
      t += 0.017

  def test_spectrum_crashes_at_width_40(self):
    """Document that Spectrum does NOT support width > 10."""
    from app.effects.imported.sound import Spectrum
    import pytest
    state = MagicMock()
    state._audio_lock_free = {
      'level': 0.5, 'bass': 0.6, 'mid': 0.4, 'high': 0.3,
      'beat': False, 'bpm': 128.0,
    }
    eff = Spectrum(width=40, height=172)
    with pytest.raises(IndexError):
      eff.render(time.monotonic(), state)
```

- [ ] **Step 2: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/test_width_policy.py::TestBrokenWidthEffects -v`
Expected: All PASS — width 10 works, width 40 still crashes (documenting the known limitation).

- [ ] **Step 3: Commit**

```bash
git add pi/tests/test_width_policy.py
git commit -m "test: add spectrum/spectrogram width regression tests"
```

---

## Execution Order Summary

| Task | What | Risk | Dependencies |
|---:|---|---|---|
| 1 | LEDBuffer zero-allocation | Low — drop-in replacement | None |
| 2 | Per-effect width policy | Low — no effect changes yet | None |
| 3 | Tag all imported NATIVE_WIDTH=10 | Low — declarative only | Task 2 |
| 4 | Rewrite MatrixRain | Medium — behavioral change | Tasks 1, 3 |
| 5 | Vectorize Twinkle | Low — single effect | None |
| 6 | Vectorize SpectralGlow | Low — single effect | None |
| 7 | Benchmark harness | None — new file | Tasks 2, 3 |
| 8 | Spectrum/Spectrogram verification | None — tests only | Task 3 |

Tasks 1, 2, 5, 6 are independent and can be parallelized. Tasks 3 depends on 2. Task 4 depends on 1 and 3. Tasks 7 and 8 depend on 3.
