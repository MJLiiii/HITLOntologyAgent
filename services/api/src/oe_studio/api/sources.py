"""Source uploads, frozen corpora and verified evidence."""
import base64
import binascii
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from fastapi.responses import Response

from .. import responses as wire
from ..errors import Problem
from ..schemas import IngestRequest, RationaleRequest, TrustGraphIngestRequest
from .dependencies import StudioDependency, project_actor
from .pagination import page
from .requests import CorpusRequest, TrustGraphRecoveryRequest, TrustGraphSnapshotRequest

router = APIRouter()


@router.get("/api/v1/projects/{p}/corpus-evidence", response_model=wire.Page[wire.EvidenceResponse], response_model_exclude_unset=True)
def corpus_evidence(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        project = studio.project(s, p)
        evidence = studio.corpus_evidence(s, p, project.corpus_snapshot_id) if project.corpus_snapshot_id else []
        return page(evidence, cursor, limit)


@router.get("/api/v1/projects/{p}/documents", response_model=wire.Page[wire.DocumentResponse], response_model_exclude_unset=True)
def documents(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        return page([studio.document_body(s, i) for i in studio.items(s, p, "document")], cursor, limit)


@router.post("/api/v1/projects/{p}/documents", status_code=201, response_model=wire.DocumentResponse, response_model_exclude_unset=True)
async def upload(studio: StudioDependency, p: str, file: UploadFile = File(...), title: str = Form(..., min_length=1, max_length=120),
                 edition: str = Form("1", max_length=80), rights: str = Form("", max_length=500), classification: str = Form("synthetic"), actor=Depends(project_actor)):
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".txt", ".md", ".pdf"}:
        raise Problem(422, "unsupported_document", "Upload a PDF or UTF-8 .txt/.md file")
    content = await file.read(studio.settings.max_upload_bytes + 1)
    return studio.upload(p, title, content, edition, classification, rights, actor,
                         "application/pdf" if extension == ".pdf" else "text/plain")


@router.post("/api/v1/projects/{p}/ingestions", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "ingestion"})
def ingest(studio: StudioDependency, p: str, body: IngestRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "ingestion", body.model_dump(), idempotency_key, actor)


@router.post("/api/v1/projects/{p}/corpus-snapshots", status_code=201, response_model=wire.CorpusResponse, response_model_exclude_unset=True)
def corpus(studio: StudioDependency, p: str, body: CorpusRequest, actor=Depends(project_actor)):
    return studio.freeze_corpus(p, body.ingestion_run_ids, actor)


@router.post("/api/v1/projects/{p}/trustgraph-ingestions", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "trustgraph-ingestion"})
def trustgraph_ingest(studio: StudioDependency, p: str, body: TrustGraphIngestRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "trustgraph-ingestion", body.model_dump(), idempotency_key, actor)


@router.post("/api/v1/projects/{p}/trustgraph-ingestion-recoveries", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "trustgraph-recovery"})
def trustgraph_recover(studio: StudioDependency, p: str, body: TrustGraphRecoveryRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "trustgraph-recovery", body.model_dump(), idempotency_key, actor)


@router.post("/api/v1/projects/{p}/trustgraph-snapshots", status_code=202, response_model=wire.JobRefResponse, response_model_exclude_unset=True, openapi_extra={"x-job-kind": "trustgraph-snapshot"})
def trustgraph_snapshot(studio: StudioDependency, p: str, body: TrustGraphSnapshotRequest, idempotency_key: str = Header(...), actor=Depends(project_actor)):
    return studio.create_job(p, "trustgraph-snapshot", body.model_dump(), idempotency_key, actor)


@router.get("/api/v1/projects/{p}/trustgraph-ingestions", response_model=wire.TrustGraphIngestionsResponse, response_model_exclude_unset=True)
def trustgraph_ingestions(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        records = sorted([*studio.items(s, p, "trustgraph_ingestion"),
                          *studio.items(s, p, "trustgraph_preparation")], key=lambda i: (i.created_at, i.id))
        kinds = {i.id: i.kind for i in records}
        selected = page([studio.body(i) for i in records], cursor, limit)
        return {"items": [i for i in selected["items"] if kinds[i["id"]] == "trustgraph_ingestion"],
                "preparations": [i for i in selected["items"] if kinds[i["id"]] == "trustgraph_preparation"],
                "configured": bool(studio.settings.trustgraph_config_file), "next_cursor": selected["next_cursor"]}


@router.get("/api/v1/projects/{p}/trustgraph-ingestions/{ingestion}/chunks", response_model=wire.TrustGraphRegisteredChunksResponse, response_model_exclude_unset=True)
def trustgraph_chunks(studio: StudioDependency, p: str, ingestion: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    from ..trustgraph_workflow import list_chunks
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


@router.post("/api/v1/projects/{p}/documents/{document_id}/withdrawal", status_code=201, response_model=wire.DocumentResponse, response_model_exclude_unset=True)
def withdraw(studio: StudioDependency, p: str, document_id: str, body: RationaleRequest, actor=Depends(project_actor)):
    return studio.withdraw_source(p, document_id, body.rationale, actor)


@router.get("/api/v1/projects/{p}/evidence/{evidence_id}", response_model=wire.EvidenceResponse, response_model_exclude_unset=True)
def evidence(studio: StudioDependency, p: str, evidence_id: str, actor=Depends(project_actor)):
    with studio.db.session() as s:
        return studio.evidence(s, p, evidence_id)


@router.get("/api/v1/projects/{p}/artifacts/{artifact_id}", response_class=Response, responses={200: {"description": "Verified immutable artifact bytes; Content-Type follows the stored media type", "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}}})
def artifact(studio: StudioDependency, p: str, artifact_id: str, actor=Depends(project_actor)):
    ref, content = studio.artifact(p, artifact_id)
    suffix = {"text/turtle": "ttl", "text/plain": "txt", "application/json": "json"}.get(ref["media_type"], "bin")
    return Response(content, media_type=ref["media_type"], headers={"Content-Disposition": f'attachment; filename="{artifact_id}.{suffix}"'})
