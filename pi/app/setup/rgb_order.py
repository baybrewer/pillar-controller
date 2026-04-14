"""
RGB-order wizard — backend analysis for camera-assisted color order detection.

Analyzes still-frame captures (dark, red, green, blue) to infer the native
color order of each LED strip. Uses Pillow + NumPy, not OpenCV.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..mapping.runtime_plan import derive_precontroller_swizzle, simulate_display
from ..hardware_constants import CONTROLLER_WIRE_ORDER

logger = logging.getLogger(__name__)

# Confidence thresholds
MIN_ROI_AREA = 50
MIN_CHANNEL_SEPARATION = 0.3
MIN_BRIGHTNESS = 30


@dataclass
class RGBOrderResult:
  strip_id: int
  observed_sequence: list[str]
  candidate_color_order: str
  confidence: float
  status: str  # "ok" | "low_confidence" | "no_roi" | "error"
  needs_manual_review: bool
  debug: dict


def _subtract_dark(lit: np.ndarray, dark: np.ndarray) -> np.ndarray:
  """Subtract dark frame from lit frame, clamping negatives."""
  return np.clip(lit.astype(np.int16) - dark.astype(np.int16), 0, 255).astype(np.uint8)


def _find_bright_roi(diff: np.ndarray, threshold: int = MIN_BRIGHTNESS) -> Optional[dict]:
  """Find the bounding box of the bright region in a difference frame."""
  brightness = np.max(diff, axis=2)
  mask = brightness > threshold
  if not np.any(mask):
    return None

  ys, xs = np.where(mask)
  area = len(ys)
  if area < MIN_ROI_AREA:
    return None

  return {
    'x_min': int(xs.min()),
    'x_max': int(xs.max()),
    'y_min': int(ys.min()),
    'y_max': int(ys.max()),
    'area': area,
  }


def _measure_dominant_channel(diff: np.ndarray, roi: dict) -> tuple[int, list[float]]:
  """Measure average channel values in the ROI, return (dominant_index, averages)."""
  region = diff[roi['y_min']:roi['y_max']+1, roi['x_min']:roi['x_max']+1, :]
  averages = [float(region[:, :, c].mean()) for c in range(3)]
  dominant = int(np.argmax(averages))
  return dominant, averages


def _infer_color_order(
  observed_sequence: list[str],
  controller_wire_order: str,
) -> Optional[str]:
  """Infer the strip native order from the observed dominant channels.

  During the wizard, raw RGB is sent WITHOUT compiled color-order compensation.
  We sent logical R, G, B and observed which camera channels lit up.
  The observed sequence tells us how the strip interprets raw bytes.
  """
  # We sent raw [R, G, B] bytes (no swizzle)
  # The controller reorders for its configured strip type
  # The actual strip interprets and shows some color
  # We observe that color via camera

  # For each candidate strip order, simulate what we'd observe
  channel_names = ['R', 'G', 'B']
  for candidate in ["RGB", "RBG", "GRB", "GBR", "BRG", "BGR"]:
    predicted = []
    identity_swizzle = (0, 1, 2)  # no compensation during wizard

    for test_color in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
      displayed = simulate_display(
        test_color, identity_swizzle, controller_wire_order, candidate,
      )
      # Camera sees the dominant displayed channel
      dominant_idx = max(range(3), key=lambda i: displayed[i])
      predicted.append(channel_names[dominant_idx])

    if predicted == observed_sequence:
      return candidate

  return None


def analyze_strip_captures(
  strip_id: int,
  dark_frame: np.ndarray,
  red_frame: np.ndarray,
  green_frame: np.ndarray,
  blue_frame: np.ndarray,
  controller_wire_order: str = CONTROLLER_WIRE_ORDER,
) -> RGBOrderResult:
  """Analyze captured frames for a single strip to determine its native color order.

  All frames should be numpy arrays of shape (height, width, 3) uint8.
  """
  channel_names = ['R', 'G', 'B']
  observed_sequence = []
  debug_info = {'channels': {}}
  total_separation = 0.0

  for test_name, lit_frame in [('red', red_frame), ('green', green_frame), ('blue', blue_frame)]:
    diff = _subtract_dark(lit_frame, dark_frame)
    roi = _find_bright_roi(diff)

    if roi is None:
      return RGBOrderResult(
        strip_id=strip_id,
        observed_sequence=[],
        candidate_color_order="",
        confidence=0.0,
        status="no_roi",
        needs_manual_review=True,
        debug={'error': f'No bright ROI found for {test_name} frame'},
      )

    dominant, averages = _measure_dominant_channel(diff, roi)
    observed_sequence.append(channel_names[dominant])

    # Channel separation: how much stronger is dominant vs next
    sorted_avgs = sorted(averages, reverse=True)
    if sorted_avgs[0] > 0:
      separation = 1.0 - (sorted_avgs[1] / sorted_avgs[0])
    else:
      separation = 0.0
    total_separation += separation

    debug_info['channels'][test_name] = {
      'dominant': channel_names[dominant],
      'averages': [round(a, 1) for a in averages],
      'separation': round(separation, 3),
      'roi_area': roi['area'],
    }

  avg_separation = total_separation / 3
  candidate = _infer_color_order(observed_sequence, controller_wire_order)

  if candidate is None:
    return RGBOrderResult(
      strip_id=strip_id,
      observed_sequence=observed_sequence,
      candidate_color_order="",
      confidence=0.0,
      status="low_confidence",
      needs_manual_review=True,
      debug=debug_info,
    )

  confidence = min(1.0, avg_separation / 0.5)
  needs_review = confidence < 0.7 or avg_separation < MIN_CHANNEL_SEPARATION

  return RGBOrderResult(
    strip_id=strip_id,
    observed_sequence=observed_sequence,
    candidate_color_order=candidate,
    confidence=round(confidence, 2),
    status="ok" if not needs_review else "low_confidence",
    needs_manual_review=needs_review,
    debug=debug_info,
  )
