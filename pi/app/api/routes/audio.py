"""Audio routes — devices, config, start/stop."""

from fastapi import APIRouter, Depends

from ..schemas import AudioConfigRequest


def create_router(deps, require_auth) -> APIRouter:
    router = APIRouter(prefix="/api/audio", tags=["audio"])

    @router.get("/devices")
    async def list_audio_devices():
        return {"devices": deps.audio_analyzer.list_devices()}

    @router.get("/config")
    async def get_audio_config():
        a = deps.audio_analyzer
        return {
            "gain": a.gain,
            "bass_sensitivity": a.bass_sensitivity,
            "mid_sensitivity": a.mid_sensitivity,
            "treble_sensitivity": a.treble_sensitivity,
        }

    @router.post("/config", dependencies=[Depends(require_auth)])
    async def configure_audio(req: AudioConfigRequest):
        a = deps.audio_analyzer
        if req.gain is not None:
            a.gain = req.gain
        if req.bass_sensitivity is not None:
            a.bass_sensitivity = req.bass_sensitivity
            deps.state_manager.audio_bass_sensitivity = req.bass_sensitivity
        if req.mid_sensitivity is not None:
            a.mid_sensitivity = req.mid_sensitivity
            deps.state_manager.audio_mid_sensitivity = req.mid_sensitivity
        if req.treble_sensitivity is not None:
            a.treble_sensitivity = req.treble_sensitivity
            deps.state_manager.audio_treble_sensitivity = req.treble_sensitivity
        if req.sensitivity is not None:
            a.bass_sensitivity = req.sensitivity
            a.mid_sensitivity = req.sensitivity
            a.treble_sensitivity = req.sensitivity
        if req.device_index is not None:
            a.set_device(req.device_index)
        return {"status": "ok"}

    @router.post("/start", dependencies=[Depends(require_auth)])
    async def start_audio():
        deps.audio_analyzer.start()
        return {"status": "started"}

    @router.post("/stop", dependencies=[Depends(require_auth)])
    async def stop_audio():
        deps.audio_analyzer.stop()
        return {"status": "stopped"}

    return router
