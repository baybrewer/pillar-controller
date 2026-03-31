"""
Persistent state manager.

Handles saving/loading of scenes, presets, and system configuration.
Uses atomic writes for crash safety.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

CONFIG_DIR = Path("/opt/pillar/config")
STATE_FILE = CONFIG_DIR / "state.json"


class StateManager:
  def __init__(self, config_dir: Optional[Path] = None):
    self.config_dir = config_dir or CONFIG_DIR
    self.state_file = self.config_dir / "state.json"
    self._state: dict = {
      'current_scene': 'rainbow_rotate',
      'current_params': {},
      'brightness': 0.8,
      'target_fps': 60,
      'gamma': 2.2,
      'blackout': False,
      'scenes': {},
      'playlists': {},
      'last_updated': None,
    }
    self.config_dir.mkdir(parents=True, exist_ok=True)

  def load(self):
    """Load state from disk."""
    if self.state_file.exists():
      try:
        with open(self.state_file) as f:
          saved = json.load(f)
        self._state.update(saved)
        logger.info(f"State loaded from {self.state_file}")
      except Exception as e:
        logger.error(f"Failed to load state: {e}")

  def save(self):
    """Atomically save state to disk."""
    self._state['last_updated'] = datetime.now().isoformat()
    try:
      # Atomic write: write to temp file, then rename
      fd, tmp_path = tempfile.mkstemp(dir=self.config_dir, suffix='.tmp')
      with os.fdopen(fd, 'w') as f:
        json.dump(self._state, f, indent=2)
      os.replace(tmp_path, self.state_file)
    except Exception as e:
      logger.error(f"Failed to save state: {e}")

  @property
  def current_scene(self) -> str:
    return self._state.get('current_scene', 'rainbow_rotate')

  @current_scene.setter
  def current_scene(self, value: str):
    self._state['current_scene'] = value
    self.save()

  @property
  def current_params(self) -> dict:
    return self._state.get('current_params', {})

  @current_params.setter
  def current_params(self, value: dict):
    self._state['current_params'] = value
    self.save()

  @property
  def brightness(self) -> float:
    return self._state.get('brightness', 0.8)

  @brightness.setter
  def brightness(self, value: float):
    self._state['brightness'] = max(0.0, min(1.0, value))
    self.save()

  @property
  def target_fps(self) -> int:
    return self._state.get('target_fps', 60)

  @target_fps.setter
  def target_fps(self, value: int):
    self._state['target_fps'] = max(1, min(90, value))
    self.save()

  # -- Scene presets --

  def save_scene(self, name: str, effect: str, params: dict):
    if 'scenes' not in self._state:
      self._state['scenes'] = {}
    self._state['scenes'][name] = {
      'effect': effect,
      'params': params,
      'saved_at': datetime.now().isoformat(),
    }
    self.save()
    logger.info(f"Scene saved: {name}")

  def load_scene(self, name: str) -> Optional[dict]:
    return self._state.get('scenes', {}).get(name)

  def delete_scene(self, name: str) -> bool:
    if name in self._state.get('scenes', {}):
      del self._state['scenes'][name]
      self.save()
      return True
    return False

  def list_scenes(self) -> dict:
    return self._state.get('scenes', {})

  # -- Playlists --

  def save_playlist(self, name: str, items: list[dict]):
    if 'playlists' not in self._state:
      self._state['playlists'] = {}
    self._state['playlists'][name] = {
      'items': items,
      'saved_at': datetime.now().isoformat(),
    }
    self.save()

  def load_playlist(self, name: str) -> Optional[dict]:
    return self._state.get('playlists', {}).get(name)

  def list_playlists(self) -> dict:
    return self._state.get('playlists', {})

  def get_full_state(self) -> dict:
    return dict(self._state)
