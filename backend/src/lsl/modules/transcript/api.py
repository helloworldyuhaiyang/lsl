from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request

from lsl.modules.transcript.schema import (
    ApiResponse,
    TranscriptData,
    TranscriptListResponseData,
    TranscriptUtteranceListResponseData,
)
from lsl.modules.transcript.service import TranscriptService

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


def get_transcript_service(request: Request) -> TranscriptService:
    service = getattr(request.app.state, "transcript_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="Transcript service is not initialized")
    return cast(TranscriptService, service)


@router.get("", response_model=ApiResponse[TranscriptListResponseData])
def list_transcripts(
    limit: int = 20,
    status: int | None = None,
    source_type: str | None = None,
    source_entity_id: str | None = None,
    transcript_service: TranscriptService = Depends(get_transcript_service),
):
    try:
        items = transcript_service.list_transcripts(
            limit=limit,
            status=status,
            source_type=source_type,
            source_entity_id=source_entity_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=TranscriptListResponseData(items=items))


@router.get("/{transcript_id}", response_model=ApiResponse[TranscriptData])
def get_transcript(
    transcript_id: str,
    include_raw: bool = False,
    transcript_service: TranscriptService = Depends(get_transcript_service),
):
    try:
        transcript = transcript_service.get_transcript(transcript_id=transcript_id, include_raw=include_raw)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=transcript)


@router.get("/{transcript_id}/utterances", response_model=ApiResponse[TranscriptUtteranceListResponseData])
def get_transcript_utterances(
    transcript_id: str,
    transcript_service: TranscriptService = Depends(get_transcript_service),
):
    try:
        items = transcript_service.list_utterances(transcript_id=transcript_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=TranscriptUtteranceListResponseData(items=items))
