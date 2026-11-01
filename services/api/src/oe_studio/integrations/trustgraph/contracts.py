from typing import Literal, Protocol
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class Frozen(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class Artifact(Frozen):
    id: str = Field(pattern=r'^[a-f0-9-]{36}$')
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    byte_length: int = Field(ge=0, le=2_097_152)
    media_type: str
    schema_version: Literal[1] = 1


class Binding(Frozen):
    """Constructed by trusted server configuration, never from request JSON."""
    project_id: UUID
    url: str
    workspace: str = Field(min_length=1, max_length=120, pattern=r'^[A-Za-z0-9_-]+$')
    flow: str = Field(min_length=1, max_length=120, pattern=r'^[A-Za-z0-9_-]+$')
    collection: str = Field(min_length=1, max_length=120, pattern=r'^[A-Za-z0-9_-]+$')
    seed_digest: str = Field(pattern=r'^(sha256:)?[a-f0-9]{64}$')
    config_digest: str = Field(pattern=r'^(sha256:)?[a-f0-9]{64}$')
    token: SecretStr = SecretStr('')
    timeout: float = Field(default=30, gt=0, le=60)

    @model_validator(mode='after')
    def endpoint(self):
        url = urlparse(self.url)
        if (url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ('', '/')
                or (url.scheme == 'http' and url.hostname not in ('localhost', '127.0.0.1', '::1'))):
            raise ValueError('TrustGraph needs an HTTPS server base URL or loopback HTTP URL')
        return self


class DocumentRegistration(Frozen):
    project_id: UUID
    source_id: UUID
    upstream_document_id: str = Field(min_length=1, max_length=2048)
    artifact: Artifact
    source_uri: str
    title: str


class IngestRequest(Frozen):
    project_id: UUID
    source_id: UUID
    artifact: Artifact
    seed_digest: str = Field(pattern=r'^(sha256:)?[a-f0-9]{64}$')
    config_digest: str = Field(pattern=r'^(sha256:)?[a-f0-9]{64}$')
    idempotency_key: str = Field(min_length=1, max_length=120)


class IngestReceipt(Frozen):
    ingestion_id: UUID
    project_id: UUID
    source_id: UUID
    document_uri: str
    processing_id: str
    binding_digest: str
    seed_digest: str
    config_digest: str
    status: Literal['queued', 'failed']
    raw_artifact: Artifact


class IngestStatus(Frozen):
    ingestion_id: UUID
    status: Literal['uploaded', 'queued', 'processing', 'completed', 'failed', 'unknown']
    observed_at: str
    completion_supported: bool
    corpus_freeze_allowed: bool = False
    reason: str | None = None
    provenance_artifacts: tuple[Artifact, ...] = ()
    mode: Literal['real', 'fake'] = 'real'


class EvidenceRef(Frozen):
    id: UUID
    project_id: UUID
    corpus_id: UUID
    source_id: UUID
    upstream_chunk_uri: str = Field(min_length=1, max_length=2048)
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    chunk_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    byte_start: int = Field(ge=0)
    byte_end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=8000)
    page_uri: str | None = None
    graph_uri: str | None = None


class CorpusRegistration(Frozen):
    project_id: UUID
    corpus_id: UUID
    evidence: tuple[EvidenceRef, ...]
    graph_uri: str = Field(pattern=r'^(urn:|https?://)\S+$')
    provenance_verified: bool = False


class RetrievalRequest(Frozen):
    project_id: UUID
    corpus_id: UUID
    query: str = Field(min_length=1, max_length=4000)
    base_ontology_digest: str = Field(pattern=r'^(sha256:)?[a-f0-9]{64}$')
    retrieval_config_digest: str = Field(pattern=r'^(sha256:)?[a-f0-9]{64}$')
    entity_limit: int = Field(default=20, ge=1, le=50)
    triple_limit: int = Field(default=100, ge=1, le=1000)
    chunk_limit: int = Field(default=20, ge=1, le=50)
    token_limit: int = Field(default=4096, ge=1, le=8192)


class EvidenceRecord(Frozen):
    ref: EvidenceRef
    resolved: bool
    reason: str | None = None
    quote: str | None = None
    chunk_artifact: Artifact | None = None
    raw_artifact: Artifact | None = None


class ContextBundle(Frozen):
    manifest_digest: str
    manifest_artifact: Artifact
    graph_artifact: Artifact
    raw_artifact: Artifact
    evidence: tuple[EvidenceRecord, ...]
    unresolved_source_uris: tuple[str, ...]
    truncated: bool
    review_eligible: bool
    reasons: tuple[str, ...]
    mode: Literal['real', 'fake']


class TrustGraphGateway(Protocol):
    async def ingest(self, request: IngestRequest) -> IngestReceipt: ...
    async def ingestion_status(self, receipt: IngestReceipt) -> IngestStatus: ...
    async def retrieve(self, request: RetrievalRequest) -> ContextBundle: ...
    async def resolve_evidence(self, ref: EvidenceRef) -> EvidenceRecord: ...
