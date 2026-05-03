from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request

from lsl.modules.asr.schema import (
    ApiResponse,
    AsrRecognitionData,
    AsrRecognitionListResponseData,
    CreateAsrRecognitionData,
    CreateAsrRecognitionRequest,
)
from lsl.modules.asr.service import AsrService

router = APIRouter(prefix="/asr", tags=["asr"])


def get_asr_service(request: Request) -> AsrService:
    service = getattr(request.app.state, "asr_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="ASR service is not initialized")
    return cast(AsrService, service)


@router.post("/recognitions", response_model=ApiResponse[CreateAsrRecognitionData])
def create_recognition(
    payload: CreateAsrRecognitionRequest,
    asr_service: AsrService = Depends(get_asr_service),
):
    try:
        data = asr_service.create_recognition(
            object_key=payload.object_key,
            audio_url=payload.audio_url,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=data)


@router.get("/recognitions", response_model=ApiResponse[AsrRecognitionListResponseData])
def list_recognitions(
    limit: int = 20,
    status: int | None = None,
    asr_service: AsrService = Depends(get_asr_service),
):
    try:
        items = asr_service.list_recognitions(limit=limit, status=status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=AsrRecognitionListResponseData(items=items))


@router.get("/recognitions/{recognition_id}", response_model=ApiResponse[AsrRecognitionData])
def get_recognition(
    recognition_id: str,
    asr_service: AsrService = Depends(get_asr_service),
):
    try:
        data = asr_service.get_recognition(recognition_id=recognition_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=data)
