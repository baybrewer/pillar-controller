"""Tests for runtime mapper parity with legacy cylinder.py mapper.

The critical gate: the default migrated installation must produce
byte-identical output to the old hardcoded mapper.
"""

import numpy as np

from app.mapping.cylinder import map_frame_fast, serialize_channels
from app.mapping.runtime_mapper import map_frame_compiled, serialize_channels_compiled
from app.mapping.runtime_plan import (
  compile_output_plan, load_controller_profile, ControllerProfile,
)
from app.config.installation import synthesize_default_installation
from app.hardware_constants import STRIPS, LEDS_PER_STRIP, CHANNELS, LEDS_PER_CHANNEL


def _make_test_frame(seed: int = 42) -> np.ndarray:
  """Create a deterministic test frame with varied pixel values."""
  rng = np.random.RandomState(seed)
  return rng.randint(0, 256, (STRIPS, LEDS_PER_STRIP, 3), dtype=np.uint8)


def _get_default_plan():
  """Get a compiled plan from the default installation."""
  installation = synthesize_default_installation()
  controller = load_controller_profile()
  return compile_output_plan(installation, controller)


class TestLegacyParity:
  """The hard gate: default migrated plan must match legacy mapper byte-for-byte."""

  def test_random_frame_parity(self):
    plan = _get_default_plan()
    frame = _make_test_frame(seed=42)

    legacy_channels = map_frame_fast(frame)
    new_channels = map_frame_compiled(frame, plan)

    np.testing.assert_array_equal(
      new_channels, legacy_channels,
      err_msg="Compiled mapper output differs from legacy mapper",
    )

  def test_serialized_bytes_parity(self):
    plan = _get_default_plan()
    frame = _make_test_frame(seed=99)

    legacy_channels = map_frame_fast(frame)
    new_channels = map_frame_compiled(frame, plan)

    legacy_bytes = serialize_channels(legacy_channels)
    new_bytes = serialize_channels_compiled(new_channels)

    assert legacy_bytes == new_bytes, "Serialized bytes differ"

  def test_all_zeros_parity(self):
    plan = _get_default_plan()
    frame = np.zeros((STRIPS, LEDS_PER_STRIP, 3), dtype=np.uint8)

    legacy = map_frame_fast(frame)
    new = map_frame_compiled(frame, plan)
    np.testing.assert_array_equal(new, legacy)

  def test_all_ones_parity(self):
    plan = _get_default_plan()
    frame = np.full((STRIPS, LEDS_PER_STRIP, 3), 255, dtype=np.uint8)

    legacy = map_frame_fast(frame)
    new = map_frame_compiled(frame, plan)
    np.testing.assert_array_equal(new, legacy)

  def test_single_pixel_per_strip_parity(self):
    """Test with only one pixel lit per strip to catch offset bugs."""
    plan = _get_default_plan()
    frame = np.zeros((STRIPS, LEDS_PER_STRIP, 3), dtype=np.uint8)
    for x in range(STRIPS):
      frame[x, x * 10, :] = [100 + x * 10, 50 + x * 5, 200 - x * 15]

    legacy = map_frame_fast(frame)
    new = map_frame_compiled(frame, plan)
    np.testing.assert_array_equal(new, legacy)

  def test_multiple_seeds_parity(self):
    """Run parity check across many random seeds."""
    plan = _get_default_plan()
    for seed in range(10):
      frame = _make_test_frame(seed=seed)
      legacy = map_frame_fast(frame)
      new = map_frame_compiled(frame, plan)
      np.testing.assert_array_equal(
        new, legacy,
        err_msg=f"Parity failure at seed={seed}",
      )


class TestCompiledPlanShape:
  def test_output_shape(self):
    plan = _get_default_plan()
    frame = _make_test_frame()
    result = map_frame_compiled(frame, plan)
    assert result.shape == (CHANNELS, LEDS_PER_CHANNEL, 3)
    assert result.dtype == np.uint8

  def test_plan_dimensions(self):
    plan = _get_default_plan()
    assert plan.channels == CHANNELS
    assert plan.leds_per_channel == LEDS_PER_CHANNEL
    assert plan.logical_width == STRIPS
    assert plan.logical_height == LEDS_PER_STRIP

  def test_strip_count(self):
    plan = _get_default_plan()
    assert len(plan.strips) == STRIPS

  def test_all_strips_identity_swizzle(self):
    """Default installation: all BGR strips with BGR controller = identity swizzle."""
    plan = _get_default_plan()
    for strip in plan.strips:
      assert strip.precontroller_swizzle == (0, 1, 2), (
        f"Strip {strip.strip_id} has non-identity swizzle: {strip.precontroller_swizzle}"
      )


class TestVariableLedCount:
  def test_shorter_strip_zero_pads(self):
    """A strip with fewer LEDs should zero-pad the remainder."""
    installation = synthesize_default_installation()
    installation.strips[0].installed_led_count = 100  # shorter than 172
    controller = load_controller_profile()
    plan = compile_output_plan(installation, controller)

    frame = np.full((STRIPS, LEDS_PER_STRIP, 3), 128, dtype=np.uint8)
    result = map_frame_compiled(frame, plan)

    # Channel 0, slot 0 (strip 0): first 100 should be 128, rest should be 0
    assert np.all(result[0, :100, :] == 128)
    assert np.all(result[0, 100:172, :] == 0)

  def test_disabled_strip_all_zeros(self):
    """A disabled strip should produce all zeros in its slot."""
    installation = synthesize_default_installation()
    installation.strips[0].enabled = False
    controller = load_controller_profile()
    plan = compile_output_plan(installation, controller)

    frame = np.full((STRIPS, LEDS_PER_STRIP, 3), 255, dtype=np.uint8)
    result = map_frame_compiled(frame, plan)

    # Strip 0 is disabled, its slot should be all zeros
    assert np.all(result[0, :172, :] == 0)
    # Strip 1 (same channel, slot 1) should still have data
    assert np.any(result[0, 172:, :] != 0)


class TestPhysicalVsElectricalSemantics:
  def test_physical_strip_length(self):
    controller = load_controller_profile()
    assert controller.physical_leds_per_strip == 172

  def test_electrical_output_length(self):
    controller = load_controller_profile()
    assert controller.electrical_leds_per_output == 344

  def test_physical_never_equals_electrical(self):
    controller = load_controller_profile()
    assert controller.physical_leds_per_strip != controller.electrical_leds_per_output
