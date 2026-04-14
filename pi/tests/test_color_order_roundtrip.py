"""Tests for color order swizzle derivation — the source of truth for correctness."""

from app.mapping.runtime_plan import (
  derive_precontroller_swizzle,
  simulate_display,
)


class TestSwizzleRoundtripAllPermutations:
  """The spec-mandated test: every controller×strip combination
  must produce correct display colors for R, G, and B."""

  def test_all_36_combinations(self):
    orders = ["RGB", "RBG", "GRB", "GBR", "BRG", "BGR"]
    for controller_order in orders:
      for strip_order in orders:
        swizzle = derive_precontroller_swizzle(controller_order, strip_order)
        for intended in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
          displayed = simulate_display(
            intended, swizzle, controller_order, strip_order,
          )
          assert displayed == intended, (
            f"controller={controller_order}, strip={strip_order}, "
            f"swizzle={swizzle}, intended={intended}, displayed={displayed}"
          )


class TestSwizzleIdentity:
  """When controller and strip order match, swizzle should be identity."""

  def test_bgr_bgr_identity(self):
    swizzle = derive_precontroller_swizzle("BGR", "BGR")
    assert swizzle == (0, 1, 2)

  def test_rgb_rgb_identity(self):
    swizzle = derive_precontroller_swizzle("RGB", "RGB")
    assert swizzle == (0, 1, 2)

  def test_grb_grb_identity(self):
    swizzle = derive_precontroller_swizzle("GRB", "GRB")
    assert swizzle == (0, 1, 2)


class TestSwizzleSpecificCases:
  """Regression tests for specific controller/strip combinations."""

  def test_bgr_controller_rgb_strip(self):
    swizzle = derive_precontroller_swizzle("BGR", "RGB")
    # Verify it works
    for intended in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
      displayed = simulate_display(intended, swizzle, "BGR", "RGB")
      assert displayed == intended

  def test_bgr_controller_grb_strip(self):
    swizzle = derive_precontroller_swizzle("BGR", "GRB")
    for intended in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
      displayed = simulate_display(intended, swizzle, "BGR", "GRB")
      assert displayed == intended

  def test_mixed_colors(self):
    """Test with non-primary colors to verify full correctness."""
    swizzle = derive_precontroller_swizzle("BGR", "RGB")
    for intended in [(128, 64, 32), (0, 0, 0), (255, 255, 255), (100, 200, 50)]:
      displayed = simulate_display(intended, swizzle, "BGR", "RGB")
      assert displayed == intended
