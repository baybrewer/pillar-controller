"""
Shared helpers for imported led_sim.py effects.

Provides palette sampling, noise functions, and buffer management
that multiple imported effects need. No Pygame dependencies.
"""

import math
import numpy as np


def hsv_to_rgb_fast(h: float, s: float, v: float) -> tuple[int, int, int]:
  """Fast HSV to RGB conversion. h, s, v in [0, 1]."""
  if s == 0:
    val = int(v * 255)
    return val, val, val
  i = int(h * 6.0) % 6
  f = (h * 6.0) - int(h * 6.0)
  p = v * (1.0 - s)
  q = v * (1.0 - s * f)
  t = v * (1.0 - s * (1.0 - f))
  if i == 0: r, g, b = v, t, p
  elif i == 1: r, g, b = q, v, p
  elif i == 2: r, g, b = p, v, t
  elif i == 3: r, g, b = p, q, v
  elif i == 4: r, g, b = t, p, v
  else: r, g, b = v, p, q
  return int(r * 255), int(g * 255), int(b * 255)


def palette_lerp(colors: list[tuple], t: float) -> tuple[int, int, int]:
  """Sample a color palette at position t (0-1, wrapping)."""
  t = t % 1.0
  n = len(colors)
  scaled = t * n
  idx = int(scaled)
  frac = scaled - idx
  c1 = colors[idx % n]
  c2 = colors[(idx + 1) % n]
  return (
    int(c1[0] + (c2[0] - c1[0]) * frac),
    int(c1[1] + (c2[1] - c1[1]) * frac),
    int(c1[2] + (c2[2] - c1[2]) * frac),
  )


def simplex_noise_2d(x: float, y: float) -> float:
  """Simple 2D value noise (not true simplex, but good enough for effects)."""
  # Use a hash-based approach for quick pseudo-noise
  ix = int(math.floor(x))
  iy = int(math.floor(y))
  fx = x - ix
  fy = y - iy
  # Smoothstep
  fx = fx * fx * (3 - 2 * fx)
  fy = fy * fy * (3 - 2 * fy)
  # Corner values
  def _hash(x, y):
    n = x * 374761393 + y * 668265263
    n = (n ^ (n >> 13)) * 1274126177
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 4294967295.0
  n00 = _hash(ix, iy)
  n10 = _hash(ix + 1, iy)
  n01 = _hash(ix, iy + 1)
  n11 = _hash(ix + 1, iy + 1)
  return n00 * (1 - fx) * (1 - fy) + n10 * fx * (1 - fy) + n01 * (1 - fx) * fy + n11 * fx * fy


# Common palettes for imported effects
FIRE_PALETTE = [
  (0, 0, 0), (128, 17, 0), (182, 34, 0), (215, 53, 2),
  (252, 100, 0), (255, 117, 0), (250, 192, 0), (255, 255, 50),
]

OCEAN_PALETTE = [
  (0, 0, 30), (0, 20, 80), (0, 50, 120), (0, 100, 180),
  (20, 150, 200), (50, 200, 220), (100, 220, 240), (150, 240, 255),
]

AURORA_PALETTE = [
  (0, 20, 0), (0, 80, 40), (0, 150, 80), (20, 200, 100),
  (80, 220, 150), (40, 180, 200), (20, 100, 180), (0, 50, 100),
]

LAVA_PALETTE = [
  (20, 0, 0), (80, 0, 0), (150, 20, 0), (200, 50, 0),
  (255, 80, 0), (255, 120, 20), (255, 160, 50), (200, 80, 0),
]
