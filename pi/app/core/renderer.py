"""
Core render loop.

Manages the scene → render → map → send pipeline at the target FPS.
"""

import asyncio
import logging
import time
from typing import Optional

import numpy as np

from ..mapping.cylinder import map_frame_fast, serialize_channels, downsample_width, N
from ..transport.usb import TeensyTransport

logger = logging.getLogger(__name__)


class RenderState:
  """Shared mutable state for the current render."""

  def __init__(self):
    self.brightness: float = 0.8
    self.gamma: float = 2.2
    self.target_fps: int = 60
    self.current_scene: Optional[str] = None
    self.blackout: bool = False

    # Audio modulation (updated by audio worker)
    self.audio_level: float = 0.0
    self.audio_bass: float = 0.0
    self.audio_mid: float = 0.0
    self.audio_high: float = 0.0
    self.audio_beat: bool = False
    self.audio_bpm: float = 0.0

    # Stats
    self.actual_fps: float = 0.0
    self.frame_count: int = 0
    self.dropped_frames: int = 0
    self.last_frame_time_ms: float = 0.0

  def to_dict(self) -> dict:
    return {
      'brightness': self.brightness,
      'target_fps': self.target_fps,
      'actual_fps': round(self.actual_fps, 1),
      'current_scene': self.current_scene,
      'blackout': self.blackout,
      'frame_count': self.frame_count,
      'dropped_frames': self.dropped_frames,
      'last_frame_time_ms': round(self.last_frame_time_ms, 2),
      'audio_level': round(self.audio_level, 3),
      'audio_beat': self.audio_beat,
    }


# Precomputed gamma LUT
def _build_gamma_lut(gamma: float) -> np.ndarray:
  lut = np.zeros(256, dtype=np.uint8)
  for i in range(256):
    lut[i] = int(pow(i / 255.0, gamma) * 255.0 + 0.5)
  return lut


class Renderer:
  def __init__(self, transport: TeensyTransport, state: RenderState,
               internal_width: int = 40):
    self.transport = transport
    self.state = state
    self.internal_width = internal_width
    self.effect_registry: dict = {}
    self.current_effect = None
    self._running = False
    self._gamma_lut = _build_gamma_lut(state.gamma)
    self._fps_samples: list[float] = []
    self._fps_window = 60

  def register_effect(self, name: str, effect_class):
    self.effect_registry[name] = effect_class

  def set_scene(self, scene_name: str, params: Optional[dict] = None):
    if scene_name not in self.effect_registry:
      logger.warning(f"Unknown effect: {scene_name}")
      return False

    effect_cls = self.effect_registry[scene_name]
    self.current_effect = effect_cls(
      width=self.internal_width,
      height=N,
      params=params or {},
    )
    self.state.current_scene = scene_name
    logger.info(f"Scene set: {scene_name}")
    return True

  async def run(self):
    """Main render loop."""
    self._running = True
    logger.info(f"Render loop started at {self.state.target_fps} FPS target")

    while self._running:
      frame_start = time.monotonic()
      target_interval = 1.0 / self.state.target_fps

      try:
        await self._render_frame()
      except Exception as e:
        logger.error(f"Render error: {e}", exc_info=True)
        self.state.dropped_frames += 1

      # Frame timing
      elapsed = time.monotonic() - frame_start
      self.state.last_frame_time_ms = elapsed * 1000

      # FPS tracking
      self._fps_samples.append(elapsed)
      if len(self._fps_samples) > self._fps_window:
        self._fps_samples.pop(0)
      if self._fps_samples:
        avg = sum(self._fps_samples) / len(self._fps_samples)
        self.state.actual_fps = 1.0 / avg if avg > 0 else 0

      # Sleep for remainder of frame budget
      remaining = target_interval - elapsed
      if remaining > 0:
        await asyncio.sleep(remaining)
      else:
        self.state.dropped_frames += 1

  async def _render_frame(self):
    """Render one frame and send to Teensy."""
    if self.state.blackout:
      channel_data = np.zeros((5, 344, 3), dtype=np.uint8)
    elif self.current_effect is None:
      # No effect active — show dim idle pattern
      channel_data = np.zeros((5, 344, 3), dtype=np.uint8)
    else:
      # Generate effect frame on internal canvas
      t = time.monotonic()
      internal_frame = self.current_effect.render(t, self.state)

      # Downsample to physical width if needed
      if internal_frame.shape[0] != 10:
        logical_frame = downsample_width(internal_frame, 10)
      else:
        logical_frame = internal_frame

      # Apply brightness
      logical_frame = (logical_frame * self.state.brightness).astype(np.uint8)

      # Apply gamma correction
      logical_frame = self._gamma_lut[logical_frame]

      # Map to electrical channels
      channel_data = map_frame_fast(logical_frame)

    # Serialize and send
    pixel_bytes = serialize_channels(channel_data)
    await self.transport.send_frame(pixel_bytes)
    self.state.frame_count += 1

  def stop(self):
    self._running = False

  def update_gamma(self, gamma: float):
    self.state.gamma = gamma
    self._gamma_lut = _build_gamma_lut(gamma)
