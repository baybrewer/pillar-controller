"""
Installation config — mutable strip configuration SSOT.

Manages installation.yaml: the per-strip setup truth that is writable
from the setup UI. hardware.yaml stays the immutable controller envelope.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import yaml

from ..hardware_constants import (
  STRIPS, LEDS_PER_STRIP, CHANNELS, CONTROLLER_WIRE_ORDER,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

VALID_COLOR_ORDERS = frozenset(["RGB", "RBG", "GRB", "GBR", "BRG", "BGR"])
VALID_CHIPSETS = frozenset(["WS2812B", "WS2812", "WS2811", "SK6812", "WS2813", "WS2815"])
VALID_DIRECTIONS = frozenset(["bottom_to_top", "top_to_bottom"])
VALID_GEOMETRY_MODES = frozenset(["canonical_grid", "front_projection"])


@dataclass
class StripConfig:
  id: int
  label: str
  enabled: bool
  logical_order: int
  output_channel: int
  output_slot: int
  direction: str
  installed_led_count: int
  color_order: str
  chipset: str

  def validate(self, max_physical: int = LEDS_PER_STRIP, max_channels: int = CHANNELS):
    errors = []
    if not 0 <= self.installed_led_count <= max_physical:
      errors.append(f"Strip {self.id}: installed_led_count {self.installed_led_count} out of range [0, {max_physical}]")
    if self.color_order not in VALID_COLOR_ORDERS:
      errors.append(f"Strip {self.id}: invalid color_order '{self.color_order}'")
    if self.chipset not in VALID_CHIPSETS:
      errors.append(f"Strip {self.id}: invalid chipset '{self.chipset}'")
    if self.direction not in VALID_DIRECTIONS:
      errors.append(f"Strip {self.id}: invalid direction '{self.direction}'")
    if not 0 <= self.output_channel < max_channels:
      errors.append(f"Strip {self.id}: output_channel {self.output_channel} out of range [0, {max_channels})")
    if self.output_slot not in (0, 1):
      errors.append(f"Strip {self.id}: output_slot must be 0 or 1, got {self.output_slot}")
    return errors


@dataclass
class InstallationConfig:
  schema_version: int = SCHEMA_VERSION
  profile_name: str = "default"
  geometry_mode: str = "canonical_grid"
  spatial_profile_id: str = "default"
  strips: list[StripConfig] = field(default_factory=list)

  def validate(self) -> list[str]:
    errors = []
    if self.geometry_mode not in VALID_GEOMETRY_MODES:
      errors.append(f"Invalid geometry_mode: '{self.geometry_mode}'")
    # Check logical_order uniqueness among enabled strips
    enabled_orders = [s.logical_order for s in self.strips if s.enabled]
    if len(enabled_orders) != len(set(enabled_orders)):
      errors.append("Duplicate logical_order among enabled strips")
    # Check channel/slot collisions
    slots = [(s.output_channel, s.output_slot) for s in self.strips if s.enabled]
    if len(slots) != len(set(slots)):
      errors.append("Duplicate (output_channel, output_slot) among enabled strips")
    for strip in self.strips:
      errors.extend(strip.validate())
    return errors

  def to_dict(self) -> dict:
    return {
      'schema_version': self.schema_version,
      'profile_name': self.profile_name,
      'geometry_mode': self.geometry_mode,
      'spatial_profile_id': self.spatial_profile_id,
      'strips': [asdict(s) for s in self.strips],
    }


def synthesize_default_installation() -> InstallationConfig:
  """Create a default installation matching the current legacy hardware layout.

  This produces the exact same output as the hardcoded cylinder.py mapper:
  10 strips, paired per channel, even=bottom_to_top, odd=top_to_bottom, all BGR.
  """
  strips = []
  for i in range(STRIPS):
    strips.append(StripConfig(
      id=i,
      label=f"S{i}",
      enabled=True,
      logical_order=i,
      output_channel=i // 2,
      output_slot=i % 2,
      direction="bottom_to_top" if i % 2 == 0 else "top_to_bottom",
      installed_led_count=LEDS_PER_STRIP,
      color_order=CONTROLLER_WIRE_ORDER,
      chipset="WS2812B",
    ))
  return InstallationConfig(strips=strips)


def load_installation(config_dir: Path) -> InstallationConfig:
  """Load installation.yaml, synthesizing defaults if it doesn't exist."""
  path = config_dir / "installation.yaml"
  if path.exists():
    with open(path) as f:
      data = yaml.safe_load(f) or {}
    return _parse_installation(data)
  # First boot: synthesize and save
  config = synthesize_default_installation()
  save_installation(config, config_dir)
  logger.info("Synthesized default installation.yaml from hardware layout")
  return config


def _parse_installation(data: dict) -> InstallationConfig:
  """Parse installation.yaml data into InstallationConfig."""
  strips = []
  for s in data.get('strips', []):
    strips.append(StripConfig(
      id=s['id'],
      label=s.get('label', f"S{s['id']}"),
      enabled=s.get('enabled', True),
      logical_order=s.get('logical_order', s['id']),
      output_channel=s.get('output_channel', s['id'] // 2),
      output_slot=s.get('output_slot', s['id'] % 2),
      direction=s.get('direction', 'bottom_to_top'),
      installed_led_count=s.get('installed_led_count', LEDS_PER_STRIP),
      color_order=s.get('color_order', CONTROLLER_WIRE_ORDER),
      chipset=s.get('chipset', 'WS2812B'),
    ))
  return InstallationConfig(
    schema_version=data.get('schema_version', SCHEMA_VERSION),
    profile_name=data.get('profile_name', 'default'),
    geometry_mode=data.get('geometry_mode', 'canonical_grid'),
    spatial_profile_id=data.get('spatial_profile_id', 'default'),
    strips=strips,
  )


def save_installation(config: InstallationConfig, config_dir: Path):
  """Atomically save installation.yaml."""
  path = config_dir / "installation.yaml"
  config_dir.mkdir(parents=True, exist_ok=True)
  data = config.to_dict()
  fd, tmp_path = tempfile.mkstemp(dir=str(config_dir), suffix='.tmp')
  try:
    with os.fdopen(fd, 'w') as f:
      yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    os.replace(tmp_path, str(path))
    logger.info(f"Saved installation.yaml (profile: {config.profile_name})")
  except Exception:
    try:
      os.unlink(tmp_path)
    except OSError:
      pass
    raise
