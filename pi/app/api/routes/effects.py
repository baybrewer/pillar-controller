"""
Effect catalog routes — rich metadata for UI and preview.

Provides /api/effects/catalog (new rich endpoint) while keeping
/api/scenes/list compatible with the existing frontend.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter

from ...effects.generative import EFFECTS
from ...effects.audio_reactive import AUDIO_EFFECTS
from ...diagnostics.patterns import DIAGNOSTIC_EFFECTS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EffectMeta:
  name: str
  label: str
  group: str
  description: str
  preview_supported: bool = True
  imported: bool = False
  geometry_aware: bool = False
  audio_requires: tuple = ()
  default_params: dict = None

  def to_dict(self) -> dict:
    return {
      'name': self.name,
      'label': self.label,
      'group': self.group,
      'description': self.description,
      'preview_supported': self.preview_supported,
      'imported': self.imported,
      'geometry_aware': self.geometry_aware,
      'audio_requires': list(self.audio_requires),
    }


def _name_to_label(name: str) -> str:
  """Convert snake_case effect name to a readable label."""
  return name.replace('_', ' ').title()


def _get_description(name: str, effect_cls) -> str:
  """Get effect description from class docstring or generate one."""
  if effect_cls.__doc__:
    first_line = effect_cls.__doc__.strip().split('\n')[0].strip()
    if first_line:
      return first_line
  return f"{_name_to_label(name)} effect"


class EffectCatalogService:
  """Metadata-backed effect catalog."""

  def __init__(self):
    self._catalog: dict[str, EffectMeta] = {}
    self._build_catalog()

  def _build_catalog(self):
    for name, cls in EFFECTS.items():
      self._catalog[name] = EffectMeta(
        name=name,
        label=_name_to_label(name),
        group='generative',
        description=_get_description(name, cls),
      )
    for name, cls in AUDIO_EFFECTS.items():
      self._catalog[name] = EffectMeta(
        name=name,
        label=_name_to_label(name),
        group='audio',
        description=_get_description(name, cls),
        audio_requires=('level', 'bass', 'mid', 'high', 'beat'),
      )
    for name, cls in DIAGNOSTIC_EFFECTS.items():
      self._catalog[name] = EffectMeta(
        name=name,
        label=_name_to_label(name),
        group='diagnostic',
        description=_get_description(name, cls),
        preview_supported=False,
      )

  def register_imported(self, name: str, meta: EffectMeta):
    """Register an imported effect with explicit metadata."""
    self._catalog[name] = meta

  def get_catalog(self) -> dict[str, EffectMeta]:
    return dict(self._catalog)

  def get_meta(self, name: str) -> Optional[EffectMeta]:
    return self._catalog.get(name)


def create_router(deps) -> APIRouter:
  router = APIRouter(prefix="/api/effects", tags=["effects"])

  @router.get("/catalog")
  async def get_catalog():
    """Rich metadata for all registered effects."""
    if hasattr(deps, 'effect_catalog') and deps.effect_catalog:
      catalog = deps.effect_catalog.get_catalog()
      return {
        'effects': {name: meta.to_dict() for name, meta in catalog.items()},
        'current': deps.render_state.current_scene,
      }
    # Fallback: build from registries
    svc = EffectCatalogService()
    catalog = svc.get_catalog()
    return {
      'effects': {name: meta.to_dict() for name, meta in catalog.items()},
      'current': deps.render_state.current_scene,
    }

  @router.get("/{name}")
  async def get_effect_meta(name: str):
    """Metadata for a single effect."""
    if hasattr(deps, 'effect_catalog') and deps.effect_catalog:
      meta = deps.effect_catalog.get_meta(name)
      if meta:
        return meta.to_dict()
    # Fallback
    svc = EffectCatalogService()
    meta = svc.get_meta(name)
    if meta:
      return meta.to_dict()
    return {"error": "not found"}, 404

  return router
