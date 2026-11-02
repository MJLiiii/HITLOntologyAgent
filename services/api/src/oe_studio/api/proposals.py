"""Candidate revisions, checks, human review and publication."""
from fastapi import APIRouter, Depends, Header

from .. import responses as wire
from ..schemas import (
    BundleRequest,
    OracleDecision,
    ProposalRequest,
    PublishRequest,
    QuestionRequest,
    RepairRequest,
    ReviewRequest,
    ReviewSessionEvent,
    RevisionRequest,
    SeedImportRequest,
    Submission,
    TestGenerationRequest,
)
from .dependencies import StudioDependency, project_actor
from .pagination import page

router = APIRouter()


@router.post("/api/v1/projects/{p}/seed-imports", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "seed-import"})
def seed_import(studio: StudioDependency, p: str, body: SeedImportRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "seed-import", body.model_dump(), idempotency_key, actor)


@router.get("/api/v1/projects/{p}/versions", response_model=wire.Page[wire.VersionResponse], response_model_exclude_unset=True)
def versions(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        return page([studio.version_body(s, i) for i in studio.items(s, p, "version")], cursor, limit)


@router.get("/api/v1/projects/{p}/versions/{version}", response_model=wire.VersionResponse, response_model_exclude_unset=True)
def version(studio: StudioDependency, p: str, version: str, actor=Depends(project_actor)):
    with studio.db.session() as s:
        return studio.version_body(s, studio.get(s, p, version, "version"))


@router.get("/api/v1/projects/{p}/proposals", response_model=wire.Page[wire.RevisionResponse], response_model_exclude_unset=True)
def proposals(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        project = studio.project(s, p)
        return page([studio.revision_body(s, project, studio.revisions(s, p, proposal.id)[-1]) for proposal in studio.items(s, p, "proposal")], cursor, limit)


@router.get("/api/v1/projects/{p}/proposals/{proposal}/revisions/{revision}", response_model=wire.RevisionResponse, response_model_exclude_unset=True)
def revision(studio: StudioDependency, p: str, proposal: str, revision: int, actor=Depends(project_actor)):
    with studio.db.session() as s:
        return studio.revision_body(s, studio.project(s, p), studio.revision(s, p, proposal, revision))


@router.post("/api/v1/projects/{p}/proposals/{proposal}/revisions", status_code=201, response_model=wire.RevisionResponse, response_model_exclude_unset=True)
def revise(studio: StudioDependency, p: str, proposal: str, body: RevisionRequest, if_match: str = Header(...), actor=Depends(project_actor)):
    return studio.revise(p, proposal, body, if_match, actor)


@router.post("/api/v1/projects/{p}/proposal-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "proposal"})
def propose(studio: StudioDependency, p: str, body: ProposalRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "proposal", body.model_dump(), idempotency_key, actor)


@router.post("/api/v1/projects/{p}/validation-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "validation"})
def validate(studio: StudioDependency, p: str, body: BundleRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "validation", body.model_dump(), idempotency_key, actor)


@router.post("/api/v1/projects/{p}/assessment-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "assessment"})
def assess(studio: StudioDependency, p: str, body: BundleRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "assessment", body.model_dump(), idempotency_key, actor)


@router.post("/api/v1/projects/{p}/repair-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "repair"})
def repair(studio: StudioDependency, p: str, body: RepairRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "repair", body.model_dump(), idempotency_key, actor)


@router.post("/api/v1/projects/{p}/question-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "question"})
def question(studio: StudioDependency, p: str, body: QuestionRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "question", body.model_dump(), idempotency_key, actor)


@router.post("/api/v1/projects/{p}/test-generation-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "test-generation"})
def generate_tests(studio: StudioDependency, p: str, body: TestGenerationRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "test-generation", body.model_dump(), idempotency_key, actor)


@router.post("/api/v1/projects/{p}/test-oracle-decisions", status_code=201, response_model=wire.OracleDecisionResponse | wire.RevisionResponse, response_model_exclude_unset=True)
def oracle_decision(studio: StudioDependency, p: str, body: OracleDecision, actor=Depends(project_actor)):
    return studio.oracle_decision(p, body, actor)


@router.get("/api/v1/projects/{p}/test-suites", response_model=wire.Page[wire.TestSuiteResponse], response_model_exclude_unset=True)
def test_suites(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        return page([studio.body(i) for i in studio.items(s, p, "test_suite")], cursor, limit)


@router.post("/api/v1/projects/{p}/review-sessions", status_code=201, response_model=wire.ReviewTimingResponse, response_model_exclude_unset=True)
def review_session(studio: StudioDependency, p: str, body: ReviewSessionEvent, actor=Depends(project_actor)):
    return studio.review_session(p, body, actor)


@router.get("/api/v1/projects/{p}/review-sessions", response_model=wire.Page[wire.ReviewTimingResponse], response_model_exclude_unset=True)
def review_sessions(studio: StudioDependency, p: str, revision_id: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.get(s, p, revision_id, "revision")
        records = [studio.body(i) for i in studio.items(s, p, "review_session") if i.data["revision_id"] == revision_id and i.data["actor"]["subject"] == actor["subject"]]
        return page(records, cursor, limit)


@router.post("/api/v1/projects/{p}/review-submissions", status_code=201, response_model=wire.RevisionResponse, response_model_exclude_unset=True)
def submit(studio: StudioDependency, p: str, body: Submission, if_match: str = Header(...), actor=Depends(project_actor)):
    return studio.submit(p, body, if_match, actor)


@router.post("/api/v1/projects/{p}/reviews", status_code=201, response_model=wire.ReviewResponse, response_model_exclude_unset=True)
def review(studio: StudioDependency, p: str, body: ReviewRequest, actor=Depends(project_actor)):
    return studio.review(p, body, actor)


@router.post("/api/v1/projects/{p}/publications", status_code=202, response_model=wire.PublicationResponse, response_model_exclude_unset=True)
def publish(studio: StudioDependency, p: str, body: PublishRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.publish(p, body, idempotency_key, actor)


@router.get("/api/v1/projects/{p}/publications/{publication}", response_model=wire.PublicationResponse, response_model_exclude_unset=True)
def publication(studio: StudioDependency, p: str, publication: str, actor=Depends(project_actor)):
    with studio.db.session() as s:
        result = studio.body(studio.get(s, p, publication, "publication"))
        errors = [i for i in studio.items(s, p, "publication_error") if i.data["publication_id"] == publication]
        return {**result, "error": errors[-1].data["message"] if errors and result["status"] != "completed" else None}


@router.get("/api/v1/projects/{p}/assessments/{report}", response_model=wire.AssessmentReportResponse, response_model_exclude_unset=True)
@router.get("/api/v1/projects/{p}/assessment-runs/{report}", response_model=wire.AssessmentReportResponse, response_model_exclude_unset=True)
def report(studio: StudioDependency, p: str, report: str, actor=Depends(project_actor)):
    with studio.db.session() as s:
        return studio.body(studio.get(s, p, report, "assessment"))


@router.get("/api/v1/projects/{p}/validation-runs/{report}", response_model=wire.ValidationReportResponse, response_model_exclude_unset=True)
def validation_report(studio: StudioDependency, p: str, report: str, actor=Depends(project_actor)):
    with studio.db.session() as s:
        return studio.body(studio.get(s, p, report, "validation"))


@router.get("/api/v1/projects/{p}/reviews/{review_id}", response_model=wire.ReviewResponse, response_model_exclude_unset=True)
def review_record(studio: StudioDependency, p: str, review_id: str, actor=Depends(project_actor)):
    with studio.db.session() as s:
        return studio.body(studio.get(s, p, review_id, "review"))


@router.get("/api/v1/projects/{p}/reviews", response_model=wire.Page[wire.ReviewResponse], response_model_exclude_unset=True)
def reviews(studio: StudioDependency, p: str, revision_id: str | None = None, cursor: str | None = None,
            limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        if revision_id is not None:
            studio.get(s, p, revision_id, "revision")
        records = [studio.body(i) for i in studio.items(s, p, "review")
                   if revision_id is None or i.data["revision_id"] == revision_id]
        return page(records, cursor, limit)
