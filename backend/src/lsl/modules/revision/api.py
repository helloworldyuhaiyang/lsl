from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request

from lsl.modules.revision.schema import (
    ApiResponse,
    CreateRevisionRequest,
    RevisionData,
    RevisionItemData,
    UpdateRevisionItemRequest,
)
from lsl.modules.revision.service import RevisionService

router = APIRouter(prefix="/revisions", tags=["revisions"])


def get_revision_service(request: Request) -> RevisionService:
    service = getattr(request.app.state, "revision_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="Revision service is not initialized")
    return cast(RevisionService, service)


@router.post("", response_model=ApiResponse[RevisionData])
def create_revision(
    payload: CreateRevisionRequest,
    revision_service: RevisionService = Depends(get_revision_service),
):
    try:
        revision = revision_service.create_revision(
            session_id=payload.session_id,
            user_prompt=payload.user_prompt,
            force=payload.force,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail in {"session not found", "task not found"} else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=revision)


@router.get("", response_model=ApiResponse[RevisionData])
def get_revision(
    session_id: str,
    revision_service: RevisionService = Depends(get_revision_service),
):
    try:
        revision = revision_service.get_revision(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=revision)


@router.patch("/items/{item_id}", response_model=ApiResponse[RevisionItemData])
def update_revision_item(
    item_id: str,
    payload: UpdateRevisionItemRequest,
    revision_service: RevisionService = Depends(get_revision_service),
):
    try:
        item = revision_service.update_revision_item(item_id=item_id, payload=payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == "revision item not found" else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=item)
