"""
Audio-reactive effects for the LED pillar.
"""

import math
import numpy as np

from .base import Effect, hsv_to_rgb, hex_to_rgb
from .generative import _hsv_array_to_rgb
from ..mapping.cylinder import N


class VUPulse(Effect):
  """VU meter-style pulse from bottom."""

  def render(self, t: float, state) -> np.ndarray:
    sensitivity = self.params.get('sensitivity', 1.0)
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)

    level = min(1.0, state.audio_level * sensitivity)
    fill_height = int(level * self.height)

    for y in range(fill_height):
      frac = y / self.height
      if frac < 0.6:
        color = (0, 255, 0)
      elif frac < 0.85:
        color = (255, 255, 0)
      else:
        color = (255, 0, 0)
      frame[:, y] = color

    return frame


class BandColors(Effect):
  """Low/mid/high frequency bands as colored sections."""

  def render(self, t: float, state) -> np.ndarray:
    low_color = hex_to_rgb(self.params.get('low_color', '#FF0000'))
    mid_color = hex_to_rgb(self.params.get('mid_color', '#00FF00'))
    high_color = hex_to_rgb(self.params.get('high_color', '#0000FF'))
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)

    third = self.height // 3

    # Low band — bottom third
    low_h = int(state.audio_bass * third)
    for y in range(low_h):
      frame[:, y] = low_color

    # Mid band — middle third
    mid_h = int(state.audio_mid * third)
    for y in range(third, third + mid_h):
      frame[:, y] = mid_color

    # High band — top third
    high_h = int(state.audio_high * third)
    for y in range(2 * third, 2 * third + high_h):
      frame[:, y] = high_color

    return frame


class BeatFlash(Effect):
  """Flash on beat detection."""

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._flash_level = 0.0

  def render(self, t: float, state) -> np.ndarray:
    decay = self.params.get('decay', 0.9)
    color = hex_to_rgb(self.params.get('color', '#FFFFFF'))
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)

    if state.audio_beat:
      self._flash_level = 1.0
    else:
      self._flash_level *= decay

    if self._flash_level > 0.01:
      c = tuple(int(v * self._flash_level) for v in color)
      frame[:, :] = c

    return frame


class EnergyRing(Effect):
  """Rotating energy ring driven by audio."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    speed = self.params.get('speed', 2.0)
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)

    # Ring position driven by audio + time
    ring_y = int((elapsed * speed * 10 + state.audio_level * 50) % self.height)
    ring_width = max(2, int(state.audio_level * 20))

    for y in range(self.height):
      dist = min(abs(y - ring_y), self.height - abs(y - ring_y))
      if dist < ring_width:
        fade = 1.0 - dist / ring_width
        for x in range(self.width):
          hue = (x / self.width + elapsed * 0.1) % 1.0
          r, g, b = hsv_to_rgb(hue, 1.0, fade)
          frame[x, y] = (r, g, b)

    return frame


class SpectralGlow(Effect):
  """Columns glow based on spectral energy. Bars grow upward from the bottom,
  brightest at the top of each bar (like a flame tip)."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    gain = self.params.get('gain', 1.0)
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)

    bands = [state.audio_bass, state.audio_mid, state.audio_high]

    # Compute per-column fill heights via interpolation
    col_pos = np.arange(self.width, dtype=np.float64) / self.width * (len(bands) - 1)
    band_idx = np.minimum(col_pos.astype(np.int32), len(bands) - 2)
    frac = col_pos - band_idx
    band_arr = np.array(bands, dtype=np.float64)
    levels = band_arr[band_idx] * (1 - frac) + band_arr[band_idx + 1] * frac
    fill_heights = np.clip((levels * gain * self.height).astype(np.int32), 0, self.height)

    # Per-column hue
    hue_base = (np.arange(self.width, dtype=np.float64) / self.width + elapsed * 0.05) % 1.0

    # Lit mask: y < fill_height (y=0 is bottom in logical coords, so bars grow up)
    y_grid = np.arange(self.height, dtype=np.int32)[np.newaxis, :]
    fill_grid = fill_heights[:, np.newaxis]
    lit_mask = y_grid < fill_grid

    # Inverted fade: brightest at the TOP of each column (y=height-1 → 1.0),
    # dimmer near the base (y=0 → 0.5). Fixes perceived upside-down look.
    y_frac = np.arange(self.height, dtype=np.float64) / self.height
    fade = 0.5 + y_frac * 0.5

    hue_grid = np.broadcast_to(hue_base[:, np.newaxis], (self.width, self.height))
    rgb = _hsv_array_to_rgb(hue_grid, 0.8, 1.0)
    rgb_faded = (rgb.astype(np.float32) * fade[np.newaxis, :, np.newaxis]).astype(np.uint8)

    frame[lit_mask] = rgb_faded[lit_mask]
    return frame


AUDIO_EFFECTS = {
  'vu_pulse': VUPulse,
  'band_colors': BandColors,
  'beat_flash': BeatFlash,
  'energy_ring': EnergyRing,
  'spectral_glow': SpectralGlow,
}
