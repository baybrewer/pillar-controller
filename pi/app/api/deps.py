"""Shared dependency container for route modules."""

from dataclasses import dataclass, field
from typing import Optional

from ..core.renderer import Renderer, RenderState
from ..core.state import StateManager
from ..core.brightness import BrightnessEngine
from ..transport.usb import TeensyTransport
from ..media.manager import MediaManager
from ..audio.analyzer import AudioAnalyzer


@dataclass
class AppDeps:
    transport: TeensyTransport
    renderer: Renderer
    render_state: RenderState
    state_manager: StateManager
    brightness_engine: BrightnessEngine
    media_manager: MediaManager
    audio_analyzer: AudioAnalyzer
    max_upload_bytes: int = 50 * 1024 * 1024
    # Phase 1+: setup and config services (optional for backwards compat)
    setup_session_service: Optional[object] = None
    spatial_map: Optional[object] = None
    preview_service: Optional[object] = None
    effect_catalog: Optional[object] = None
