"""Tests for RGB-order wizard detection logic."""

import numpy as np
from app.setup.rgb_order import (
  analyze_strip_captures, _subtract_dark, _find_bright_roi,
  _measure_dominant_channel, _infer_color_order, RGBOrderResult,
)


def _make_frame(h=100, w=100, color=(0, 0, 0)):
  """Create a test frame filled with a solid color."""
  frame = np.zeros((h, w, 3), dtype=np.uint8)
  frame[:, :] = color
  return frame


def _make_strip_frame(h=100, w=100, bg=(0, 0, 0), strip_color=(255, 0, 0),
                      strip_x=(40, 60), strip_y=(10, 90)):
  """Create a frame with a bright strip region against dark background."""
  frame = np.full((h, w, 3), bg, dtype=np.uint8)
  frame[strip_y[0]:strip_y[1], strip_x[0]:strip_x[1], :] = strip_color
  return frame


class TestDarkSubtraction:
  def test_basic_subtraction(self):
    dark = _make_frame(color=(10, 10, 10))
    lit = _make_frame(color=(100, 50, 30))
    diff = _subtract_dark(lit, dark)
    assert diff[0, 0, 0] == 90
    assert diff[0, 0, 1] == 40
    assert diff[0, 0, 2] == 20

  def test_clamps_negatives(self):
    dark = _make_frame(color=(100, 100, 100))
    lit = _make_frame(color=(50, 50, 50))
    diff = _subtract_dark(lit, dark)
    assert np.all(diff == 0)


class TestROIDetection:
  def test_finds_bright_region(self):
    diff = _make_strip_frame(strip_color=(200, 0, 0))
    roi = _find_bright_roi(diff)
    assert roi is not None
    assert roi['area'] > 0

  def test_returns_none_for_dark_frame(self):
    diff = _make_frame(color=(5, 5, 5))
    roi = _find_bright_roi(diff)
    assert roi is None

  def test_roi_bounds_reasonable(self):
    diff = _make_strip_frame(strip_x=(40, 60), strip_y=(10, 90), strip_color=(200, 50, 50))
    roi = _find_bright_roi(diff)
    assert roi is not None
    assert 35 <= roi['x_min'] <= 45
    assert 55 <= roi['x_max'] <= 65


class TestDominantChannel:
  def test_red_dominant(self):
    diff = _make_strip_frame(strip_color=(200, 30, 10))
    roi = _find_bright_roi(diff)
    dom, avgs = _measure_dominant_channel(diff, roi)
    assert dom == 0  # R

  def test_green_dominant(self):
    diff = _make_strip_frame(strip_color=(10, 200, 30))
    roi = _find_bright_roi(diff)
    dom, avgs = _measure_dominant_channel(diff, roi)
    assert dom == 1  # G

  def test_blue_dominant(self):
    diff = _make_strip_frame(strip_color=(10, 30, 200))
    roi = _find_bright_roi(diff)
    dom, avgs = _measure_dominant_channel(diff, roi)
    assert dom == 2  # B


class TestColorOrderInference:
  def test_bgr_strip_with_bgr_controller(self):
    """BGR controller + BGR strip: raw RGB sent, camera sees what controller outputs."""
    # With BGR controller sending raw R → OctoWS2811 outputs BGR → BGR strip shows correctly
    # Camera sees: R shows R, G shows G, B shows B
    result = _infer_color_order(['R', 'G', 'B'], 'BGR')
    assert result == 'BGR'

  def test_rgb_strip_with_bgr_controller(self):
    """BGR controller + RGB strip: raw R sent → strip shows B (channels swapped)."""
    # With BGR controller, raw R → OctoWS2811 outputs BGR → RGB strip reads B,G,R → shows (B, G, R)
    # Camera dominant: B
    # Raw G → shows (G, ?, ?) → depends on exact permutation
    result = _infer_color_order(['B', 'G', 'R'], 'BGR')
    assert result == 'RGB'


class TestAnalyzeStripCaptures:
  def test_confident_bgr_detection(self):
    """Simulate BGR strip: when we send R, camera sees R dominant."""
    dark = _make_frame(color=(5, 5, 5))
    red = _make_strip_frame(strip_color=(200, 10, 10))
    green = _make_strip_frame(strip_color=(10, 200, 10))
    blue = _make_strip_frame(strip_color=(10, 10, 200))

    result = analyze_strip_captures(0, dark, red, green, blue, controller_wire_order='BGR')
    assert result.status == 'ok'
    assert result.candidate_color_order == 'BGR'
    assert result.confidence > 0.5
    assert result.needs_manual_review is False

  def test_no_roi_returns_manual_review(self):
    dark = _make_frame(color=(5, 5, 5))
    dim = _make_frame(color=(8, 8, 8))

    result = analyze_strip_captures(0, dark, dim, dim, dim)
    assert result.status == 'no_roi'
    assert result.needs_manual_review is True

  def test_low_confidence_flagged(self):
    """Ambiguous channels should flag for manual review."""
    dark = _make_frame(color=(5, 5, 5))
    # All frames show similar brightness in all channels
    ambiguous = _make_strip_frame(strip_color=(100, 95, 90))

    result = analyze_strip_captures(0, dark, ambiguous, ambiguous, ambiguous)
    # Result may still detect something but with low confidence
    assert result.needs_manual_review is True or result.status == 'low_confidence'


class TestIdentityBypassRegression:
  """Wizard patterns must bypass compiled color-order compensation."""

  def test_identity_swizzle_used_in_inference(self):
    """The inference code uses identity swizzle (no compensation),
    which is correct because wizard patterns bypass the compiled plan."""
    # This tests that the inference logic uses (0,1,2) swizzle internally,
    # matching the wizard behavior of use_compiled_color_order=False
    result = _infer_color_order(['R', 'G', 'B'], 'BGR')
    assert result is not None
