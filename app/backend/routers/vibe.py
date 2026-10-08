"""API routes for the VibeCoding H5 app generator."""

import logging

from fastapi import APIRouter, HTTPException
from schemas.vibe import GenerateAppRequest, GenerateAppResponse
from services.vibe import generate_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/vibe", tags=["vibe"])


@router.post("/generate", response_model=GenerateAppResponse)
async def generate_vibe_app(payload: GenerateAppRequest) -> GenerateAppResponse:
    """Create a new H5 app or apply a refinement instruction to the current one."""
    return await generate_app(payload)
