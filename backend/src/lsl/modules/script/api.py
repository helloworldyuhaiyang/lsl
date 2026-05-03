from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request

from lsl.modules.script.schema import (
    ApiResponse,
    GenerateScriptSessionData,
    GenerateScriptSessionRequest,
    ScriptGenerationData,
    ScriptGenerationPreviewData,
)
from lsl.modules.script.service import ScriptService

router = APIRouter(prefix="/scripts", tags=["scripts"])


def get_script_service(request: Request) -> ScriptService:
    service = getattr(request.app.state, "script_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="Script service is not initialized")
    return cast(ScriptService, service)


@router.post("/generate-session", response_model=ApiResponse[GenerateScriptSessionData])
def generate_script_session(
    payload: GenerateScriptSessionRequest,
    script_service: ScriptService = Depends(get_script_service),
):
    try:
        data = script_service.generate_session(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=data)


@router.get("/generations/{generation_id}/preview", response_model=ApiResponse[ScriptGenerationPreviewData])
def get_script_generation_preview(
    generation_id: str,
    script_service: ScriptService = Depends(get_script_service),
):
    try:
        data = script_service.get_generation_preview(generation_id=generation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=data)


@router.get("/generations/{generation_id}", response_model=ApiResponse[ScriptGenerationData])
def get_script_generation(
    generation_id: str,
    script_service: ScriptService = Depends(get_script_service),
):
    try:
        data = script_service.get_generation(generation_id=generation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=data)
