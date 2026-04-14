"""
Preview API routes — dedicated simulator/preview transport.

Manages preview effect instances separate from live, with a binary
WebSocket for frame streaming and REST endpoints for lifecycle.
"""

import asyncio
import logging
import struct
import time
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ...effects.generative import EFFECTS
from ...effects.audio_reactive import AUDIO_EFFECTS

logger = logging.getLogger(__name__)

# Preview frame header: type(1) + frame_id(4) + width(2) + height(2) + encoding(1) = 10 bytes
FRAME_HEADER_FORMAT = '<BIHHB'
FRAME_HEADER_SIZE = struct.calcsize(FRAME_HEADER_FORMAT)
MSG_TYPE_FRAME = 0x01


class PreviewStartRequest(BaseModel):
  effect: str
  params: dict = {}
  fps: int = 30


class PreviewService:
  """Manages preview effect instances and frame streaming."""

  def __init__(self, renderer):
    self._renderer = renderer
    self._effect = None
    self._effect_name: Optional[str] = None
    self._running = False
    self._clients: set[WebSocket] = set()
    self._frame_id = 0
    self._fps = 30
    self._task: Optional[asyncio.Task] = None

  @property
  def active(self) -> bool:
    return self._running and self._effect is not None

  @property
  def effect_name(self) -> Optional[str]:
    return self._effect_name

  def start(self, effect_name: str, params: dict = None, fps: int = 30):
    """Start a preview effect (separate from live)."""
    all_effects = {**EFFECTS, **AUDIO_EFFECTS}
    if effect_name not in all_effects:
      raise ValueError(f"Unknown effect: {effect_name}")

    effect_cls = all_effects[effect_name]
    from ...mapping.cylinder import N
    internal_width = self._renderer.internal_width if hasattr(self._renderer, 'internal_width') else 10

    # Merge params
    yaml_params = {}
    if hasattr(self._renderer, 'effects_config') and self._renderer.effects_config:
      for section in ('effects', 'audio_effects'):
        section_data = self._renderer.effects_config.get(section, {})
        if effect_name in section_data:
          yaml_params = section_data[effect_name].get('params', {})
          break
    merged = {**yaml_params, **(params or {})}

    self._effect = effect_cls(width=10, height=N, params=merged)
    self._effect_name = effect_name
    self._fps = max(1, min(fps, 60))
    self._running = True
    self._frame_id = 0
    logger.info(f"Preview started: {effect_name} at {self._fps} FPS")

  def stop(self):
    """Stop the preview effect."""
    self._running = False
    self._effect = None
    self._effect_name = None
    logger.info("Preview stopped")

  def render_frame(self, state) -> Optional[bytes]:
    """Render one preview frame and return binary payload with header."""
    if not self._running or self._effect is None:
      return None

    t = time.monotonic()
    try:
      frame = self._effect.render(t, state)
    except Exception as e:
      logger.error(f"Preview render error: {e}")
      return None

    # Ensure (width, height, 3) shape
    if frame.ndim != 3 or frame.shape[2] != 3:
      return None

    width = frame.shape[0]
    height = frame.shape[1]

    self._frame_id += 1
    header = struct.pack(
      FRAME_HEADER_FORMAT,
      MSG_TYPE_FRAME,
      self._frame_id,
      width,
      height,
      0,  # encoding: 0 = RGB
    )
    return header + frame.tobytes()

  def add_client(self, ws: WebSocket):
    self._clients.add(ws)

  def remove_client(self, ws: WebSocket):
    self._clients.discard(ws)

  def get_status(self) -> dict:
    return {
      'active': self.active,
      'effect': self._effect_name,
      'fps': self._fps,
      'frame_id': self._frame_id,
      'clients': len(self._clients),
    }


def create_router(deps) -> APIRouter:
  router = APIRouter(prefix="/api/preview", tags=["preview"])

  def _get_preview_service() -> PreviewService:
    if not hasattr(deps, 'preview_service') or deps.preview_service is None:
      from fastapi import HTTPException
      raise HTTPException(503, "Preview service not available")
    return deps.preview_service

  @router.get("/status")
  async def preview_status():
    try:
      svc = _get_preview_service()
      return svc.get_status()
    except Exception:
      return {'active': False, 'effect': None, 'fps': 0, 'frame_id': 0, 'clients': 0}

  @router.post("/start")
  async def preview_start(req: PreviewStartRequest):
    svc = _get_preview_service()
    try:
      svc.start(req.effect, req.params, req.fps)
    except ValueError as e:
      from fastapi import HTTPException
      raise HTTPException(404, str(e))
    return svc.get_status()

  @router.post("/stop")
  async def preview_stop():
    svc = _get_preview_service()
    svc.stop()
    return {'status': 'stopped'}

  @router.websocket("/ws")
  async def preview_websocket(ws: WebSocket):
    svc = _get_preview_service()
    await ws.accept()
    svc.add_client(ws)
    try:
      while True:
        if svc.active:
          payload = svc.render_frame(deps.render_state)
          if payload:
            await ws.send_bytes(payload)
        await asyncio.sleep(1.0 / max(svc._fps, 1))
    except WebSocketDisconnect:
      pass
    except asyncio.CancelledError:
      pass
    finally:
      svc.remove_client(ws)

  return router
