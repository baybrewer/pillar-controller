"""
Installation config — channel-oriented LED configuration.

Manages installation.yaml: per-channel color order and LED count.
hardware.yaml stays the immutable controller envelope.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

from ..hardware_constants import (
  CHANNELS, LEDS_PER_CHANNEL, CONTROLLER_WIRE_ORDER,
  ACTIVE_OUTPUTS, TOTAL_OUTPUTS,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2
MAX_LEDS_PER_CHANNEL = 1100

VALID_COLOR_ORDERS = frozenset(["RGB", "RBG", "GRB", "GBR", "BRG", "BGR"])


@dataclass
class ChannelConfig:
  channel: int
  color_order: str = "BGR"
  led_count: int = 0

  def validate(self) -> list[str]:
    errors = []
    if not 0 <= self.channel < 8:
      errors.append(f"Channel {self.channel}: channel number out of range [0, 7]")
    if self.color_order not in VALID_COLOR_ORDERS:
      errors.append(f"Channel {self.channel}: invalid color_order '{self.color_order}'")
    if not 0 <= self.led_count <= MAX_LEDS_PER_CHANNEL:
      errors.append(f"Channel {self.channel}: led_count {self.led_count} out of range [0, {MAX_LEDS_PER_CHANNEL}]")
    return errors


@dataclass
class ChannelInstallation:
  schema_version: int = SCHEMA_VERSION
  channels: list[ChannelConfig] = field(default_factory=list)

  def validate(self) -> list[str]:
    errors = []
    for ch in self.channels:
      errors.extend(ch.validate())
    return errors

  def to_dict(self) -> dict:
    return {
      'schema_version': self.schema_version,
      'channels': [asdict(ch) for ch in self.channels],
    }

  def channels_api_dict(self) -> list[dict]:
    return [asdict(ch) for ch in self.channels]


def synthesize_default_channels() -> ChannelInstallation:
  channels = []
  for i in range(8):
    led_count = LEDS_PER_CHANNEL if i < ACTIVE_OUTPUTS else 0
    channels.append(ChannelConfig(
      channel=i,
      color_order=CONTROLLER_WIRE_ORDER,
      led_count=led_count,
    ))
  return ChannelInstallation(channels=channels)


def migrate_strip_to_channel(data: dict) -> ChannelInstallation:
  channels = {i: ChannelConfig(channel=i) for i in range(8)}

  for s in data.get('strips', []):
    ch_num = s.get('output_channel', 0)
    if 0 <= ch_num < 8:
      ch = channels[ch_num]
      if s.get('enabled', True):
        ch.led_count += s.get('installed_led_count', 0)
        if ch.color_order == 'BGR' or ch.led_count == s.get('installed_led_count', 0):
          ch.color_order = s.get('color_order', CONTROLLER_WIRE_ORDER)

  return ChannelInstallation(
    schema_version=SCHEMA_VERSION,
    channels=[channels[i] for i in range(8)],
  )


def load_installation(config_dir: Path) -> ChannelInstallation:
  path = config_dir / "installation.yaml"
  if path.exists():
    with open(path) as f:
      data = yaml.safe_load(f) or {}

    if data.get('schema_version', 0) >= 2:
      return _parse_channels(data)

    if 'strips' in data:
      logger.info("Migrating strip-oriented installation.yaml to channel format")
      inst = migrate_strip_to_channel(data)
      save_installation(inst, config_dir)
      return inst

  inst = synthesize_default_channels()
  save_installation(inst, config_dir)
  logger.info("Synthesized default channel installation.yaml")
  return inst


def _parse_channels(data: dict) -> ChannelInstallation:
  channels = []
  for ch in data.get('channels', []):
    channels.append(ChannelConfig(
      channel=ch.get('channel', len(channels)),
      color_order=ch.get('color_order', CONTROLLER_WIRE_ORDER),
      led_count=ch.get('led_count', 0),
    ))
  while len(channels) < 8:
    channels.append(ChannelConfig(channel=len(channels)))
  return ChannelInstallation(
    schema_version=data.get('schema_version', SCHEMA_VERSION),
    channels=channels,
  )


def save_installation(config: ChannelInstallation, config_dir: Path):
  path = config_dir / "installation.yaml"
  config_dir.mkdir(parents=True, exist_ok=True)
  data = config.to_dict()
  fd, tmp_path = tempfile.mkstemp(dir=str(config_dir), suffix='.tmp')
  try:
    with os.fdopen(fd, 'w') as f:
      yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    os.replace(tmp_path, str(path))
    logger.info("Saved installation.yaml")
  except Exception:
    try:
      os.unlink(tmp_path)
    except OSError:
      pass
    raise
