"""
Geometry wizard — anchor-fit front-projection solver.

Solves visible strip LED positions from captured anchor images.
Uses anchor-fit first, dense scan only as fallback for failed strips.
"""

import logging
import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..config.spatial_map import SpatialMap, StripGeometry

logger = logging.getLogger(__name__)

MIN_BRIGHTNESS = 40
MIN_BLOB_AREA = 10


@dataclass
class AnchorObservation:
  strip_id: int
  anchor_index: int  # 0=0%, 1=25%, 2=50%, 3=75%, 4=100%
  centroid_x: float
  centroid_y: float
  brightness: float


@dataclass
class StripFitResult:
  strip_id: int
  anchors: list[list[float]]
  positions: list[list[float]]
  fit_method: str
  mean_error: float
  max_error: float
  passed: bool


def detect_blob_centroid(
  frame: np.ndarray,
  dark_frame: np.ndarray,
  threshold: int = MIN_BRIGHTNESS,
) -> Optional[tuple[float, float, float]]:
  """Find the centroid of the brightest blob in a difference image.

  Returns (x, y, brightness) or None if no blob found.
  """
  diff = np.clip(frame.astype(np.int16) - dark_frame.astype(np.int16), 0, 255).astype(np.uint8)
  brightness = np.max(diff, axis=2)
  mask = brightness > threshold

  if not np.any(mask):
    return None

  ys, xs = np.where(mask)
  if len(ys) < MIN_BLOB_AREA:
    return None

  weights = brightness[mask].astype(np.float64)
  total_weight = weights.sum()
  if total_weight == 0:
    return None

  cx = float(np.average(xs.astype(np.float64), weights=weights))
  cy = float(np.average(ys.astype(np.float64), weights=weights))
  avg_brightness = float(weights.mean())

  return (cx, cy, avg_brightness)


def fit_strip_from_anchors(
  strip_id: int,
  anchors: list[AnchorObservation],
  installed_led_count: int,
  image_width: int,
  image_height: int,
) -> StripFitResult:
  """Fit a polyline through anchor observations and interpolate LED positions.

  Anchors are at 0%, 25%, 50%, 75%, 100% of the strip.
  Positions are normalized to UV [0,1] with origin at bottom-left.
  """
  if len(anchors) < 2:
    return StripFitResult(
      strip_id=strip_id, anchors=[], positions=[],
      fit_method='insufficient_anchors', mean_error=float('inf'),
      max_error=float('inf'), passed=False,
    )

  # Sort anchors by index
  sorted_anchors = sorted(anchors, key=lambda a: a.anchor_index)

  # Normalize to UV: x/width, flip y (image y=0 is top, UV y=0 is bottom)
  anchor_uvs = []
  for a in sorted_anchors:
    u = a.centroid_x / image_width
    v = 1.0 - (a.centroid_y / image_height)
    anchor_uvs.append([round(u, 4), round(v, 4)])

  # Anchor LED indices (fraction of total)
  anchor_fracs = [a.anchor_index / 4.0 for a in sorted_anchors]

  # Interpolate all LED positions along the polyline
  positions = []
  for led_idx in range(installed_led_count):
    frac = led_idx / max(installed_led_count - 1, 1)

    # Find which segment this LED falls in
    u, v = _interpolate_along_polyline(frac, anchor_fracs, anchor_uvs)
    positions.append([round(u, 5), round(v, 5)])

  return StripFitResult(
    strip_id=strip_id,
    anchors=anchor_uvs,
    positions=positions,
    fit_method='anchor_polyline_v1',
    mean_error=0.0,  # Populated during validation
    max_error=0.0,
    passed=True,
  )


def _interpolate_along_polyline(
  frac: float,
  anchor_fracs: list[float],
  anchor_uvs: list[list[float]],
) -> tuple[float, float]:
  """Interpolate a position along a polyline defined by anchors."""
  if frac <= anchor_fracs[0]:
    return anchor_uvs[0][0], anchor_uvs[0][1]
  if frac >= anchor_fracs[-1]:
    return anchor_uvs[-1][0], anchor_uvs[-1][1]

  for i in range(len(anchor_fracs) - 1):
    if anchor_fracs[i] <= frac <= anchor_fracs[i + 1]:
      seg_len = anchor_fracs[i + 1] - anchor_fracs[i]
      if seg_len == 0:
        t = 0
      else:
        t = (frac - anchor_fracs[i]) / seg_len
      u = anchor_uvs[i][0] + t * (anchor_uvs[i + 1][0] - anchor_uvs[i][0])
      v = anchor_uvs[i][1] + t * (anchor_uvs[i + 1][1] - anchor_uvs[i][1])
      return u, v

  return anchor_uvs[-1][0], anchor_uvs[-1][1]


def validate_fit(
  fit: StripFitResult,
  validation_observations: list[tuple[int, float, float]],
  tolerance: float = 0.05,
) -> StripFitResult:
  """Validate a strip fit against observed sample LED positions.

  validation_observations: list of (led_index, observed_u, observed_v)
  tolerance: max acceptable error in UV space
  """
  if not fit.passed or not validation_observations or not fit.positions:
    return fit

  errors = []
  for led_idx, obs_u, obs_v in validation_observations:
    if led_idx < len(fit.positions):
      pred_u, pred_v = fit.positions[led_idx]
      err = math.sqrt((pred_u - obs_u) ** 2 + (pred_v - obs_v) ** 2)
      errors.append(err)

  if errors:
    mean_err = sum(errors) / len(errors)
    max_err = max(errors)
    passed = max_err < tolerance

    return StripFitResult(
      strip_id=fit.strip_id,
      anchors=fit.anchors,
      positions=fit.positions,
      fit_method=fit.fit_method,
      mean_error=round(mean_err, 5),
      max_error=round(max_err, 5),
      passed=passed,
    )

  return fit


def build_spatial_map(
  fits: list[StripFitResult],
  visible_strip_ids: list[int],
  camera_resolution: tuple[int, int] = (1280, 720),
) -> SpatialMap:
  """Build a SpatialMap from validated strip fits."""
  strips = []
  for fit in fits:
    if fit.passed and fit.positions:
      strips.append(StripGeometry(
        id=fit.strip_id,
        anchors=fit.anchors,
        positions=fit.positions,
        fit_method=fit.fit_method,
        visibility='direct' if fit.strip_id in visible_strip_ids else 'inferred',
      ))

  return SpatialMap(
    visible_strips=visible_strip_ids,
    strips=strips,
    camera_resolution=list(camera_resolution),
  )
