from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from lsl.modules.tts.schema import (
    ApiResponse,
    CreateTtsSynthesisData,
    CreateTtsSynthesisRequest,
    GenerateTtsItemRequest,
    TtsSettingsData,
    TtsSpeakerListData,
    TtsSynthesisData,
    UpdateTtsSettingsRequest,
)
from lsl.modules.tts.service import TtsService

router = APIRouter(prefix="/tts", tags=["tts"])


def get_tts_service(request: Request) -> TtsService:
    service = getattr(request.app.state, "tts_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="TTS service is not initialized")
    return cast(TtsService, service)


@router.get("/providers/{provider}/speakers", response_model=ApiResponse[TtsSpeakerListData])
def get_provider_speakers(
    provider: str,
    tts_service: TtsService = Depends(get_tts_service),
):
    try:
        items = tts_service.list_speakers(provider_name=provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=TtsSpeakerListData(items=items))


@router.get("/settings", response_model=ApiResponse[TtsSettingsData])
def get_tts_settings(
    session_id: str,
    tts_service: TtsService = Depends(get_tts_service),
):
    try:
        data = tts_service.get_settings(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=data)


@router.put("/settings", response_model=ApiResponse[TtsSettingsData])
def update_tts_settings(
    payload: UpdateTtsSettingsRequest,
    tts_service: TtsService = Depends(get_tts_service),
):
    try:
        data = tts_service.update_settings(payload=payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == "session not found" else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=data)


@router.post("/items/{item_id}/generate")
def generate_tts_item(
    item_id: str,
    payload: GenerateTtsItemRequest,
    tts_service: TtsService = Depends(get_tts_service),
):
    try:
        audio_bytes, content_type = tts_service.generate_item_audio(item_id=item_id, payload=payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail in {"session not found", "revision not found", "tts source item not found"} else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return StreamingResponse(iter([audio_bytes]), media_type=content_type)


@router.post("", response_model=ApiResponse[CreateTtsSynthesisData])
def create_tts_synthesis(
    payload: CreateTtsSynthesisRequest,
    tts_service: TtsService = Depends(get_tts_service),
):
    try:
        data = tts_service.create_synthesis(session_id=payload.session_id, force=payload.force)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail in {"session not found", "revision not found"} else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=data)


@router.get("", response_model=ApiResponse[TtsSynthesisData])
def get_tts_synthesis(
    session_id: str,
    tts_service: TtsService = Depends(get_tts_service),
):
    try:
        data = tts_service.get_synthesis(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=data)
