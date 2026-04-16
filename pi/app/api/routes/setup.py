"""
Setup API routes — live channel configuration.

Each channel edit validates, recompiles the output plan, hot-applies
to the renderer, and persists to installation.yaml. No sessions.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import ChannelConfigRequest
from ...config.installation import (
  save_installation, VALID_COLOR_ORDERS, MAX_LEDS_PER_CHANNEL,
)
from ...mapping.runtime_plan import compile_channel_plan

logger = logging.getLogger(__name__)


def create_router(deps, require_auth, broadcast_state) -> APIRouter:
    router = APIRouter(prefix="/api/setup", tags=["setup"])

    @router.get("/channels")
    async def get_channels():
        return {"channels": deps.installation.channels_api_dict()}

    @router.post("/channels/{n}", dependencies=[Depends(require_auth)])
    async def update_channel(n: int, req: ChannelConfigRequest):
        if not 0 <= n <= 7:
            raise HTTPException(400, f"Channel must be 0-7, got {n}")

        ch = deps.installation.channels[n]

        if req.color_order is not None:
            if req.color_order not in VALID_COLOR_ORDERS:
                raise HTTPException(422, f"Invalid color_order: {req.color_order}. Must be one of: {', '.join(sorted(VALID_COLOR_ORDERS))}")
            ch.color_order = req.color_order

        if req.led_count is not None:
            if not 0 <= req.led_count <= MAX_LEDS_PER_CHANNEL:
                raise HTTPException(422, f"led_count must be 0-{MAX_LEDS_PER_CHANNEL}, got {req.led_count}")
            ch.led_count = req.led_count

        # Recompile and hot-apply
        plan = compile_channel_plan(deps.installation, deps.controller_profile)
        deps.renderer.apply_output_plan(plan)

        # Persist
        save_installation(deps.installation, deps.config_dir)

        logger.info(f"Channel {n} updated: {ch.color_order}, {ch.led_count} LEDs")
        return {"status": "ok", "channels": deps.installation.channels_api_dict()}

    return router
