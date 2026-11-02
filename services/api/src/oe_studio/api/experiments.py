"""Registered synthetic experiments and sealed exports."""
import csv
import io
import json

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse, Response

from .. import responses as wire
from ..errors import Problem
from ..schemas import ExperimentRequest
from .dependencies import StudioDependency, project_actor
from .pagination import page
from .requests import ExperimentReviewLink, SyntheticTaskJob, SyntheticTaskRegistration

router = APIRouter()


@router.post("/api/v1/projects/{p}/experiment-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "experiment"})
def experiment(studio: StudioDependency, p: str, body: ExperimentRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "experiment", body.model_dump(), idempotency_key, actor)


@router.post("/api/v1/projects/{p}/synthetic-tasks", status_code=201, response_model=wire.SyntheticTaskResponse, response_model_exclude_unset=True)
def register_synthetic_task(studio: StudioDependency, p: str, body: SyntheticTaskRegistration, actor=Depends(project_actor)):
    from ..research_workflow import register
    return register(studio, p, body, actor)


@router.get("/api/v1/projects/{p}/synthetic-tasks", response_model=wire.Page[wire.SyntheticTaskResponse], response_model_exclude_unset=True)
def synthetic_tasks(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        return page([studio.body(i) for i in studio.items(s, p, "synthetic_task")], cursor, limit)


@router.post("/api/v1/projects/{p}/synthetic-task-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "synthetic-experiment"})
def synthetic_task_run(studio: StudioDependency, p: str, body: SyntheticTaskJob, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "synthetic-experiment", body.model_dump(), idempotency_key, actor)


@router.get("/api/v1/projects/{p}/experiments", response_model=wire.Page[wire.ExperimentResponse], response_model_exclude_unset=True)
def experiments(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        return page([studio.experiment_body(i) for i in studio.items(s, p, "experiment")], cursor, limit)


@router.post("/api/v1/projects/{p}/experiments/{run_id}/proposal", status_code=201, response_model=wire.RevisionResponse, response_model_exclude_unset=True)
def experiment_proposal(studio: StudioDependency, p: str, run_id: str, actor=Depends(project_actor)):
    return studio.stage_experiment(p, run_id, actor)


@router.post("/api/v1/projects/{p}/experiments/{run_id}/review-results", status_code=201, response_model=wire.ExperimentResponse, response_model_exclude_unset=True)
def experiment_review(studio: StudioDependency, p: str, run_id: str, body: ExperimentReviewLink, actor=Depends(project_actor)):
    return studio.link_experiment_review(p, run_id, body.review_id, actor)


@router.get("/api/v1/projects/{p}/experiments/export", response_model=wire.ExperimentExport, responses={200: {"content": {"text/csv": {"schema": {"type": "string"}}}}})
def export(studio: StudioDependency, p: str, format: str = "csv", actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        items = studio.items(s, p, "experiment")
        rows = [studio.experiment_record(i) for i in items]
        provenance = {i.id: {"project_context": i.data["project_context"],
                            "sealed_record": i.data["sealed_record"], "stored_at": i.created_at} for i in items}
    if format == "json":
        return JSONResponse(wire.ExperimentExport.model_validate({"schema_version": 2, "demo_only": True, "items": rows,
            "provenance": provenance}).model_dump(exclude_unset=True), headers={"Content-Disposition": 'attachment; filename="ontology-results.json"'})
    if format != "csv":
        raise Problem(422, "invalid_format", "Export format must be csv or json")
    fields = sorted({key for row in rows for key in row}) or ["id", "condition", "task_id", "status"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows({key: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value
                     for key, value in row.items()} for row in rows)
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="ontology-results.csv"'})
