"""
Audio-reactive effects for the LED pillar.
"""

import math
import numpy as np

from .base import Effect, hsv_to_rgb, hex_to_rgb
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
  """Columns glow based on spectral energy."""

  def render(self, t: float, state) -> np.ndarray:
    elapsed = self.elapsed(t)
    smoothing = self.params.get('smoothing', 0.8)
    frame = np.zeros((self.width, self.height, 3), dtype=np.uint8)

    # Distribute frequency bands across columns
    bands = [state.audio_bass, state.audio_mid, state.audio_high]

    for x in range(self.width):
      # Map column to a frequency band with interpolation
      band_pos = x / self.width * (len(bands) - 1)
      band_idx = int(band_pos)
      frac = band_pos - band_idx
      if band_idx >= len(bands) - 1:
        level = bands[-1]
      else:
        level = bands[band_idx] * (1 - frac) + bands[band_idx + 1] * frac

      fill_h = int(level * self.height)
      hue = (x / self.width + elapsed * 0.05) % 1.0

      for y in range(fill_h):
        fade = 1.0 - y / self.height * 0.5
        r, g, b = hsv_to_rgb(hue, 0.8, fade)
        frame[x, y] = (r, g, b)

    return frame


AUDIO_EFFECTS = {
  'vu_pulse': VUPulse,
  'band_colors': BandColors,
  'beat_flash': BeatFlash,
  'energy_ring': EnergyRing,
  'spectral_glow': SpectralGlow,
}
