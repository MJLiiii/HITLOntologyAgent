"""Authorized durable-job status."""
from fastapi import APIRouter, Depends

from .. import responses as wire
from ..db import Job
from ..errors import Problem
from .dependencies import StudioDependency, project_actor

router = APIRouter()


@router.get("/api/v1/jobs/{job_id}", response_model=wire.JobResponse, response_model_exclude_unset=True)
def job(studio: StudioDependency, job_id: str, actor=Depends(project_actor)):
    with studio.db.session() as s:
        value = s.get(Job, job_id)
        if not value:
            raise Problem(404, "not_found", "Job not found")
        studio.authorize(value.project_id, actor, 'viewer')
        studio.project(s, value.project_id)
        profile = value.payload.get("_resolved_llm_profile")
        metadata = ({key: profile[key] for key in ("id", "revision", "provider", "model", "timeout", "max_output_tokens", "temperature", "structured_output")}
                    if profile else None)
        return {"id": value.id, "model_configuration": metadata, "status": value.status, "result": value.result, "error": value.error, "stage": value.kind,
                "progress": 1 if value.status in {"succeeded", "failed"} else 0, "created_at": value.created_at}
