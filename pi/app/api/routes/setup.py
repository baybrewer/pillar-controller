"""
Setup API routes — strip listing and test patterns.

Read-only strip listing from the compiled pixel map.
Full pixel map CRUD will be in the pixel_map routes (Task 10).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def create_router(deps, require_auth, broadcast_state) -> APIRouter:
    router = APIRouter(prefix="/api/setup", tags=["setup"])

    @router.get("/strips")
    async def get_strips():
        """List strips from the compiled pixel map."""
        pm = deps.compiled_pixel_map
        if pm is None:
            return {"strips": []}
        strips = []
        for s in pm.strips:
            strips.append({
                "id": s.id,
                "output": s.output,
                "output_offset": s.output_offset,
                "total_leds": s.total_leds,
            })
        return {"strips": strips}

    @router.get("/installation")
    async def get_installation():
        """Legacy endpoint — returns strip info from pixel map."""
        pm = deps.compiled_pixel_map
        if pm is None:
            return {"strips": []}
        strips = []
        for s in pm.strips:
            strips.append({
                "id": s.id,
                "output": s.output,
                "output_offset": s.output_offset,
                "total_leds": s.total_leds,
            })
        return {"strips": strips}

    @router.post("/strips/{strip_id}/test", dependencies=[Depends(require_auth)])
    async def test_strip(strip_id: int):
        pm = deps.compiled_pixel_map
        if pm is None:
            raise HTTPException(404, "No pixel map loaded")
        strip = next((s for s in pm.strips if s.id == strip_id), None)
        if strip is None:
            raise HTTPException(404, f"Strip {strip_id} not found")
        deps.renderer.set_test_strip(strip_id)
        return {"status": "ok", "strip_id": strip_id, "duration": 5}

    return router
