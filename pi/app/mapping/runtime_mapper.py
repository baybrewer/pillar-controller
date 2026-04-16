"""
Plan-driven runtime mapper.

Replaces the hardcoded cylinder.py mapping with a compiled-plan-driven
approach that supports per-strip color order, direction, and LED count.
"""

import numpy as np

from .runtime_plan import CompiledOutputPlan, CompiledStripPlan


def map_frame_compiled(logical_frame: np.ndarray, plan: CompiledOutputPlan) -> np.ndarray:
  """Map a logical frame to channel data using the compiled output plan.

  logical_frame: shape (logical_width, logical_height, 3) uint8
  Returns: shape (channels, leds_per_channel, 3) uint8
  """
  channel_data = np.zeros(
    (plan.channels, plan.leds_per_channel, 3), dtype=np.uint8,
  )

  for strip in plan.strips:
    if not strip.enabled:
      continue
    if strip.logical_order >= logical_frame.shape[0]:
      continue

    # Extract the logical column for this strip
    col = logical_frame[strip.logical_order, :, :]

    # Truncate to installed LED count
    led_count = min(strip.installed_led_count, col.shape[0])
    col = col[:led_count, :]

    # Reverse if direction is top-to-bottom
    if strip.direction == "top_to_bottom":
      col = col[::-1, :]

    # Apply per-strip brightness multiplier
    if strip.brightness < 1.0:
      col = (col * strip.brightness).astype(np.uint8)

    # Apply precontroller swizzle if not identity
    swizzle = strip.precontroller_swizzle
    if swizzle != (0, 1, 2):
      col = col[:, swizzle]

    # Place into channel data at the correct offset
    offset = strip.output_offset
    channel_data[strip.output_channel, offset:offset + led_count, :] = col

  return channel_data


def serialize_channels_compiled(channel_data: np.ndarray) -> bytes:
  """Serialize channel data to bytes for USB transport."""
  return channel_data.tobytes()
