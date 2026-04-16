"""Tests for Animation Switcher runtime playlist updates and sanitization."""

import numpy as np
import pytest

from app.effects.switcher import AnimationSwitcher


class FakeEffect:
  """Minimal effect stub for switcher tests."""
  def __init__(self, width=10, height=172, params=None):
    self.width = width
    self.height = height
    self.params = params or {}

  def render(self, t, state):
    return np.zeros((self.width, self.height, 3), dtype=np.uint8)


REGISTRY = {
  'twinkle': FakeEffect,
  'fire': FakeEffect,
  'plasma': FakeEffect,
  'animation_switcher': FakeEffect,
  'diag_sweep': FakeEffect,
  'diag_strip_identify': FakeEffect,
}


def _make_switcher(playlist=None):
  return AnimationSwitcher(
    width=10,
    height=172,
    params={
      'interval': 15,
      'fade_duration': 2.0,
      '_effect_registry': REGISTRY,
      'playlist': playlist if playlist is not None else [],
    },
  )


class TestRuntimePlaylistUpdate:
  def test_update_playlist_changes_rotation(self):
    s = _make_switcher(playlist=['twinkle', 'fire'])
    s.update_params({'playlist': ['plasma']})
    assert s._playlist == ['plasma']

  def test_update_playlist_resets_index(self):
    s = _make_switcher(playlist=['twinkle', 'fire', 'plasma'])
    s._current_idx = 2
    s.update_params({'playlist': ['fire', 'plasma']})
    assert s._current_idx == 0

  def test_update_interval_no_playlist_reset(self):
    s = _make_switcher(playlist=['twinkle', 'fire'])
    s._current_idx = 1
    s.update_params({'interval': 30})
    assert s._current_idx == 1
    assert s._interval == 30

  def test_update_empty_playlist_clears(self):
    s = _make_switcher(playlist=['twinkle'])
    s.update_params({'playlist': []})
    assert s._playlist == []

  def test_update_same_playlist_does_not_reset_index(self):
    s = _make_switcher(playlist=['twinkle', 'fire', 'plasma'])
    s._current_idx = 2
    s.update_params({'playlist': ['twinkle', 'fire', 'plasma']})
    assert s._current_idx == 2


class TestEmptyPlaylist:
  def test_empty_playlist_renders_black(self):
    s = _make_switcher(playlist=[])
    frame = s.render(0.0, None)
    assert frame.shape == (10, 172, 3)
    assert frame.sum() == 0


class TestSanitization:
  def test_init_strips_unknown_effect_names(self):
    s = _make_switcher(playlist=['twinkle', 'nonexistent', 'fire'])
    assert s._playlist == ['twinkle', 'fire']

  def test_update_strips_unknown_effect_names(self):
    s = _make_switcher(playlist=['twinkle'])
    s.update_params({'playlist': ['fire', 'does_not_exist', 'plasma']})
    assert s._playlist == ['fire', 'plasma']

  def test_all_unknown_becomes_empty(self):
    s = _make_switcher(playlist=['twinkle'])
    s.update_params({'playlist': ['unknown_a', 'unknown_b']})
    assert s._playlist == []


class TestStatus:
  def test_get_switcher_status_shape(self):
    s = _make_switcher(playlist=['twinkle', 'fire'])
    status = s.get_switcher_status()
    assert status['active'] is True
    assert 'current' in status
    assert 'playlist' in status
    assert 'interval' in status
    assert 'time_remaining' in status
