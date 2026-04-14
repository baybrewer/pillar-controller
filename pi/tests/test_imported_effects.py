"""Tests for imported effect metadata and helper infrastructure."""

from app.effects.imported_sim_meta import (
  IMPORTED_EFFECTS_META, BATCH_B1, BATCH_B2, BATCH_B3,
)
from app.effects.imported_sim_helpers import (
  hsv_to_rgb_fast, palette_lerp, simplex_noise_2d,
  FIRE_PALETTE, OCEAN_PALETTE, AURORA_PALETTE,
)


class TestImportedEffectInventory:
  def test_total_count_is_27(self):
    assert len(IMPORTED_EFFECTS_META) == 27

  def test_classic_count(self):
    classics = [m for m in IMPORTED_EFFECTS_META.values() if m.category == 'classic']
    assert len(classics) == 5

  def test_ambient_count(self):
    ambients = [m for m in IMPORTED_EFFECTS_META.values() if m.category == 'ambient']
    assert len(ambients) == 12

  def test_sound_count(self):
    sounds = [m for m in IMPORTED_EFFECTS_META.values() if m.category == 'sound']
    assert len(sounds) == 10

  def test_b1_is_non_audio(self):
    for meta in BATCH_B1.values():
      assert meta.audio_requires == (), f"{meta.name} should have no audio deps"

  def test_b2_has_audio_deps(self):
    for meta in BATCH_B2.values():
      assert len(meta.audio_requires) > 0, f"{meta.name} should have audio deps"

  def test_b3_has_band_deps(self):
    for meta in BATCH_B3.values():
      assert 'bands' in meta.audio_requires or 'beat_energy' in meta.audio_requires, (
        f"{meta.name} should require bands or beat_energy"
      )

  def test_all_have_display_names(self):
    for meta in IMPORTED_EFFECTS_META.values():
      assert meta.display_name
      assert len(meta.display_name) > 0

  def test_all_have_descriptions(self):
    for meta in IMPORTED_EFFECTS_META.values():
      assert meta.description
      assert len(meta.description) > 5

  def test_batch_counts(self):
    assert len(BATCH_B1) == 17  # 5 classic + 12 ambient
    assert len(BATCH_B2) == 6
    assert len(BATCH_B3) == 4
    assert len(BATCH_B1) + len(BATCH_B2) + len(BATCH_B3) == 27

  def test_unique_names(self):
    names = list(IMPORTED_EFFECTS_META.keys())
    assert len(names) == len(set(names))


class TestHelperFunctions:
  def test_hsv_to_rgb_red(self):
    r, g, b = hsv_to_rgb_fast(0.0, 1.0, 1.0)
    assert r == 255
    assert g == 0
    assert b == 0

  def test_hsv_to_rgb_green(self):
    r, g, b = hsv_to_rgb_fast(1/3, 1.0, 1.0)
    assert g == 255

  def test_hsv_to_rgb_white(self):
    r, g, b = hsv_to_rgb_fast(0.0, 0.0, 1.0)
    assert r == 255 and g == 255 and b == 255

  def test_palette_lerp_endpoints(self):
    colors = [(255, 0, 0), (0, 255, 0)]
    r, g, b = palette_lerp(colors, 0.0)
    assert r == 255 and g == 0

  def test_palette_lerp_midpoint(self):
    colors = [(0, 0, 0), (255, 255, 255)]
    r, g, b = palette_lerp(colors, 0.25)
    assert 120 <= r <= 135  # approximately half

  def test_noise_bounded(self):
    for x in range(10):
      for y in range(10):
        v = simplex_noise_2d(x * 0.1, y * 0.1)
        assert 0 <= v <= 1.0

  def test_palettes_have_entries(self):
    assert len(FIRE_PALETTE) >= 4
    assert len(OCEAN_PALETTE) >= 4
    assert len(AURORA_PALETTE) >= 4
