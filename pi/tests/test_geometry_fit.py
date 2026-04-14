"""Tests for geometry wizard — anchor-fit, interpolation, validation, spatial map."""

import numpy as np
from app.setup.geometry import (
  detect_blob_centroid, fit_strip_from_anchors,
  validate_fit, build_spatial_map, AnchorObservation,
  _interpolate_along_polyline,
)
from app.config.spatial_map import SpatialMap


def _make_dark_frame(h=100, w=100):
  return np.full((h, w, 3), 5, dtype=np.uint8)


def _make_blob_frame(h=100, w=100, cx=50, cy=50, radius=5, color=(200, 200, 200)):
  frame = np.full((h, w, 3), 5, dtype=np.uint8)
  for y in range(max(0, cy - radius), min(h, cy + radius)):
    for x in range(max(0, cx - radius), min(w, cx + radius)):
      if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
        frame[y, x] = color
  return frame


class TestBlobDetection:
  def test_detects_bright_blob(self):
    dark = _make_dark_frame()
    frame = _make_blob_frame(cx=50, cy=50)
    result = detect_blob_centroid(frame, dark)
    assert result is not None
    cx, cy, brightness = result
    assert 45 <= cx <= 55
    assert 45 <= cy <= 55
    assert brightness > 50

  def test_returns_none_for_dark(self):
    dark = _make_dark_frame()
    result = detect_blob_centroid(dark, dark)
    assert result is None

  def test_centroid_accuracy(self):
    dark = _make_dark_frame()
    frame = _make_blob_frame(cx=30, cy=70, radius=8)
    result = detect_blob_centroid(frame, dark)
    assert result is not None
    cx, cy, _ = result
    assert abs(cx - 30) < 3
    assert abs(cy - 70) < 3


class TestAnchorInterpolation:
  def test_interpolate_at_anchors(self):
    fracs = [0.0, 0.25, 0.5, 0.75, 1.0]
    uvs = [[0.1, 0.0], [0.1, 0.25], [0.1, 0.5], [0.1, 0.75], [0.1, 1.0]]
    u, v = _interpolate_along_polyline(0.0, fracs, uvs)
    assert abs(u - 0.1) < 0.01
    assert abs(v - 0.0) < 0.01

    u, v = _interpolate_along_polyline(0.5, fracs, uvs)
    assert abs(u - 0.1) < 0.01
    assert abs(v - 0.5) < 0.01

  def test_interpolate_between_anchors(self):
    fracs = [0.0, 0.5, 1.0]
    uvs = [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]
    u, v = _interpolate_along_polyline(0.25, fracs, uvs)
    assert abs(u - 0.25) < 0.01
    assert abs(v - 0.25) < 0.01

  def test_interpolate_beyond_bounds(self):
    fracs = [0.25, 0.75]
    uvs = [[0.2, 0.2], [0.8, 0.8]]
    u, v = _interpolate_along_polyline(0.0, fracs, uvs)
    assert abs(u - 0.2) < 0.01  # clamps to first anchor


class TestStripFit:
  def _make_vertical_anchors(self, strip_id=0, x_frac=0.1):
    return [
      AnchorObservation(strip_id, 0, x_frac * 100, 95, 200),
      AnchorObservation(strip_id, 1, x_frac * 100, 75, 200),
      AnchorObservation(strip_id, 2, x_frac * 100, 50, 200),
      AnchorObservation(strip_id, 3, x_frac * 100, 25, 200),
      AnchorObservation(strip_id, 4, x_frac * 100, 5, 200),
    ]

  def test_fit_produces_positions(self):
    anchors = self._make_vertical_anchors()
    fit = fit_strip_from_anchors(0, anchors, 172, 100, 100)
    assert fit.passed
    assert len(fit.positions) == 172
    assert fit.fit_method == 'anchor_polyline_v1'

  def test_positions_normalized_uv(self):
    anchors = self._make_vertical_anchors()
    fit = fit_strip_from_anchors(0, anchors, 172, 100, 100)
    for u, v in fit.positions:
      assert 0 <= u <= 1
      assert 0 <= v <= 1

  def test_insufficient_anchors_fails(self):
    anchors = [AnchorObservation(0, 0, 10, 95, 200)]
    fit = fit_strip_from_anchors(0, anchors, 172, 100, 100)
    assert not fit.passed

  def test_vertical_strip_positions_monotonic(self):
    """LED positions should progress from bottom to top."""
    anchors = self._make_vertical_anchors()
    fit = fit_strip_from_anchors(0, anchors, 172, 100, 100)
    vs = [p[1] for p in fit.positions]
    # Should be monotonically increasing (bottom to top)
    for i in range(1, len(vs)):
      assert vs[i] >= vs[i - 1] - 0.001


class TestFitValidation:
  def test_good_validation_passes(self):
    anchors = [
      AnchorObservation(0, 0, 10, 95, 200),
      AnchorObservation(0, 2, 10, 50, 200),
      AnchorObservation(0, 4, 10, 5, 200),
    ]
    fit = fit_strip_from_anchors(0, anchors, 100, 100, 100)
    # Validate with points close to predictions
    obs = [(25, fit.positions[25][0], fit.positions[25][1])]
    result = validate_fit(fit, obs, tolerance=0.05)
    assert result.passed

  def test_bad_validation_fails(self):
    anchors = [
      AnchorObservation(0, 0, 10, 95, 200),
      AnchorObservation(0, 4, 10, 5, 200),
    ]
    fit = fit_strip_from_anchors(0, anchors, 100, 100, 100)
    # Validate with a point far from prediction
    obs = [(50, 0.9, 0.9)]  # way off
    result = validate_fit(fit, obs, tolerance=0.05)
    assert not result.passed


class TestBuildSpatialMap:
  def test_builds_from_fits(self):
    anchors = [
      AnchorObservation(0, 0, 10, 95, 200),
      AnchorObservation(0, 2, 10, 50, 200),
      AnchorObservation(0, 4, 10, 5, 200),
    ]
    fit = fit_strip_from_anchors(0, anchors, 50, 100, 100)
    spatial_map = build_spatial_map([fit], [0])
    assert isinstance(spatial_map, SpatialMap)
    assert len(spatial_map.strips) == 1
    assert spatial_map.visible_strips == [0]

  def test_hidden_strips_excluded(self):
    spatial_map = build_spatial_map([], [])
    assert len(spatial_map.strips) == 0
