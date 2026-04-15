# Generative Effects Overhaul — Plan A

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire palette support into all 14 generative effects, fix broken effects (fire direction, color wipe, scanline), add requested controls (solid color modes, darkness sliders, brightness), and reduce speeds. Every generative effect should respond to palette selection from the UI.

**Architecture:** All generative effects currently generate color via HSV and ignore the `palette` param. The fix is to replace `_hsv_array_to_rgb(hue, s, v)` calls with `pal_color_grid(pal_idx, hue)` where `hue` is used as the palette position (0–1). The palette infrastructure (`pal_color_grid` in `palettes.py`) is already imported by all imported effects and works. The UI already sends `params.palette` as an integer index. The effects.yaml already defines palette defaults for most effects but the effects never read them.

**Tech Stack:** Python 3.13, NumPy, existing `pal_color_grid` / `_PAL_ARRAYS`

**Key reference:** `pal_color_grid(pal_idx, t_array)` in `pi/app/effects/engine/palettes.py:125` — takes a palette index and a float array (0–1), returns `(..., 3)` uint8 RGB. 10 palettes available: Rainbow(0), Ocean(1), Sunset(2), Forest(3), Lava(4), Ice(5), Neon(6), Cyberpunk(7), Pastel(8), Vapor(9).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `pi/app/effects/generative.py` | Modify | All 14 effect classes — add palette, fix bugs, tune params |
| `pi/config/effects.yaml` | Modify | Update default param ranges |
| `pi/tests/test_generative_palette.py` | Create | Tests that every generative effect responds to palette param |

---

### Task 1: Import Palette Infrastructure + Add Palette Test Harness

Wire the palette module into generative.py and create the test file that will validate every subsequent task.

**Files:**
- Modify: `pi/app/effects/generative.py` (imports only)
- Create: `pi/tests/test_generative_palette.py`

- [ ] **Step 1: Add palette imports to generative.py**

At the top of `pi/app/effects/generative.py`, add after the existing imports (line 10):

```python
from .engine.palettes import pal_color_grid, NUM_PALETTES
```

- [ ] **Step 2: Create the palette test harness**

```python
# pi/tests/test_generative_palette.py
"""Tests that all generative effects respond to palette selection."""

import time
import numpy as np
from unittest.mock import MagicMock

from app.effects.generative import EFFECTS


def _make_state():
  state = MagicMock()
  state._audio_lock_free = {
    'level': 0.0, 'bass': 0.0, 'mid': 0.0, 'high': 0.0,
    'beat': False, 'bpm': 0.0,
  }
  state.audio_level = 0.0
  state.audio_bass = 0.0
  state.audio_mid = 0.0
  state.audio_high = 0.0
  state.audio_beat = False
  state.audio_bpm = 0.0
  return state


# Effects that should respond to palette changes
PALETTE_EFFECTS = [
  'vertical_gradient', 'rainbow_rotate', 'plasma', 'twinkle', 'spark',
  'noise_wash', 'sine_bands', 'cylinder_rotate', 'fire',
]

# Effects with special color handling (not palette-indexed)
# solid_color: has its own color picker + fade mode
# color_wipe: uses two palette colors
# scanline: uses palette for beam color
# seam_pulse: diagnostic, fixed colors
# diagnostic_labels: diagnostic, fixed colors


class TestGenerativePaletteSupport:
  def test_palette_effects_produce_different_output_per_palette(self):
    """Each palette-supporting effect must produce visibly different frames
    when palette 0 (Rainbow) vs palette 4 (Lava) is selected."""
    state = _make_state()
    t = time.monotonic()
    for name in PALETTE_EFFECTS:
      cls = EFFECTS[name]
      eff_pal0 = cls(width=10, height=172, params={'palette': 0})
      eff_pal4 = cls(width=10, height=172, params={'palette': 4})
      # Render a few frames to let effects warm up
      for _ in range(10):
        f0 = eff_pal0.render(t, state)
        f4 = eff_pal4.render(t, state)
        t += 0.017
      assert not np.array_equal(f0, f4), (
        f"{name}: palette 0 and palette 4 produced identical frames"
      )

  def test_all_effects_render_correct_shape(self):
    state = _make_state()
    t = time.monotonic()
    for name, cls in EFFECTS.items():
      eff = cls(width=10, height=172)
      frame = eff.render(t, state)
      assert frame.shape == (10, 172, 3), f"{name}: wrong shape {frame.shape}"
      assert frame.dtype == np.uint8, f"{name}: wrong dtype {frame.dtype}"
      t += 0.017


class TestSolidColorModes:
  def test_static_mode_is_uniform(self):
    from app.effects.generative import SolidColor
    state = _make_state()
    eff = SolidColor(width=10, height=172, params={'color': '#FF0000', 'speed': 0.0})
    frame = eff.render(time.monotonic(), state)
    # All pixels should be the same color
    assert np.all(frame[0, 0] == frame[-1, -1])

  def test_fade_mode_cycles_palette(self):
    from app.effects.generative import SolidColor
    state = _make_state()
    eff = SolidColor(width=10, height=172, params={'speed': 1.0, 'palette': 0})
    t = time.monotonic()
    frames = []
    for _ in range(30):
      frames.append(eff.render(t, state).copy())
      t += 0.1
    # Frames should change over time when speed > 0
    assert not np.array_equal(frames[0], frames[-1])


class TestFireDirection:
  def test_fire_hot_at_bottom(self):
    """Fire should be brightest at the bottom (low y values)."""
    from app.effects.generative import Fire
    state = _make_state()
    eff = Fire(width=10, height=172, params={'sparking': 200})
    t = time.monotonic()
    # Render enough frames for fire to develop
    for _ in range(120):
      frame = eff.render(t, state)
      t += 0.017
    # Bottom quarter should be brighter than top quarter on average
    bottom_brightness = frame[:, :43, :].astype(float).mean()
    top_brightness = frame[:, 129:, :].astype(float).mean()
    assert bottom_brightness > top_brightness, (
      f"Fire is upside down: bottom={bottom_brightness:.1f}, top={top_brightness:.1f}"
    )


class TestScanlineBounce:
  def test_scanline_ping_pongs(self):
    """Scanline should reverse direction at top."""
    from app.effects.generative import Scanline
    state = _make_state()
    eff = Scanline(width=10, height=172, params={'speed': 2.0})
    t = time.monotonic()
    positions = []
    for _ in range(200):
      frame = eff.render(t, state)
      # Find the brightest row
      row_brightness = frame.sum(axis=(0, 2))
      positions.append(int(np.argmax(row_brightness)))
      t += 0.017
    # Should go up AND down — check we have both increasing and decreasing runs
    diffs = [positions[i+1] - positions[i] for i in range(len(positions)-1) if positions[i+1] != positions[i]]
    has_up = any(d > 0 for d in diffs)
    has_down = any(d < 0 for d in diffs)
    assert has_up and has_down, "Scanline should ping-pong but only moves in one direction"


class TestColorWipeContinuous:
  def test_no_full_blackout(self):
    """Color wipe should transition color-to-color, never go fully black."""
    from app.effects.generative import ColorWipe
    state = _make_state()
    eff = ColorWipe(width=10, height=172, params={'speed': 1.0, 'palette': 0})
    t = time.monotonic()
    black_frames = 0
    for _ in range(120):
      frame = eff.render(t, state)
      if frame.sum() == 0:
        black_frames += 1
      t += 0.017
    assert black_frames == 0, f"ColorWipe went fully black {black_frames} times in 120 frames"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd pi && PYTHONPATH=. pytest tests/test_generative_palette.py -v`
Expected: Multiple failures — palette tests fail because effects ignore palette, fire direction may fail, scanline bounce fails, color wipe blackout fails.

- [ ] **Step 4: Commit**

```bash
git add pi/app/effects/generative.py pi/tests/test_generative_palette.py
git commit -m "test: add generative effects palette + behavior test harness"
```

---

### Task 2: Wire Palette into VerticalGradient, RainbowRotate, Plasma, NoisWash, SineBands, CylinderRotate

These 6 effects all follow the same pattern: they compute a `hue` array (0–1) and pass it through `_hsv_array_to_rgb`. Replace with `pal_color_grid(pal_idx, hue)`. Also reduce speeds where requested.

**Files:**
- Modify: `pi/app/effects/generative.py` — 6 effect classes

- [ ] **Step 1: VerticalGradient — add palette + reduce speed**

Replace the `VerticalGradient` class (lines 47–59):

```python
class VerticalGradient(Effect):
  """Animated vertical gradient from a palette."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    speed = self.params.get('speed', 0.05)
    pal_idx = self.params.get('palette', 0) % NUM_PALETTES

    ys = np.arange(self.height, dtype=np.float64) / self.height
    pos = (ys + elapsed * speed) % 1.0  # (height,)

    # Broadcast to (width, height) and lookup palette
    pos_2d = np.broadcast_to(pos[np.newaxis, :], (self.width, self.height))
    return pal_color_grid(pal_idx, pos_2d)
```

- [ ] **Step 2: RainbowRotate — add palette**

Replace `RainbowRotate.render` (lines 65–76):

```python
class RainbowRotate(Effect):
  """Rainbow that rotates around the cylinder."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    speed = self.params.get('speed', 1.0)
    scale = self.params.get('scale', 1.0)
    pal_idx = self.params.get('palette', 0) % NUM_PALETTES

    xs = np.arange(self.width, dtype=np.float64) / self.width * scale
    ys = np.arange(self.height, dtype=np.float64) / self.height * 0.3
    xx, yy = np.meshgrid(xs, ys, indexing='ij')
    hue = (xx + yy + elapsed * speed * 0.1) % 1.0

    return pal_color_grid(pal_idx, hue)
```

- [ ] **Step 3: Plasma — add palette**

Replace `Plasma.render` (lines 82–103):

```python
class Plasma(Effect):
  """Plasma effect using overlapping sine waves."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    speed = self.params.get('speed', 1.0)
    scale = self.params.get('scale', 2.0)
    pal_idx = self.params.get('palette', 0) % NUM_PALETTES

    tt = elapsed * speed

    xs = np.arange(self.width, dtype=np.float64) / self.width * scale * math.pi * 2
    ys = np.arange(self.height, dtype=np.float64) / self.height * scale * math.pi * 2
    xx, yy = np.meshgrid(xs, ys, indexing='ij')

    v1 = np.sin(xx + tt)
    v2 = np.sin(yy + tt * 0.7)
    v3 = np.sin(xx + yy + tt * 0.5)
    v4 = np.sin(np.sqrt(xx**2 + yy**2) + tt * 1.3)

    v = (v1 + v2 + v3 + v4) / 4.0
    hue = (v + 1.0) / 2.0

    return pal_color_grid(pal_idx, hue)
```

- [ ] **Step 4: NoiseWash — add palette**

Replace `NoiseWash.render` (lines 189–204):

```python
class NoiseWash(Effect):
  """Smooth noise-based color wash."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    speed = self.params.get('speed', 0.5)
    scale = self.params.get('scale', 3.0)
    pal_idx = self.params.get('palette', 0) % NUM_PALETTES

    nx = np.arange(self.width, dtype=np.float64) / self.width * scale
    ny = np.arange(self.height, dtype=np.float64) / self.height * scale
    nxx, nyy = np.meshgrid(nx, ny, indexing='ij')

    v = (np.sin(nxx * 2.1 + elapsed * speed) +
         np.sin(nyy * 1.7 + elapsed * speed * 0.8) +
         np.sin((nxx + nyy) * 1.3 + elapsed * speed * 0.6)) / 3.0
    hue = (v + 1.0) / 2.0

    return pal_color_grid(pal_idx, hue)
```

- [ ] **Step 5: SineBands — add palette, simplify**

The current SineBands does manual vectorized HSV with per-pixel v. With palette, this simplifies dramatically. Replace `SineBands` (lines 305–343):

```python
class SineBands(Effect):
  """Sine-wave color bands."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    freq = self.params.get('frequency', 3.0)
    speed = self.params.get('speed', 1.0)
    pal_idx = self.params.get('palette', 0) % NUM_PALETTES

    ys = np.arange(self.height, dtype=np.float64)
    hue_1d = (np.sin(ys / self.height * freq * math.pi * 2 + elapsed * speed) + 1.0) / 2.0

    # Broadcast to (width, height)
    hue_2d = np.broadcast_to(hue_1d[np.newaxis, :], (self.width, self.height))

    # Palette lookup gives us the color; modulate brightness with the sine
    rgb = pal_color_grid(pal_idx, hue_2d)

    # Apply brightness modulation — brighter at sine peaks
    brightness = np.broadcast_to(hue_1d[np.newaxis, :], (self.width, self.height))
    return (rgb.astype(np.float32) * brightness[..., np.newaxis]).astype(np.uint8)
```

- [ ] **Step 6: CylinderRotate — add palette, simplify**

Same pattern. Replace `CylinderRotate` (lines 346–378):

```python
class CylinderRotate(Effect):
  """Color pattern that rotates around the cylinder."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    speed = self.params.get('speed', 1.0)
    pal_idx = self.params.get('palette', 0) % NUM_PALETTES

    xs = np.arange(self.width, dtype=np.float64) / self.width
    ys = np.arange(self.height, dtype=np.float64)
    xx, yy = np.meshgrid(xs, ys, indexing='ij')

    hue = (xx + elapsed * speed * 0.1) % 1.0
    brightness = (np.sin(yy / self.height * math.pi * 4 + elapsed) + 1.0) / 2.0

    rgb = pal_color_grid(pal_idx, hue)
    return (rgb.astype(np.float32) * brightness[..., np.newaxis]).astype(np.uint8)
```

- [ ] **Step 7: Run palette tests for these 6 effects**

Run: `cd pi && PYTHONPATH=. pytest tests/test_generative_palette.py::TestGenerativePaletteSupport -v`
Expected: These 6 should now produce different output per palette. Others still fail.

- [ ] **Step 8: Run full test suite**

Run: `cd pi && PYTHONPATH=. pytest tests/ -v --tb=short`
Expected: All pass (except pre-existing migration failure).

- [ ] **Step 9: Commit**

```bash
git add pi/app/effects/generative.py
git commit -m "feat: wire palette into VerticalGradient, RainbowRotate, Plasma, NoiseWash, SineBands, CylinderRotate"
```

---

### Task 3: Wire Palette into Twinkle + Add Darkness Slider

Twinkle needs palette support and a darkness slider that dims the overall output.

**Files:**
- Modify: `pi/app/effects/generative.py` — Twinkle class

- [ ] **Step 1: Replace Twinkle class**

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
    darkness = self.params.get('darkness', 0.0)
    pal_idx = self.params.get('palette', 0) % NUM_PALETTES

    brightness = (np.sin(self._stars * 3.0 + elapsed * speed * 2.0) + 1.0) / 2.0
    mask = self._rng.random((self.width, self.height)) < density
    visible = (brightness > 0.7) | mask

    # Palette position varies by row and time
    y_coords = np.arange(self.height, dtype=np.float64) / self.height * 0.3
    hue = (elapsed * 0.02 + y_coords[np.newaxis, :]) % 1.0

    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)
    rgb = pal_color_grid(pal_idx, hue)
    # Apply per-pixel brightness and darkness
    dim = 1.0 - min(1.0, max(0.0, darkness))
    scaled = (rgb.astype(np.float32) * brightness[..., np.newaxis] * dim).astype(np.uint8)
    frame[visible] = scaled[visible]

    return frame
```

- [ ] **Step 2: Run tests**

Run: `cd pi && PYTHONPATH=. pytest tests/test_generative_palette.py -v -k twinkle`

- [ ] **Step 3: Commit**

```bash
git add pi/app/effects/generative.py
git commit -m "feat: Twinkle — add palette support + darkness slider"
```

---

### Task 4: Wire Palette into Spark + Add Brightness Control

Spark needs palette for trail colors and a brightness multiplier since sparks are very dim.

**Files:**
- Modify: `pi/app/effects/generative.py` — Spark class

- [ ] **Step 1: Replace Spark class**

```python
class Spark(Effect):
  """Upward-moving sparks."""

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._sparks: list[dict] = []
    self._last_spawn = 0.0

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    speed = self.params.get('speed', 2.0)
    rate = self.params.get('rate', 10)
    brightness = self.params.get('brightness', 1.0)
    pal_idx = self.params.get('palette', 0) % NUM_PALETTES
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)

    # Spawn new sparks
    spawn_interval = 1.0 / max(1, rate)
    while elapsed - self._last_spawn > spawn_interval:
      self._last_spawn += spawn_interval
      self._sparks.append({
        'x': np.random.randint(0, self.width),
        'y': 0.0,
        'speed': speed * (0.5 + np.random.random()),
        'hue': np.random.random(),
        'life': 1.0,
      })

    # Update and draw
    alive = []
    for s in self._sparks:
      s['y'] += s['speed']
      s['life'] -= 0.01
      if s['life'] > 0 and int(s['y']) < self.height:
        yi = int(s['y'])
        c = pal_color_grid(pal_idx, np.array([s['hue']]))[0]
        b = s['life'] * min(2.0, max(0.1, brightness))
        frame[s['x'] % self.width, yi] = np.clip(c.astype(np.float32) * b, 0, 255).astype(np.uint8)
        # Tail
        for tail in range(1, 4):
          ty = yi - tail
          if 0 <= ty < self.height:
            fade = s['life'] * (1 - tail * 0.25) * min(2.0, max(0.1, brightness))
            if fade > 0:
              frame[s['x'] % self.width, ty] = np.clip(c.astype(np.float32) * fade, 0, 255).astype(np.uint8)
        alive.append(s)
    self._sparks = alive[-200:]
    return frame
```

- [ ] **Step 2: Run tests + commit**

Run: `cd pi && PYTHONPATH=. pytest tests/test_generative_palette.py tests/ -v --tb=short`

```bash
git add pi/app/effects/generative.py
git commit -m "feat: Spark — add palette support + brightness control"
```

---

### Task 5: Fix Fire — Flip Direction + Add Palette

Fire renders upside-down on the physical pillar. The heat simulation is correct (y=0 = bottom) but the output needs to be flipped. Also wire in palette support using `pal_color_grid` instead of hardcoded red→yellow→white.

**Files:**
- Modify: `pi/app/effects/generative.py` — Fire class

- [ ] **Step 1: Replace Fire class**

```python
class Fire(Effect):
  """Fire-like effect rising from the bottom. Fully vectorized."""

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._heat = np.zeros((self.width, self.height), dtype=np.float64)
    self._rng = np.random.default_rng(42)

  def render(self, t: float, state) -> np.ndarray:
    cooling = self.params.get('cooling', 55)
    sparking = self.params.get('sparking', 120)
    pal_idx = self.params.get('palette', 4) % NUM_PALETTES  # default Lava

    # Cool down
    cool_amount = self._rng.integers(
      0, max(1, (cooling * 10) // self.height + 2),
      size=(self.width, self.height)
    ) / 255.0
    self._heat = np.maximum(0, self._heat - cool_amount)

    # Heat rises: shift upward with averaging
    shifted = np.zeros_like(self._heat)
    shifted[:, 3:] = (
      self._heat[:, 2:-1] +
      self._heat[:, 1:-2] +
      self._heat[:, 1:-2]
    ) / 3.0
    shifted[:, :3] = self._heat[:, :3]
    self._heat = shifted

    # Sparks at bottom
    spark_mask = self._rng.integers(0, 255, size=self.width) < sparking
    for x in np.where(spark_mask)[0]:
      y = self._rng.integers(0, min(7, self.height))
      self._heat[x, y] = min(1.0, self._heat[x, y] + 0.4 + self._rng.random() * 0.4)

    # Palette-based color mapping — heat value (0-1) maps to palette position
    frame = pal_color_grid(pal_idx, self._heat)

    # Flip vertically — heat sim uses y=0 as hot base, but physical pillar
    # needs hot pixels at high y (bottom of display)
    return frame[:, ::-1, :]
```

- [ ] **Step 2: Run fire direction test**

Run: `cd pi && PYTHONPATH=. pytest tests/test_generative_palette.py::TestFireDirection -v`
Expected: PASS — bottom should now be brighter than top.

- [ ] **Step 3: Run full suite + commit**

Run: `cd pi && PYTHONPATH=. pytest tests/ -v --tb=short`

```bash
git add pi/app/effects/generative.py
git commit -m "fix: Fire — flip to correct orientation + add palette support"
```

---

### Task 6: Fix ColorWipe — Continuous Color-over-Color

Color wipe currently blacks out between wipes. It should continuously sweep one palette color over another, never going fully black.

**Files:**
- Modify: `pi/app/effects/generative.py` — ColorWipe class

- [ ] **Step 1: Replace ColorWipe class**

```python
class ColorWipe(Effect):
  """Color wipe — sweeps one palette color over another, ping-pong."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    speed = self.params.get('speed', 0.5)
    pal_idx = self.params.get('palette', 0) % NUM_PALETTES
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)

    # Two colors from the palette — current and next
    cycle_pos = (elapsed * speed * 0.1) % 1.0
    color_a_pos = cycle_pos % 1.0
    color_b_pos = (cycle_pos + 0.5) % 1.0
    color_a = pal_color_grid(pal_idx, np.array([color_a_pos]))[0]
    color_b = pal_color_grid(pal_idx, np.array([color_b_pos]))[0]

    # Ping-pong wipe position
    raw_pos = (elapsed * speed * 0.3) % 2.0
    if raw_pos > 1.0:
      wipe_frac = 2.0 - raw_pos  # bouncing back
    else:
      wipe_frac = raw_pos
    wipe_y = int(wipe_frac * self.height)

    # Fill: color_a below wipe, color_b above
    frame[:, :wipe_y] = color_a
    frame[:, wipe_y:] = color_b

    return frame
```

- [ ] **Step 2: Run color wipe test**

Run: `cd pi && PYTHONPATH=. pytest tests/test_generative_palette.py::TestColorWipeContinuous -v`
Expected: PASS — no fully black frames.

- [ ] **Step 3: Run full suite + commit**

```bash
git add pi/app/effects/generative.py
git commit -m "fix: ColorWipe — continuous color-over-color with ping-pong, no blackout"
```

---

### Task 7: Fix Scanline — Ping-Pong + Gaussian + Palette

Scanline should bounce (not wrap), have a gaussian brightness profile, and use palette color.

**Files:**
- Modify: `pi/app/effects/generative.py` — Scanline class

- [ ] **Step 1: Replace Scanline class**

```python
class Scanline(Effect):
  """Horizontal scanline with gaussian glow, ping-pong bounce."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    speed = self.params.get('speed', 0.5)
    width_param = self.params.get('width', 8)
    pal_idx = self.params.get('palette', 0) % NUM_PALETTES
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)

    # Ping-pong position
    raw = (elapsed * speed * 0.3) % 2.0
    if raw > 1.0:
      pos = (2.0 - raw) * self.height
    else:
      pos = raw * self.height

    # Gaussian brightness around center
    ys = np.arange(self.height, dtype=np.float64)
    dist = np.abs(ys - pos)
    sigma = max(1.0, width_param)
    gaussian = np.exp(-0.5 * (dist / sigma) ** 2)

    # Center is blown-out white, edges get palette color with increasing saturation
    center_color = np.array([255, 255, 255], dtype=np.float64)
    # Palette position varies along the gaussian wings
    pal_pos = (ys / self.height + elapsed * 0.02) % 1.0
    pal_rgb = pal_color_grid(pal_idx, pal_pos)  # (height, 3) uint8

    # Blend: at center (gaussian ~1) → white; at edges → palette color
    # Use gaussian^2 for a tighter white core
    white_blend = gaussian ** 2
    result_1d = (
      center_color[np.newaxis, :] * white_blend[:, np.newaxis] +
      pal_rgb.astype(np.float64) * (1.0 - white_blend[:, np.newaxis])
    )
    # Scale by overall gaussian envelope for falloff
    result_1d = result_1d * gaussian[:, np.newaxis]
    result_1d = np.clip(result_1d, 0, 255).astype(np.uint8)

    # Broadcast across width
    frame[:, :, :] = result_1d[np.newaxis, :, :]
    return frame
```

- [ ] **Step 2: Run scanline test + full suite + commit**

Run: `cd pi && PYTHONPATH=. pytest tests/test_generative_palette.py::TestScanlineBounce tests/ -v --tb=short`

```bash
git add pi/app/effects/generative.py
git commit -m "feat: Scanline — ping-pong bounce + gaussian profile + palette color"
```

---

### Task 8: SolidColor — Add Color Picker + Fade-Cycle Mode

When speed=0, show a static solid color from a `hue` slider (0–1). When speed>0, cycle through the selected palette at that speed. The hue slider is only for static mode.

**Files:**
- Modify: `pi/app/effects/generative.py` — SolidColor class

- [ ] **Step 1: Replace SolidColor class**

```python
class SolidColor(Effect):
  """Solid color fill — static or palette cycling.

  speed=0: static color from 'hue' param (0-1).
  speed>0: cycles through selected palette at that speed.
  """

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    speed = self.params.get('speed', 0.0)
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)

    if speed == 0:
      # Static mode — use color param or hue slider
      color_hex = self.params.get('color', None)
      if color_hex:
        color = hex_to_rgb(color_hex)
      else:
        hue = self.params.get('hue', 0.0)
        pal_idx = self.params.get('palette', 0) % NUM_PALETTES
        color = tuple(pal_color_grid(pal_idx, np.array([hue]))[0])
      frame[:, :] = color
    else:
      # Fade-cycle mode — smoothly cycle through palette
      pal_idx = self.params.get('palette', 0) % NUM_PALETTES
      pos = (elapsed * speed * 0.05) % 1.0
      color = pal_color_grid(pal_idx, np.array([pos]))[0]
      frame[:, :] = color

    return frame
```

- [ ] **Step 2: Run tests + commit**

Run: `cd pi && PYTHONPATH=. pytest tests/test_generative_palette.py::TestSolidColorModes tests/ -v --tb=short`

```bash
git add pi/app/effects/generative.py
git commit -m "feat: SolidColor — static hue picker + palette cycling fade mode"
```

---

### Task 9: Update effects.yaml Defaults

Update param defaults to match the tuning feedback. Reduce speeds, set correct default palettes.

**Files:**
- Modify: `pi/config/effects.yaml`

- [ ] **Step 1: Update effects.yaml**

```yaml
effects:
  solid_color:
    params:
      color: "#FF6600"
      speed: 0.0
      hue: 0.0
      palette: 0

  vertical_gradient:
    params:
      speed: 0.05
      palette: 0

  rainbow_rotate:
    params:
      speed: 0.1
      scale: 1.0
      palette: 0

  plasma:
    params:
      speed: 1.0
      scale: 2.0
      palette: 0

  twinkle:
    params:
      density: 0.05
      speed: 1.0
      darkness: 0.0
      palette: 5

  spark:
    params:
      rate: 10
      speed: 2.0
      brightness: 1.0
      palette: 4

  noise_wash:
    params:
      speed: 0.5
      scale: 3.0
      palette: 1

  color_wipe:
    params:
      speed: 0.5
      palette: 0

  scanline:
    params:
      width: 8
      speed: 0.5
      palette: 0

  fire:
    params:
      cooling: 55
      sparking: 120
      palette: 4

  sine_bands:
    params:
      frequency: 3.0
      speed: 1.0
      palette: 0

  cylinder_rotate:
    params:
      speed: 0.1
      palette: 2
```

- [ ] **Step 2: Run full suite + commit**

Run: `cd pi && PYTHONPATH=. pytest tests/ -v --tb=short`

```bash
git add pi/config/effects.yaml
git commit -m "config: update generative effect defaults — reduced speeds, palette indices"
```

---

### Task 10: Final Validation

- [ ] **Step 1: Run all palette tests**

Run: `cd pi && PYTHONPATH=. pytest tests/test_generative_palette.py -v`
Expected: All PASS.

- [ ] **Step 2: Run full test suite**

Run: `cd pi && PYTHONPATH=. pytest tests/ -v --tb=short`
Expected: All PASS (except pre-existing migration issue).

- [ ] **Step 3: Run benchmark to verify no performance regression**

Run: `cd pi && PYTHONPATH=. python -m tools.bench_effects --frames 600`
Expected: All effects OK, no regressions. Palette lookup via `pal_color_grid` should be as fast or faster than `_hsv_array_to_rgb`.

- [ ] **Step 4: Commit any remaining fixes**

- [ ] **Step 5: Deploy to Pi**

```bash
bash /Users/jim/ai/pillar-controller/pi/scripts/deploy.sh ledfanatic.local
```

---

## Summary of Changes per Effect

| Effect | Palette | Speed Reduced | Other Changes |
|---|---|---|---|
| SolidColor | Yes (fade mode) | — | Static hue picker + fade-cycle mode |
| VerticalGradient | Yes | 0.5 → 0.05 | Vectorized |
| RainbowRotate | Yes | — | — |
| Plasma | Yes | — | — |
| Twinkle | Yes | — | Darkness slider |
| Spark | Yes | — | Brightness control |
| NoiseWash | Yes | — | — |
| ColorWipe | Yes | — | Fixed: continuous wipe, no blackout, ping-pong |
| Scanline | Yes | — | Fixed: ping-pong bounce + gaussian profile |
| Fire | Yes (default: Lava) | — | Fixed: flipped to correct orientation |
| SineBands | Yes | — | Simplified with palette |
| CylinderRotate | Yes | 1.0 → 0.1 | Simplified with palette |
| SeamPulse | No | — | Diagnostic — unchanged |
| DiagnosticLabels | No | — | Diagnostic — unchanged |
