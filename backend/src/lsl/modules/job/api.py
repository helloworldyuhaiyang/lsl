from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request

from lsl.modules.job.schema import (
    ApiResponse,
    CreateJobRequest,
    JobListResponseData,
    RunDueJobsRequest,
    RunJobsResponseData,
)
from lsl.modules.job.types import JobData
from lsl.modules.job.service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def get_job_service(request: Request) -> JobService:
    service = getattr(request.app.state, "job_service", None)
    if service is None:
        raise HTTPException(status_code=500, detail="Job service is not initialized")
    return cast(JobService, service)


@router.post("", response_model=ApiResponse[JobData])
def create_job(
    payload: CreateJobRequest,
    job_service: JobService = Depends(get_job_service),
):
    try:
        job = job_service.create_job(
            job_type=payload.job_type,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            payload=payload.payload,
            priority=payload.priority,
            max_attempts=payload.max_attempts,
            next_run_at=payload.next_run_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=job)


@router.get("", response_model=ApiResponse[JobListResponseData])
def list_jobs(
    limit: int = 20,
    status: int | None = None,
    job_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    job_service: JobService = Depends(get_job_service),
):
    try:
        items = job_service.list_jobs(
            limit=limit,
            status=status,
            job_type=job_type,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=JobListResponseData(items=items))


@router.post("/run-due", response_model=ApiResponse[RunJobsResponseData])
def run_due_jobs(
    payload: RunDueJobsRequest,
    job_service: JobService = Depends(get_job_service),
):
    try:
        items = job_service.run_due_jobs(limit=payload.limit, worker_id=payload.worker_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=RunJobsResponseData(items=items))


@router.get("/{job_id}", response_model=ApiResponse[JobData])
def get_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
):
    try:
        job = job_service.get_job(job_id=job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=job)


@router.post("/{job_id}/run", response_model=ApiResponse[JobData])
def run_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
):
    try:
        job = job_service.run_job(job_id=job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(data=job)
