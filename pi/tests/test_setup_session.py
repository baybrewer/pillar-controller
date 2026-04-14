"""Tests for setup session service — snapshot/restore, staged edits, commit."""

from unittest.mock import MagicMock, patch
from pathlib import Path

from app.setup.session import SetupSessionService, SetupSnapshot
from app.config.installation import synthesize_default_installation, InstallationConfig
from app.mapping.runtime_plan import load_controller_profile


def _make_service(tmp_path: Path) -> SetupSessionService:
  """Create a SetupSessionService with mocked renderer and state."""
  installation = synthesize_default_installation()
  controller = load_controller_profile()

  renderer = MagicMock()
  renderer.activate_scene = MagicMock(return_value=True)

  render_state = MagicMock()
  render_state.current_scene = "rainbow_rotate"
  render_state.blackout = False

  state_manager = MagicMock()
  state_manager.current_params = {"speed": 1.0}

  return SetupSessionService(
    installation=installation,
    controller=controller,
    config_dir=tmp_path,
    renderer=renderer,
    render_state=render_state,
    state_manager=state_manager,
  )


class TestSessionLifecycle:
  def test_start_session(self, tmp_path):
    svc = _make_service(tmp_path)
    session = svc.start_session()
    assert session.session_id
    assert session.snapshot.current_scene == "rainbow_rotate"
    assert session.snapshot.blackout is False
    assert len(session.staged_installation.strips) == 10

  def test_cannot_start_twice(self, tmp_path):
    svc = _make_service(tmp_path)
    svc.start_session()
    try:
      svc.start_session()
      assert False, "Should have raised"
    except ValueError:
      pass

  def test_get_session(self, tmp_path):
    svc = _make_service(tmp_path)
    assert svc.get_session() is None
    svc.start_session()
    assert svc.get_session() is not None

  def test_cancel_restores_scene(self, tmp_path):
    svc = _make_service(tmp_path)
    session = svc.start_session()
    svc.render_state.blackout = True  # simulate setup changes
    snapshot = svc.cancel()
    assert snapshot.current_scene == "rainbow_rotate"
    assert svc.render_state.blackout is False
    svc.renderer.activate_scene.assert_called_with("rainbow_rotate", {"speed": 1.0})
    assert svc.get_session() is None

  def test_cancel_without_session_raises(self, tmp_path):
    svc = _make_service(tmp_path)
    try:
      svc.cancel()
      assert False, "Should have raised"
    except ValueError:
      pass

  def test_commit_saves_and_restores(self, tmp_path):
    svc = _make_service(tmp_path)
    svc.start_session()
    result = svc.commit()
    assert result['status'] == 'committed'
    assert result['strips'] == 10
    assert svc.get_session() is None
    # Verify file was saved
    assert (tmp_path / "installation.yaml").exists()

  def test_commit_validates(self, tmp_path):
    svc = _make_service(tmp_path)
    session = svc.start_session()
    # Make invalid: duplicate logical orders
    session.staged_installation.strips[0].logical_order = 1
    session.staged_installation.strips[1].logical_order = 1
    try:
      svc.commit()
      assert False, "Should have raised"
    except ValueError as e:
      assert "logical_order" in str(e)


class TestStagedEdits:
  def test_update_strip_color_order(self, tmp_path):
    svc = _make_service(tmp_path)
    svc.start_session()
    staged = svc.update_staged_installation([
      {'id': 3, 'color_order': 'RGB'},
    ])
    assert staged.strips[3].color_order == 'RGB'
    # Other strips unchanged
    assert staged.strips[0].color_order == 'BGR'

  def test_update_strip_led_count(self, tmp_path):
    svc = _make_service(tmp_path)
    svc.start_session()
    staged = svc.update_staged_installation([
      {'id': 5, 'installed_led_count': 100},
    ])
    assert staged.strips[5].installed_led_count == 100

  def test_update_multiple_strips(self, tmp_path):
    svc = _make_service(tmp_path)
    svc.start_session()
    staged = svc.update_staged_installation([
      {'id': 0, 'enabled': False},
      {'id': 9, 'enabled': False},
    ])
    assert staged.strips[0].enabled is False
    assert staged.strips[9].enabled is False
    assert staged.strips[1].enabled is True

  def test_update_nonexistent_strip_ignored(self, tmp_path):
    svc = _make_service(tmp_path)
    svc.start_session()
    staged = svc.update_staged_installation([
      {'id': 99, 'color_order': 'RGB'},
    ])
    # No crash, no change
    assert all(s.color_order == 'BGR' for s in staged.strips)

  def test_staged_edits_dont_affect_live(self, tmp_path):
    svc = _make_service(tmp_path)
    svc.start_session()
    svc.update_staged_installation([{'id': 0, 'color_order': 'RGB'}])
    # Live installation should not be affected
    assert svc.installation.strips[0].color_order == 'BGR'


class TestSetupPatterns:
  def test_run_and_clear_pattern(self, tmp_path):
    svc = _make_service(tmp_path)
    session = svc.start_session()
    svc.run_pattern({'mode': 'fill_strip', 'targets': [{'strip_id': 0}]})
    assert session.active_pattern is not None
    svc.clear_pattern()
    assert session.active_pattern is None


class TestSnapshotRestore:
  def test_snapshot_captures_blackout(self, tmp_path):
    svc = _make_service(tmp_path)
    svc.render_state.blackout = True
    session = svc.start_session()
    assert session.snapshot.blackout is True

  def test_cancel_restores_blackout(self, tmp_path):
    svc = _make_service(tmp_path)
    svc.render_state.blackout = True
    svc.start_session()
    svc.render_state.blackout = False  # changed during setup
    svc.cancel()
    assert svc.render_state.blackout is True
