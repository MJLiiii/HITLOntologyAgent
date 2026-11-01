from contextlib import asynccontextmanager
import base64
import binascii
import csv
import io
import json
import logging
import hmac
from pathlib import Path
from threading import Event, Thread
from typing import Annotated, Literal
from uuid import uuid4
from fastapi import Depends, FastAPI, File, Form, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from .auth import bootstrap_token, init_cookie, require_actor
from .assessment_contracts import MappingDraft
from .db import Job, Project
from .errors import Problem
from . import responses as wire
from .schemas import (BundleRequest, ExperimentRequest, IngestRequest, ProjectCreate, ProposalRequest,
                      PublishRequest, QuestionRequest, ReviewRequest, RevisionRequest, ScopeDecision, StrictModel, Submission, TestGenerationRequest, OracleDecision, ReviewSessionEvent, RationaleRequest, ScopeUpload, SeedImportRequest)
from .settings import Settings
from .request_limits import RequestBodyLimit
from .workflow import Studio
from pydantic import Field


class CorpusRequest(StrictModel):
    ingestion_run_ids: list[str] = Field(min_length=1, max_length=100)


class TrustGraphSnapshotRequest(StrictModel):
    ingestion_run_id: str
    chunk_uris: list[str] = Field(min_length=1, max_length=50)


class TrustGraphRecoveryRequest(StrictModel):
    preparation_id: str


class SyntheticTaskRegistration(BundleRequest):
    task_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,79}$")
    instruction: str = Field(min_length=5, max_length=4000)


class SyntheticTaskJob(StrictModel):
    registration_id: str
    registration_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    condition: Literal["A", "B", "C", "D", "all"] = "all"
    replicate_ids: list[Annotated[int, Field(ge=1, le=3)]] = Field(default_factory=lambda: [1], min_length=1, max_length=3)


class MappingSetRequest(StrictModel):
    mappings: list[MappingDraft] = Field(max_length=100)


class MappingDecision(StrictModel):
    mapping_set_id: str
    digest: str
    decision: Literal["accept", "reject"]
    rationale: str = Field(min_length=5, max_length=4000)


class ExperimentReviewLink(StrictModel):
    review_id: str


def create_app(settings=None):
    settings = settings or Settings()
    studio = Studio(settings)
    stopping = Event()

    def worker():
        while not stopping.is_set():
            try:
                studio.reconcile_pending(continue_on_error=True)
                worked = studio.work_once()
            except Exception:
                logging.getLogger(__name__).exception("Worker/recovery failed")
                worked = False
            if not worked:
                stopping.wait(.5)

    @asynccontextmanager
    async def lifespan(app):
        thread = None
        if not settings.eager_jobs:
            logging.getLogger("uvicorn.error").info("Local operator link (keep private): http://127.0.0.1:8000/#session=%s", app.state.bootstrap_token)
            thread = Thread(target=worker, daemon=True, name="ontology-worker")
            thread.start()
        yield
        stopping.set()
        if thread:
            thread.join(timeout=2)

    app = FastAPI(title="Ontology Studio API", version="0.1.0", lifespan=lifespan,
                  responses={status: {"model": wire.ProblemResponse} for status in (401, 403, 404, 409, 413, 422, 504)})
    app.state.settings, app.state.studio = settings, studio
    app.state.local_cookie = init_cookie(settings.data_dir)
    app.state.bootstrap_token = bootstrap_token(settings.data_dir)

    @app.exception_handler(Problem)
    async def problem_handler(request, exc):
        return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message, "details": exc.details, "correlation_id": str(uuid4())})

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse(status_code=422, content={"code": "invalid_content", "message": str(exc)[:500], "details": None, "correlation_id": str(uuid4())})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={"code": "invalid_request", "message": "Request does not match the API schema", "details": [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()], "correlation_id": str(uuid4())})

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.add_middleware(RequestBodyLimit, limit=settings.max_upload_bytes + 65536)

    @app.get("/api/v1/session", response_model=wire.SessionResponse, response_model_exclude_unset=True)
    def session(request: Request, response: Response, x_oe_session_token: str | None = Header(None), authorization: str | None = Header(None)):
        host, peer = request.url.hostname, request.client.host if request.client else ""
        if host not in {"127.0.0.1", "localhost", "testserver", "::1"} or peer not in {"127.0.0.1", "::1", "testclient"}:
            raise Problem(403, "local_only", "Local session is only available on loopback")
        if authorization:
            actor = require_actor(request)
            return {"actor": actor, "mode": "local", "model_mode": "model" if settings.model_url and settings.model_name else "local"}
        if not (hmac.compare_digest(request.cookies.get("oe_session", ""), app.state.local_cookie)
                or hmac.compare_digest(x_oe_session_token or "", app.state.bootstrap_token)):
            raise Problem(401, "operator_session_required", "Open the private operator link printed by the local server, or enter its session token")
        response.set_cookie("oe_session", app.state.local_cookie, httponly=True, samesite="strict", path="/", max_age=86400)
        return {"actor": {"subject": "local-human", "kind": "human", "roles": ["researcher", "reviewer", "approver", "viewer"]},
                "mode": "local", "model_mode": "model" if settings.model_url and settings.model_name else "local", "integrations": {"trustgraph": "configured_on_demand" if settings.trustgraph_config_file else "not_configured", "identity": "loopback_single_user"}}

    @app.get("/health/live", response_model=wire.LiveResponse, response_model_exclude_unset=True)
    @app.get("/api/v1/health/live", response_model=wire.LiveResponse, response_model_exclude_unset=True)
    def live():
        return {"status": "ok"}

    @app.get("/health/ready", response_model=wire.ReadyResponse, response_model_exclude_unset=True, responses={503: {"model": wire.ReadyResponse}})
    @app.get("/api/v1/health/ready", response_model=wire.ReadyResponse, response_model_exclude_unset=True, responses={503: {"model": wire.ReadyResponse}})
    def ready():
        from .health import dependencies
        from sqlalchemy.exc import SQLAlchemyError
        checks = dependencies(studio)
        try:
            with studio.db.session() as s:
                s.execute(select(Project.id).limit(1))
            checks["database"] = "available"
        except SQLAlchemyError:
            checks["database"] = "unavailable"
        available = all(value in {"available", "not_configured"} for value in checks.values())
        return JSONResponse(status_code=200 if available else 503,
                            content=wire.ReadyResponse.model_validate({"status": "ready" if available else "not_ready", "mode": "local", **checks,
                                     "trustgraph": "configured_on_demand" if settings.trustgraph_config_file else "not_configured", "shared_auth": "not_configured"}).model_dump())

    def page(items, cursor: str | None, limit: int):
        if limit < 1 or limit > 200:
            raise Problem(422, "invalid_limit", "Limit must be between 1 and 200")
        start = 0
        if cursor:
            indices = [i for i, value in enumerate(items) if value["id"] == cursor]
            if not indices:
                raise Problem(422, "invalid_cursor", "Unknown list cursor")
            start = indices[0] + 1
        selected = items[start:start + limit]
        return {"items": selected, "next_cursor": selected[-1]["id"] if start + limit < len(items) else None}

    @app.get("/api/v1/projects", response_model=wire.Page[wire.ProjectResponse], response_model_exclude_unset=True)
    def projects(cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            return page([studio.project_body(p) for p in s.scalars(select(Project).order_by(Project.id))], cursor, limit)

    @app.post("/api/v1/projects", status_code=201, response_model=wire.ProjectResponse, response_model_exclude_unset=True)
    def new_project(body: ProjectCreate, actor=Depends(require_actor)):
        return studio.create_project(body.name, body.domain, actor)

    @app.get("/api/v1/projects/{p}", response_model=wire.ProjectResponse, response_model_exclude_unset=True)
    def get_project(p: str, actor=Depends(require_actor)):
        with studio.db.session() as s:
            return studio.project_body(studio.project(s, p))

    @app.post("/api/v1/projects/{p}/scope-decisions", status_code=201, response_model=wire.ScopeDecisionResponse, response_model_exclude_unset=True)
    def scope(p: str, body: ScopeDecision, actor=Depends(require_actor)):
        return studio.scope_decision(p, body, actor)

    @app.post("/api/v1/projects/{p}/scope", status_code=201, response_model=wire.ScopeResponse, response_model_exclude_unset=True)
    def upload_scope(p: str, body: ScopeUpload, actor=Depends(require_actor)):
        return studio.upload_scope(p, body, actor)

    @app.get("/api/v1/projects/{p}/scope", response_model=wire.ScopeResponse, response_model_exclude_unset=True)
    def get_scope(p: str, actor=Depends(require_actor)):
        return studio.current_scope(p)

    @app.get("/api/v1/projects/{p}/scopes", response_model=wire.Page[wire.ScopeResponse], response_model_exclude_unset=True)
    def scopes(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.project(s, p)
            return page([studio.body(i) for i in studio.items(s, p, "scope")], cursor, limit)

    @app.post("/api/v1/projects/{p}/mapping-sets", status_code=201, response_model=wire.MappingSetResponse, response_model_exclude_unset=True)
    def mapping_set(p: str, body: MappingSetRequest, actor=Depends(require_actor)):
        return studio.draft_mappings(p, body, actor)

    @app.get("/api/v1/projects/{p}/mapping-sets", response_model=wire.Page[wire.MappingSetResponse], response_model_exclude_unset=True)
    def mapping_sets(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.project(s, p)
            return page([studio.body(i) for i in studio.items(s, p, "mapping_set")], cursor, limit)

    @app.post("/api/v1/projects/{p}/mapping-decisions", status_code=201, response_model=wire.MappingDecisionResponse, response_model_exclude_unset=True)
    def mapping_decision(p: str, body: MappingDecision, actor=Depends(require_actor)):
        return studio.decide_mappings(p, body, actor)

    @app.get("/api/v1/projects/{p}/mapping-config", response_model=wire.MappingConfigResponse, response_model_exclude_unset=True)
    def mapping_config(p: str, actor=Depends(require_actor)):
        from .artifacts import digest
        with studio.db.session() as s:
            project = studio.project(s, p)
            mappings = studio.approved_mappings(s, project)
            return {"decision_id": project.data.get("assessment_mapping_decision_id"), "digest": digest(mappings),
                    "scope_digest": project.data["scope_digest"], "mappings": mappings}

    @app.get("/api/v1/projects/{p}/corpus-evidence", response_model=wire.Page[wire.EvidenceResponse], response_model_exclude_unset=True)
    def corpus_evidence(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            project = studio.project(s, p)
            evidence = studio.corpus_evidence(s, p, project.corpus_snapshot_id) if project.corpus_snapshot_id else []
            return page(evidence, cursor, limit)

    @app.get("/api/v1/projects/{p}/generation-runs", response_model=wire.Page[wire.GenerationResponse], response_model_exclude_unset=True)
    def generations(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.project(s, p)
            return page([studio.body(i) for i in studio.items(s, p, "generation")], cursor, limit)

    @app.post("/api/v1/projects/{p}/seed-imports", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "seed-import"})
    def seed_import(p: str, body: SeedImportRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "seed-import", body.model_dump(), idempotency_key, actor)

    @app.get("/api/v1/projects/{p}/documents", response_model=wire.Page[wire.DocumentResponse], response_model_exclude_unset=True)
    def documents(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.project(s, p)
            return page([studio.document_body(s, i) for i in studio.items(s, p, "document")], cursor, limit)

    @app.post("/api/v1/projects/{p}/documents", status_code=201, response_model=wire.DocumentResponse, response_model_exclude_unset=True)
    async def upload(p: str, file: UploadFile = File(...), title: str = Form(..., min_length=1, max_length=120),
                     edition: str = Form("1", max_length=80), rights: str = Form("", max_length=500), classification: str = Form("synthetic"), actor=Depends(require_actor)):
        extension = Path(file.filename or "").suffix.lower()
        if extension not in {".txt", ".md", ".pdf"}:
            raise Problem(422, "unsupported_document", "Upload a PDF or UTF-8 .txt/.md file")
        content = await file.read(settings.max_upload_bytes + 1)
        return studio.upload(p, title, content, edition, classification, rights, actor,
                             "application/pdf" if extension == ".pdf" else "text/plain")

    @app.post("/api/v1/projects/{p}/ingestions", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "ingestion"})
    def ingest(p: str, body: IngestRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "ingestion", body.model_dump(), idempotency_key, actor)

    @app.post("/api/v1/projects/{p}/corpus-snapshots", status_code=201, response_model=wire.CorpusResponse, response_model_exclude_unset=True)
    def corpus(p: str, body: CorpusRequest, actor=Depends(require_actor)):
        return studio.freeze_corpus(p, body.ingestion_run_ids, actor)

    @app.post("/api/v1/projects/{p}/trustgraph-ingestions", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "trustgraph-ingestion"})
    def trustgraph_ingest(p: str, body: IngestRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "trustgraph-ingestion", body.model_dump(), idempotency_key, actor)

    @app.post("/api/v1/projects/{p}/trustgraph-ingestion-recoveries", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "trustgraph-recovery"})
    def trustgraph_recover(p: str, body: TrustGraphRecoveryRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "trustgraph-recovery", body.model_dump(), idempotency_key, actor)

    @app.post("/api/v1/projects/{p}/trustgraph-snapshots", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "trustgraph-snapshot"})
    def trustgraph_snapshot(p: str, body: TrustGraphSnapshotRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "trustgraph-snapshot", body.model_dump(), idempotency_key, actor)

    @app.get("/api/v1/projects/{p}/trustgraph-ingestions", response_model=wire.TrustGraphIngestionsResponse, response_model_exclude_unset=True)
    def trustgraph_ingestions(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.project(s, p)
            records = sorted([*studio.items(s, p, "trustgraph_ingestion"),
                              *studio.items(s, p, "trustgraph_preparation")], key=lambda i: (i.created_at, i.id))
            kinds = {i.id: i.kind for i in records}
            selected = page([studio.body(i) for i in records], cursor, limit)
            return {"items": [i for i in selected["items"] if kinds[i["id"]] == "trustgraph_ingestion"],
                    "preparations": [i for i in selected["items"] if kinds[i["id"]] == "trustgraph_preparation"],
                    "configured": bool(settings.trustgraph_config_file), "next_cursor": selected["next_cursor"]}

    @app.get("/api/v1/projects/{p}/trustgraph-ingestions/{ingestion}/chunks", response_model=wire.TrustGraphRegisteredChunksResponse, response_model_exclude_unset=True)
    def trustgraph_chunks(p: str, ingestion: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        from .trustgraph_workflow import list_chunks
        page([], None, limit)  # Reject invalid bounds before calling the upstream provider.
        previous = None
        if cursor:
            try:
                if len(cursor) > 4096:
                    raise ValueError("Cursor too long")
                previous = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
                if not isinstance(previous, list) or len(previous) != 4 or not all(isinstance(v, str) for v in previous):
                    raise ValueError("Invalid cursor shape")
            except (ValueError, binascii.Error):
                raise Problem(422, "invalid_cursor", "Invalid chunk discovery cursor") from None
        result = list_chunks(studio, p, ingestion)
        identity = [p, ingestion, result["provenance_artifact"]["sha256"]]
        if previous and previous[:3] != identity:
            raise Problem(409, "chunk_discovery_changed", "Chunk discovery changed; refresh the list before selecting passages")
        selected = page([{"id": uri} for uri in result["chunk_uris"]], previous[3] if previous else None, limit)
        following = (base64.urlsafe_b64encode(json.dumps([*identity, selected["next_cursor"]]).encode()).decode()
                     if selected["next_cursor"] else None)
        return {**result, "chunk_uris": [item["id"] for item in selected["items"]], "next_cursor": following}

    @app.get("/api/v1/projects/{p}/versions", response_model=wire.Page[wire.VersionResponse], response_model_exclude_unset=True)
    def versions(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.project(s, p)
            return page([studio.version_body(s, i) for i in studio.items(s, p, "version")], cursor, limit)

    @app.get("/api/v1/projects/{p}/versions/{version}", response_model=wire.VersionResponse, response_model_exclude_unset=True)
    def version(p: str, version: str, actor=Depends(require_actor)):
        with studio.db.session() as s:
            return studio.version_body(s, studio.get(s, p, version, "version"))

    @app.get("/api/v1/projects/{p}/proposals", response_model=wire.Page[wire.RevisionResponse], response_model_exclude_unset=True)
    def proposals(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            project = studio.project(s, p)
            return page([studio.revision_body(s, project, studio.revisions(s, p, proposal.id)[-1]) for proposal in studio.items(s, p, "proposal")], cursor, limit)

    @app.get("/api/v1/projects/{p}/proposals/{proposal}/revisions/{revision}", response_model=wire.RevisionResponse, response_model_exclude_unset=True)
    def revision(p: str, proposal: str, revision: int, actor=Depends(require_actor)):
        with studio.db.session() as s:
            return studio.revision_body(s, studio.project(s, p), studio.revision(s, p, proposal, revision))

    @app.post("/api/v1/projects/{p}/proposals/{proposal}/revisions", status_code=201, response_model=wire.RevisionResponse, response_model_exclude_unset=True)
    def revise(p: str, proposal: str, body: RevisionRequest, if_match: str = Header(...), actor=Depends(require_actor)):
        return studio.revise(p, proposal, body, if_match, actor)

    @app.post("/api/v1/projects/{p}/proposal-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "proposal"})
    def propose(p: str, body: ProposalRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "proposal", body.model_dump(), idempotency_key, actor)

    @app.post("/api/v1/projects/{p}/validation-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "validation"})
    def validate(p: str, body: BundleRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "validation", body.model_dump(), idempotency_key, actor)

    @app.post("/api/v1/projects/{p}/assessment-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "assessment"})
    def assess(p: str, body: BundleRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "assessment", body.model_dump(), idempotency_key, actor)

    @app.post("/api/v1/projects/{p}/repair-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "repair"})
    def repair(p: str, body: BundleRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "repair", body.model_dump(), idempotency_key, actor)

    @app.post("/api/v1/projects/{p}/question-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "question"})
    def question(p: str, body: QuestionRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "question", body.model_dump(), idempotency_key, actor)

    @app.post("/api/v1/projects/{p}/experiment-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "experiment"})
    def experiment(p: str, body: ExperimentRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "experiment", body.model_dump(), idempotency_key, actor)

    @app.post("/api/v1/projects/{p}/synthetic-tasks", status_code=201, response_model=wire.SyntheticTaskResponse, response_model_exclude_unset=True)
    def register_synthetic_task(p: str, body: SyntheticTaskRegistration, actor=Depends(require_actor)):
        from .research_workflow import register
        return register(studio, p, body, actor)

    @app.get("/api/v1/projects/{p}/synthetic-tasks", response_model=wire.Page[wire.SyntheticTaskResponse], response_model_exclude_unset=True)
    def synthetic_tasks(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.project(s, p)
            return page([studio.body(i) for i in studio.items(s, p, "synthetic_task")], cursor, limit)

    @app.post("/api/v1/projects/{p}/synthetic-task-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "synthetic-experiment"})
    def synthetic_task_run(p: str, body: SyntheticTaskJob, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "synthetic-experiment", body.model_dump(), idempotency_key, actor)

    @app.post("/api/v1/projects/{p}/test-generation-jobs", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "test-generation"})
    def generate_tests(p: str, body: TestGenerationRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.create_job(p, "test-generation", body.model_dump(), idempotency_key, actor)

    @app.post("/api/v1/projects/{p}/test-oracle-decisions", status_code=201, response_model=wire.OracleDecisionResponse | wire.RevisionResponse, response_model_exclude_unset=True)
    def oracle_decision(p: str, body: OracleDecision, actor=Depends(require_actor)):
        return studio.oracle_decision(p, body, actor)

    @app.get("/api/v1/projects/{p}/test-suites", response_model=wire.Page[wire.TestSuiteResponse], response_model_exclude_unset=True)
    def test_suites(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.project(s, p)
            return page([studio.body(i) for i in studio.items(s, p, "test_suite")], cursor, limit)

    @app.post("/api/v1/projects/{p}/review-sessions", status_code=201, response_model=wire.ReviewTimingResponse, response_model_exclude_unset=True)
    def review_session(p: str, body: ReviewSessionEvent, actor=Depends(require_actor)):
        return studio.review_session(p, body, actor)

    @app.get("/api/v1/projects/{p}/review-sessions", response_model=wire.Page[wire.ReviewTimingResponse], response_model_exclude_unset=True)
    def review_sessions(p: str, revision_id: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.get(s, p, revision_id, "revision")
            records = [studio.body(i) for i in studio.items(s, p, "review_session") if i.data["revision_id"] == revision_id and i.data["actor"]["subject"] == actor["subject"]]
            return page(records, cursor, limit)

    @app.post("/api/v1/projects/{p}/documents/{document_id}/withdrawal", status_code=201, response_model=wire.DocumentResponse, response_model_exclude_unset=True)
    def withdraw(p: str, document_id: str, body: RationaleRequest, actor=Depends(require_actor)):
        return studio.withdraw_source(p, document_id, body.rationale, actor)

    @app.post("/api/v1/projects/{p}/review-submissions", status_code=201, response_model=wire.RevisionResponse, response_model_exclude_unset=True)
    def submit(p: str, body: Submission, if_match: str = Header(...), actor=Depends(require_actor)):
        return studio.submit(p, body, if_match, actor)

    @app.post("/api/v1/projects/{p}/reviews", status_code=201, response_model=wire.ReviewResponse, response_model_exclude_unset=True)
    def review(p: str, body: ReviewRequest, actor=Depends(require_actor)):
        return studio.review(p, body, actor)

    @app.post("/api/v1/projects/{p}/publications", status_code=202, response_model=wire.PublicationResponse, response_model_exclude_unset=True)
    def publish(p: str, body: PublishRequest, idempotency_key: str = Header(...), actor=Depends(require_actor)):
        return studio.publish(p, body, idempotency_key, actor)

    @app.get("/api/v1/projects/{p}/publications/{publication}", response_model=wire.PublicationResponse, response_model_exclude_unset=True)
    def publication(p: str, publication: str, actor=Depends(require_actor)):
        with studio.db.session() as s:
            result = studio.body(studio.get(s, p, publication, "publication"))
            errors = [i for i in studio.items(s, p, "publication_error") if i.data["publication_id"] == publication]
            return {**result, "error": errors[-1].data["message"] if errors and result["status"] != "completed" else None}

    @app.get("/api/v1/projects/{p}/evidence/{evidence_id}", response_model=wire.EvidenceResponse, response_model_exclude_unset=True)
    def evidence(p: str, evidence_id: str, actor=Depends(require_actor)):
        with studio.db.session() as s:
            return studio.evidence(s, p, evidence_id)

    @app.get("/api/v1/projects/{p}/artifacts/{artifact_id}", response_class=Response, responses={200: {"description": "Verified immutable artifact bytes; Content-Type follows the stored media type", "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}}})
    def artifact(p: str, artifact_id: str, actor=Depends(require_actor)):
        ref, content = studio.artifact(p, artifact_id)
        suffix = {"text/turtle": "ttl", "text/plain": "txt", "application/json": "json"}.get(ref["media_type"], "bin")
        return Response(content, media_type=ref["media_type"], headers={"Content-Disposition": f'attachment; filename="{artifact_id}.{suffix}"'})

    @app.get("/api/v1/projects/{p}/assessments/{report}", response_model=wire.AssessmentReportResponse, response_model_exclude_unset=True)
    @app.get("/api/v1/projects/{p}/assessment-runs/{report}", response_model=wire.AssessmentReportResponse, response_model_exclude_unset=True)
    def report(p: str, report: str, actor=Depends(require_actor)):
        with studio.db.session() as s:
            return studio.body(studio.get(s, p, report, "assessment"))

    @app.get("/api/v1/projects/{p}/validation-runs/{report}", response_model=wire.ValidationReportResponse, response_model_exclude_unset=True)
    def validation_report(p: str, report: str, actor=Depends(require_actor)):
        with studio.db.session() as s:
            return studio.body(studio.get(s, p, report, "validation"))

    @app.get("/api/v1/projects/{p}/reviews/{review_id}", response_model=wire.ReviewResponse, response_model_exclude_unset=True)
    def review_record(p: str, review_id: str, actor=Depends(require_actor)):
        with studio.db.session() as s:
            return studio.body(studio.get(s, p, review_id, "review"))

    @app.get("/api/v1/projects/{p}/reviews", response_model=wire.Page[wire.ReviewResponse], response_model_exclude_unset=True)
    def reviews(p: str, revision_id: str | None = None, cursor: str | None = None,
                limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.project(s, p)
            if revision_id is not None:
                studio.get(s, p, revision_id, "revision")
            records = [studio.body(i) for i in studio.items(s, p, "review")
                       if revision_id is None or i.data["revision_id"] == revision_id]
            return page(records, cursor, limit)

    @app.get("/api/v1/projects/{p}/audit", response_model=wire.Page[wire.AuditResponse], response_model_exclude_unset=True)
    def audit(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.project(s, p)
            return page([studio.body(i) for i in studio.items(s, p, "audit")], cursor, limit)

    @app.get("/api/v1/projects/{p}/experiments", response_model=wire.Page[wire.ExperimentResponse], response_model_exclude_unset=True)
    def experiments(p: str, cursor: str | None = None, limit: int = 50, actor=Depends(require_actor)):
        with studio.db.session() as s:
            studio.project(s, p)
            return page([studio.experiment_body(i) for i in studio.items(s, p, "experiment")], cursor, limit)

    @app.post("/api/v1/projects/{p}/experiments/{run_id}/proposal", status_code=201, response_model=wire.RevisionResponse, response_model_exclude_unset=True)
    def experiment_proposal(p: str, run_id: str, actor=Depends(require_actor)):
        return studio.stage_experiment(p, run_id, actor)

    @app.post("/api/v1/projects/{p}/experiments/{run_id}/review-results", status_code=201, response_model=wire.ExperimentResponse, response_model_exclude_unset=True)
    def experiment_review(p: str, run_id: str, body: ExperimentReviewLink, actor=Depends(require_actor)):
        return studio.link_experiment_review(p, run_id, body.review_id, actor)

    @app.get("/api/v1/projects/{p}/experiments/export", response_model=wire.ExperimentExport, responses={200: {"content": {"text/csv": {"schema": {"type": "string"}}}}})
    def export(p: str, format: str = "csv", actor=Depends(require_actor)):
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

    @app.get("/api/v1/jobs/{job_id}", response_model=wire.JobResponse, response_model_exclude_unset=True)
    def job(job_id: str, actor=Depends(require_actor)):
        with studio.db.session() as s:
            value = s.get(Job, job_id)
            if not value:
                raise Problem(404, "not_found", "Job not found")
            studio.project(s, value.project_id)
            return {"id": value.id, "status": value.status, "result": value.result, "error": value.error, "stage": value.kind,
                    "progress": 1 if value.status in {"succeeded", "failed"} else 0, "created_at": value.created_at}

    root = Path(__file__).resolve().parents[4]
    web = root / "apps/studio-plugin/dist"
    if web.exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="studio")
    return app


app = create_app()
