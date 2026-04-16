"""
Sound-reactive variants of ambient/classic effects.

Each variant forks the base effect's render loop and layers audio modulation
on top via AudioCompatAdapter. Separate classes (not subclasses) for clarity
and safety — editing these cannot break the originals.
"""

import math
import random

import numpy as np

from ..base import Effect
from ..engine.buffer import LEDBuffer
from ..engine.color import hsv2rgb
from ..engine.palettes import (
  pal_color, NUM_PALETTES, PALETTE_NAMES, pal_color_grid,
  FELDSTEIN_PALETTES, FELDSTEIN_PALETTE_NAMES, NUM_FELDSTEIN_PALETTES,
)
from ..engine.noise import cyl_noise, perlin_grid
from ...audio.adapter import AudioCompatAdapter
from ...mapping.cylinder import N


def _get_pal_idx(params, default=0, names=PALETTE_NAMES, count=NUM_PALETTES):
  val = params.get('palette', default)
  if isinstance(val, str):
    try:
      return names.index(val) % count
    except ValueError:
      return default % count
  return int(val) % count


class _Param:
  __slots__ = ('label', 'attr', 'lo', 'hi', 'step', 'default')
  def __init__(self, label, attr, lo, hi, step, default):
    self.label = label
    self.attr = attr
    self.lo = lo
    self.hi = hi
    self.step = step
    self.default = default


# ═══════════════════════════════════════════════════════════════════
#  SR FELDSTEIN
# ═══════════════════════════════════════════════════════════════════

class SRFeldstein(Effect):
  """Sound-reactive Feldstein: bass drives speed, beat shifts hue, buildup increases fade."""

  CATEGORY = "sound"
  DISPLAY_NAME = "SR Feldstein"
  DESCRIPTION = "Audio-reactive Feldstein OG — bass speed, beat hue pulse"
  PALETTE_SUPPORT = False  # uses FELDSTEIN_PALETTES

  PARAMS = [
    _Param("Gain", "gain", 0.2, 5.0, 0.1, 1.0),
    _Param("Speed", "speed", 0.04, 0.6, 0.02, 0.2),
    _Param("Fade/Dark", "fade", 10, 200, 5, 48),
  ]
  _SCALAR_PARAMS = {"gain": 1.0, "speed": 0.2, "fade": 48, "palette": 0}
  NATIVE_WIDTH = 10

  def __init__(self, width=10, height=N, params=None):
    super().__init__(width, height, params)
    self._audio_adapter = AudioCompatAdapter()
    self.buf = LEDBuffer(width, height)
    self._rng = random.Random()
    self._xo = self._rng.randint(0, 65535)
    self._yo = self._rng.randint(0, 65535)
    self._zo = self._rng.randint(0, 65535)
    self._hue = 0
    self._hue_accum = 0.0
    self._elapsed_ms = 0.0
    self._last_t = None

  def render(self, t, state):
    dt_ms = self._calc_dt_ms(t)
    raw = state._audio_lock_free
    audio = self._audio_adapter.adapt(raw, t)

    gain = self.params.get("gain", 1.0)
    base_speed = self.params.get("speed", 0.2)
    base_fade = int(self.params.get("fade", 48))
    pi = _get_pal_idx(self.params, names=FELDSTEIN_PALETTE_NAMES, count=NUM_FELDSTEIN_PALETTES)

    # Audio modulation
    speed = base_speed * (1.0 + audio.bass * gain * 2.0)
    fade = int(max(10, min(200, base_fade - audio.buildup * gain * 30)))
    if audio.beat:
      self._hue = (self._hue + int(38 * gain)) % 256

    self._elapsed_ms += dt_ms
    time_val = int(self._elapsed_ms * speed) // 7 + self._zo
    SCALE = 180

    self._hue_accum += dt_ms
    if self._hue_accum >= 1000:
      self._hue = (self._hue + 1) % 256
      self._hue_accum -= 1000
    h = self._hue

    _pname, layers = FELDSTEIN_PALETTES[pi]
    h1_off, s1, _ = layers[0]
    h2_off, s2, _ = layers[1]
    h3_off, s3, _ = layers[2]

    self.buf.fade_by(fade)

    cols, rows = self.width, self.height
    x_idx = np.arange(cols, dtype=np.float64)
    y_idx = np.arange(rows, dtype=np.float64)
    xS = (x_idx * SCALE + self._xo)[:, np.newaxis] * np.ones(rows)
    yS = np.ones(cols)[:, np.newaxis] * (y_idx * SCALE + self._yo)

    for h_off, sat, (nx_div, ny_div, ny_off, nz_val) in [
      (h1_off, s1, (10, 50, time_val // 2, float(time_val))),
      (h2_off, s2, (10, 50, time_val // 2, float(time_val + 100 * SCALE))),
      (h3_off, s3, (100, 40, 0, float(time_val // 10 + 300 * SCALE))),
    ]:
      px = xS / nx_div / 256.0
      py = (yS / ny_div + ny_off) / 256.0
      pz = np.full_like(px, nz_val / 256.0)
      raw = (perlin_grid(px, py, pz) + 1.0) * 127.5
      raw = np.clip(raw, 0, 255).astype(np.int32)
      vals = raw - 128
      vals = np.clip(vals, 0, 255)
      vals = vals + ((vals * 128) >> 8)
      vals = np.clip(vals, 0, 255).astype(np.uint8)

      hue = (h + h_off) & 255
      r_c, g_c, b_c = hsv2rgb(hue, sat, 255)
      layer = np.zeros((cols, rows, 3), dtype=np.uint8)
      if r_c + g_c + b_c > 0:
        layer[..., 0] = (vals.astype(np.uint16) * r_c // 255).astype(np.uint8)
        layer[..., 1] = (vals.astype(np.uint16) * g_c // 255).astype(np.uint8)
        layer[..., 2] = (vals.astype(np.uint16) * b_c // 255).astype(np.uint8)
      self.buf.data = np.clip(
        self.buf.data.astype(np.int16) + layer.astype(np.int16), 0, 255
      ).astype(np.uint8)

    return self.buf.get_frame()

  def _calc_dt_ms(self, t):
    if self._last_t is None:
      self._last_t = t
      return 16.67
    dt = (t - self._last_t) * 1000.0
    self._last_t = t
    return max(0.0, dt)


SOUND_VARIANTS_EFFECTS = {
  'sr_feldstein': SRFeldstein,
}
