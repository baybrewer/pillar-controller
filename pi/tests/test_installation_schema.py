"""Tests for installation.yaml schema, validation, migration, and atomic save."""

import yaml
from pathlib import Path

from app.config.installation import (
  InstallationConfig, StripConfig, synthesize_default_installation,
  load_installation, save_installation, SCHEMA_VERSION,
  VALID_COLOR_ORDERS, VALID_CHIPSETS, VALID_DIRECTIONS,
)
from app.hardware_constants import STRIPS, LEDS_PER_STRIP, CHANNELS, CONTROLLER_WIRE_ORDER


class TestStripConfigValidation:
  def test_valid_strip(self):
    strip = StripConfig(
      id=0, label="S0", enabled=True, logical_order=0,
      output_channel=0, output_slot=0, direction="bottom_to_top",
      installed_led_count=172, color_order="BGR", chipset="WS2812B",
    )
    assert strip.validate() == []

  def test_led_count_too_high(self):
    strip = StripConfig(
      id=0, label="S0", enabled=True, logical_order=0,
      output_channel=0, output_slot=0, direction="bottom_to_top",
      installed_led_count=200, color_order="BGR", chipset="WS2812B",
    )
    errors = strip.validate()
    assert len(errors) == 1
    assert "out of range" in errors[0]

  def test_led_count_zero_is_valid(self):
    strip = StripConfig(
      id=0, label="S0", enabled=True, logical_order=0,
      output_channel=0, output_slot=0, direction="bottom_to_top",
      installed_led_count=0, color_order="BGR", chipset="WS2812B",
    )
    assert strip.validate() == []

  def test_invalid_color_order(self):
    strip = StripConfig(
      id=0, label="S0", enabled=True, logical_order=0,
      output_channel=0, output_slot=0, direction="bottom_to_top",
      installed_led_count=172, color_order="XYZ", chipset="WS2812B",
    )
    errors = strip.validate()
    assert any("color_order" in e for e in errors)

  def test_invalid_chipset(self):
    strip = StripConfig(
      id=0, label="S0", enabled=True, logical_order=0,
      output_channel=0, output_slot=0, direction="bottom_to_top",
      installed_led_count=172, color_order="BGR", chipset="APA102",
    )
    errors = strip.validate()
    assert any("chipset" in e for e in errors)

  def test_invalid_direction(self):
    strip = StripConfig(
      id=0, label="S0", enabled=True, logical_order=0,
      output_channel=0, output_slot=0, direction="left_to_right",
      installed_led_count=172, color_order="BGR", chipset="WS2812B",
    )
    errors = strip.validate()
    assert any("direction" in e for e in errors)

  def test_channel_out_of_range(self):
    strip = StripConfig(
      id=0, label="S0", enabled=True, logical_order=0,
      output_channel=10, output_slot=0, direction="bottom_to_top",
      installed_led_count=172, color_order="BGR", chipset="WS2812B",
    )
    errors = strip.validate()
    assert any("output_channel" in e for e in errors)

  def test_slot_out_of_range(self):
    strip = StripConfig(
      id=0, label="S0", enabled=True, logical_order=0,
      output_channel=0, output_slot=2, direction="bottom_to_top",
      installed_led_count=172, color_order="BGR", chipset="WS2812B",
    )
    errors = strip.validate()
    assert any("output_slot" in e for e in errors)


class TestInstallationConfigValidation:
  def test_valid_default(self):
    config = synthesize_default_installation()
    assert config.validate() == []

  def test_duplicate_logical_order(self):
    config = synthesize_default_installation()
    config.strips[1].logical_order = 0  # duplicate
    errors = config.validate()
    assert any("logical_order" in e for e in errors)

  def test_duplicate_channel_slot(self):
    config = synthesize_default_installation()
    config.strips[1].output_channel = 0
    config.strips[1].output_slot = 0  # collides with strip 0
    errors = config.validate()
    assert any("output_channel, output_slot" in e for e in errors)

  def test_invalid_geometry_mode(self):
    config = synthesize_default_installation()
    config.geometry_mode = "spherical"
    errors = config.validate()
    assert any("geometry_mode" in e for e in errors)


class TestSynthesizeDefault:
  def test_produces_10_strips(self):
    config = synthesize_default_installation()
    assert len(config.strips) == STRIPS

  def test_channel_pairing(self):
    config = synthesize_default_installation()
    for i, strip in enumerate(config.strips):
      assert strip.output_channel == i // 2
      assert strip.output_slot == i % 2

  def test_directions(self):
    config = synthesize_default_installation()
    for strip in config.strips:
      expected = "bottom_to_top" if strip.id % 2 == 0 else "top_to_bottom"
      assert strip.direction == expected

  def test_all_bgr(self):
    config = synthesize_default_installation()
    for strip in config.strips:
      assert strip.color_order == "BGR"

  def test_all_172_leds(self):
    config = synthesize_default_installation()
    for strip in config.strips:
      assert strip.installed_led_count == LEDS_PER_STRIP

  def test_schema_version(self):
    config = synthesize_default_installation()
    assert config.schema_version == SCHEMA_VERSION

  def test_validates_clean(self):
    config = synthesize_default_installation()
    assert config.validate() == []


class TestLoadSaveInstallation:
  def test_save_and_reload(self, tmp_path):
    config = synthesize_default_installation()
    save_installation(config, tmp_path)
    loaded = load_installation(tmp_path)
    assert loaded.profile_name == config.profile_name
    assert len(loaded.strips) == len(config.strips)
    for orig, loaded_s in zip(config.strips, loaded.strips):
      assert orig.id == loaded_s.id
      assert orig.color_order == loaded_s.color_order
      assert orig.direction == loaded_s.direction
      assert orig.installed_led_count == loaded_s.installed_led_count

  def test_synthesize_on_missing(self, tmp_path):
    config = load_installation(tmp_path)
    assert len(config.strips) == STRIPS
    assert (tmp_path / "installation.yaml").exists()

  def test_atomic_write_creates_file(self, tmp_path):
    config = synthesize_default_installation()
    save_installation(config, tmp_path)
    path = tmp_path / "installation.yaml"
    assert path.exists()
    with open(path) as f:
      data = yaml.safe_load(f)
    assert data['schema_version'] == SCHEMA_VERSION
    assert len(data['strips']) == STRIPS

  def test_to_dict_roundtrip(self):
    config = synthesize_default_installation()
    d = config.to_dict()
    assert d['schema_version'] == SCHEMA_VERSION
    assert len(d['strips']) == STRIPS
    assert d['strips'][0]['color_order'] == 'BGR'


class TestAllColorOrdersValid:
  def test_six_permutations(self):
    assert len(VALID_COLOR_ORDERS) == 6
    for order in ["RGB", "RBG", "GRB", "GBR", "BRG", "BGR"]:
      assert order in VALID_COLOR_ORDERS
