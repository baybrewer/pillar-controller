"""
Spatial map — optional front-projection geometry calibration.

Loads and saves spatial_map.json, the solved front-projection UV
coordinates from the geometry wizard.
"""

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


@dataclass
class StripGeometry:
  id: int
  anchors: list[list[float]]
  positions: list[list[float]]
  fit_method: str = "anchor_polyline_v1"
  visibility: str = "direct"


@dataclass
class SpatialMap:
  schema_version: int = SCHEMA_VERSION
  profile_id: str = "default"
  coordinate_space: str = "front_projection_uv"
  camera_resolution: list[int] = field(default_factory=lambda: [1280, 720])
  visible_strips: list[int] = field(default_factory=list)
  strips: list[StripGeometry] = field(default_factory=list)
  bounds: dict = field(default_factory=lambda: {
    "x_min": 0.0, "x_max": 1.0, "y_min": 0.0, "y_max": 1.0,
  })

  def to_dict(self) -> dict:
    return {
      'schema_version': self.schema_version,
      'profile_id': self.profile_id,
      'coordinate_space': self.coordinate_space,
      'camera_resolution': self.camera_resolution,
      'visible_strips': self.visible_strips,
      'strips': [
        {
          'id': s.id,
          'anchors': s.anchors,
          'positions': s.positions,
          'fit_method': s.fit_method,
          'visibility': s.visibility,
        }
        for s in self.strips
      ],
      'bounds': self.bounds,
    }


def load_spatial_map(config_dir: Path) -> Optional[SpatialMap]:
  """Load spatial_map.json if it exists. Returns None if absent."""
  path = config_dir / "spatial_map.json"
  if not path.exists():
    return None
  with open(path) as f:
    data = json.load(f)
  return _parse_spatial_map(data)


def _parse_spatial_map(data: dict) -> SpatialMap:
  strips = []
  for s in data.get('strips', []):
    strips.append(StripGeometry(
      id=s['id'],
      anchors=s.get('anchors', []),
      positions=s.get('positions', []),
      fit_method=s.get('fit_method', 'anchor_polyline_v1'),
      visibility=s.get('visibility', 'direct'),
    ))
  return SpatialMap(
    schema_version=data.get('schema_version', SCHEMA_VERSION),
    profile_id=data.get('profile_id', 'default'),
    coordinate_space=data.get('coordinate_space', 'front_projection_uv'),
    camera_resolution=data.get('camera_resolution', [1280, 720]),
    visible_strips=data.get('visible_strips', []),
    strips=strips,
    bounds=data.get('bounds', {"x_min": 0.0, "x_max": 1.0, "y_min": 0.0, "y_max": 1.0}),
  )


def save_spatial_map(spatial_map: SpatialMap, config_dir: Path):
  """Atomically save spatial_map.json."""
  path = config_dir / "spatial_map.json"
  config_dir.mkdir(parents=True, exist_ok=True)
  data = spatial_map.to_dict()
  fd, tmp_path = tempfile.mkstemp(dir=str(config_dir), suffix='.tmp')
  try:
    with os.fdopen(fd, 'w') as f:
      json.dump(data, f, indent=2)
    os.replace(tmp_path, str(path))
    logger.info(f"Saved spatial_map.json (profile: {spatial_map.profile_id})")
  except Exception:
    try:
      os.unlink(tmp_path)
    except OSError:
      pass
    raise
