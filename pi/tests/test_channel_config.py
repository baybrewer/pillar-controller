"""Tests for channel-oriented installation config."""

import pytest
import tempfile
from pathlib import Path

from app.config.installation import (
  ChannelConfig, ChannelInstallation, VALID_COLOR_ORDERS,
  synthesize_default_channels, load_installation, save_installation,
  migrate_strip_to_channel,
)


class TestChannelConfig:
  def test_default_channels(self):
    inst = synthesize_default_channels()
    assert len(inst.channels) == 8
    for i in range(5):
      assert inst.channels[i].led_count == 344
      assert inst.channels[i].color_order == 'BGR'
    for i in range(5, 8):
      assert inst.channels[i].led_count == 0

  def test_validate_valid(self):
    inst = synthesize_default_channels()
    errors = inst.validate()
    assert errors == []

  def test_validate_bad_color_order(self):
    inst = synthesize_default_channels()
    inst.channels[0].color_order = 'XYZ'
    errors = inst.validate()
    assert any('color_order' in e for e in errors)

  def test_validate_led_count_range(self):
    inst = synthesize_default_channels()
    inst.channels[0].led_count = 1200
    errors = inst.validate()
    assert any('led_count' in e for e in errors)

  def test_validate_led_count_zero_ok(self):
    inst = synthesize_default_channels()
    inst.channels[7].led_count = 0
    errors = inst.validate()
    assert errors == []


class TestMigration:
  def test_migrate_strip_format(self):
    old_data = {
      'schema_version': 1,
      'strips': [
        {'id': 0, 'output_channel': 0, 'output_slot': 0, 'installed_led_count': 172, 'color_order': 'BGR', 'enabled': True},
        {'id': 1, 'output_channel': 0, 'output_slot': 1, 'installed_led_count': 172, 'color_order': 'BGR', 'enabled': True},
        {'id': 2, 'output_channel': 1, 'output_slot': 0, 'installed_led_count': 172, 'color_order': 'GRB', 'enabled': True},
        {'id': 3, 'output_channel': 1, 'output_slot': 1, 'installed_led_count': 172, 'color_order': 'GRB', 'enabled': True},
      ],
    }
    inst = migrate_strip_to_channel(old_data)
    assert inst.schema_version == 2
    assert len(inst.channels) == 8
    assert inst.channels[0].led_count == 344
    assert inst.channels[0].color_order == 'BGR'
    assert inst.channels[1].led_count == 344
    assert inst.channels[1].color_order == 'GRB'
    for i in range(2, 8):
      assert inst.channels[i].led_count == 0


class TestPersistence:
  def test_save_and_load(self):
    with tempfile.TemporaryDirectory() as tmp:
      config_dir = Path(tmp)
      inst = synthesize_default_channels()
      inst.channels[2].color_order = 'RGB'
      inst.channels[2].led_count = 500
      save_installation(inst, config_dir)

      loaded = load_installation(config_dir)
      assert loaded.channels[2].color_order == 'RGB'
      assert loaded.channels[2].led_count == 500
      assert loaded.schema_version == 2
