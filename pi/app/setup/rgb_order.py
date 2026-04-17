"""
RGB-order wizard — backend analysis for camera-assisted color order detection.

Analyzes still-frame captures (dark, red, green, blue) to infer the native
color order of each LED strip. Uses Pillow + NumPy, not OpenCV.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

# --- Color order permutation logic (relocated from legacy runtime_plan.py) ---

_RGB_INDEX = {'R': 0, 'G': 1, 'B': 2}


def _order_to_component_map(order: str) -> tuple[int, int, int]:
  """Map byte positions to RGB component indices for a given order string.

  For 'BGR': position 0 is B(=2), position 1 is G(=1), position 2 is R(=0)
  Returns: (2, 1, 0)
  """
  return tuple(_RGB_INDEX[c] for c in order)


def _invert_perm(perm: tuple[int, int, int]) -> tuple[int, int, int]:
  """Compute the inverse of a permutation."""
  inv = [0, 0, 0]
  for i, v in enumerate(perm):
    inv[v] = i
  return tuple(inv)


def derive_precontroller_swizzle(
  controller_wire_order: str,
  strip_native_order: str,
) -> tuple[int, int, int]:
  """Derive the permutation to apply to logical RGB pixels before sending
  to the controller, so that the strip displays the intended color.

  The OctoWS2811 controller assumes RGB input and reorders to match its
  configured strip type (controller_wire_order). If a strip's actual
  native order differs, we pre-compensate.

  Formula: swizzle[j] = strip_component[ctrl_inverse[j]]
  """
  ctrl_component = _order_to_component_map(controller_wire_order)
  ctrl_inverse = _invert_perm(ctrl_component)
  strip_component = _order_to_component_map(strip_native_order)
  return tuple(strip_component[ctrl_inverse[j]] for j in range(3))


def simulate_display(
  intended: tuple[int, int, int],
  swizzle: tuple[int, int, int],
  controller_wire_order: str,
  strip_native_order: str,
) -> tuple[int, int, int]:
  """Simulate what color a strip actually displays.

  Pipeline:
  1. Apply precontroller swizzle to intended RGB
  2. OctoWS2811 reorders assuming RGB input -> controller_wire_order output
  3. Strip interprets bytes according to its native order
  """
  # Step 1: swizzle
  after_swizzle = tuple(intended[swizzle[i]] for i in range(3))

  # Step 2: OctoWS2811 reorders from RGB input to controller_wire_order output
  ctrl_component = _order_to_component_map(controller_wire_order)
  wire = [0, 0, 0]
  for i in range(3):
    wire[i] = after_swizzle[ctrl_component[i]]

  # Step 3: strip interprets wire bytes according to its native order
  strip_component = _order_to_component_map(strip_native_order)
  displayed = [0, 0, 0]
  for i in range(3):
    displayed[strip_component[i]] = wire[i]

  return tuple(displayed)


# Default controller wire order (BGR for OctoWS2811 with BGR-native strips)
CONTROLLER_WIRE_ORDER = "BGR"

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
