"""Wire response contracts. Stable records reject undeclared fields.

Only provider/engine diagnostic records permit JSON-valued extensions: their raw
payloads are retained evidence, not a fixed application DTO. Route serialization
uses exclude_unset so optional fields absent in historical records stay absent;
explicit nulls (including missing measurements) are never discarded.
"""
from typing import Annotated, Generic, Literal, TypeVar, Union
from pydantic import BaseModel, ConfigDict, Field, RootModel, StrictBool, StrictFloat, StrictInt, StrictStr
from .assessment_contracts import ApprovedMapping, MappingDraft
from .schemas import Triple, ScopeDecision, ReviewRequest, OracleDecision, TestSpec
from .integrations.trustgraph.contracts import PreparedIngestion, IngestReceipt, ImportedSnapshot, ImportedChunk

from typing_extensions import TypeAliasType

JsonValue = TypeAliasType("JsonValue", Union[dict[str, "JsonValue"], list["JsonValue"], StrictBool, StrictStr, StrictInt, StrictFloat, None])
Number = int | float
JSON = dict[str, JsonValue]
T = TypeVar('T')


class WireModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class DiagnosticRecord(BaseModel):
    """Extensible upstream diagnostics, with all extension values valid JSON."""
    model_config = ConfigDict(extra='allow')
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)


class Actor(WireModel):
    subject: str
    kind: Literal['human', 'service']
    roles: list[str]


class ArtifactRef(WireModel):
    # Early immutable records identify bytes by hash without a download-route ID.
    id: str | None = None
    sha256: str
    byte_length: int
    media_type: str
    schema_version: int


class Record(WireModel):
    id: str
    status: str
    created_at: str


class Page(WireModel, Generic[T]):
    items: list[T]
    next_cursor: str | None


class Items(WireModel, Generic[T]):
    items: list[T]


class ProblemResponse(WireModel):
    code: str
    message: str
    details: JsonValue
    correlation_id: str


class SessionResponse(WireModel):
    actor: Actor
    mode: str
    model_mode: Literal['local', 'model']
    integrations: dict[str, str] | None = None


class LiveResponse(WireModel):
    status: Literal['ok']


class ReadyResponse(WireModel):
    status: Literal['ready', 'not_ready']
    mode: str
    jena: str
    ontocheck: str
    model: str
    database: str
    trustgraph: str
    shared_auth: str


class QuestionResponse(WireModel):
    id: str
    question: str
    sparql_query: str
    required: bool = True
    expected: bool | None = None


class ProjectResponse(WireModel):
    id: str
    name: str
    domain: str
    approved_version_id: str | None
    corpus_snapshot_id: str | None
    pending_publication_id: str | None
    mode: str
    description: str | None = None
    scope_digest: str
    scope_accepted: bool
    review_policy_id: str
    competency_questions: list[QuestionResponse]
    scope_id: str | None = None
    shapes_ttl: str | None = None
    fixtures_ttl: str | None = None
    assessment_mapping_decision_id: str | None = None
    assessment_mappings_digest: str | None = None


class ScopeQuestion(QuestionResponse):
    expected: bool


class ScopeResponse(WireModel):
    id: str | None
    title: str
    purpose: str
    namespace: str
    competency_questions: list[ScopeQuestion]
    shapes_ttl: str
    fixtures_ttl: str
    digest: str
    status: str
    accepted: bool | None = None
    created_at: str | None = None
    actor: Actor | None = None


class ScopeDecisionResponse(ScopeDecision, Record):
    actor: Actor


class MappingSetResponse(Record):
    mappings: list[MappingDraft]
    scope_digest: str
    digest: str
    actor: Actor


class MappingDecisionResponse(Record):
    mapping_set_id: str
    decision: Literal['accept', 'reject']
    rationale: str
    actor: Actor
    mappings: list[ApprovedMapping]
    digest: str
    corpus_snapshot_id: str | None


class MappingConfigResponse(WireModel):
    decision_id: str | None
    digest: str
    scope_digest: str
    mappings: list[ApprovedMapping]


class ExtractionSummary(WireModel):
    status: str
    record_id: str
    report: ArtifactRef
    diagnostics: list[str] | None = None


class DocumentResponse(Record):
    title: str
    edition: str
    classification: str
    rights: str
    artifact: ArtifactRef
    content_hash: str
    ingestion_run_id: str | None
    ingestion_status: str | None
    extraction: ExtractionSummary | None
    chunk_count: int


class EvidenceResponse(Record):
    document_id: str
    title: str
    quote: str
    locator: str
    span_start: int
    span_end: int
    source_hash: str
    chunk: ArtifactRef
    content_hash: str
    adapter: str
    resolved: bool
    page: int | None = None
    extraction_record_id: str | None = None
    extraction_text: ArtifactRef | None = None
    provenance: ImportedChunk | None = None


class CorpusResponse(Record):
    ingestion_run_ids: list[str]
    document_ids: list[str]
    evidence_ids: list[str]
    digest: str
    provider: Literal['trustgraph'] | None = None
    selection_kind: Literal['explicit_registered_chunks'] | None = None
    upstream_completion_supported: Literal[False] | None = None
    provider_snapshot: ImportedSnapshot | None = None


class EvidenceHash(WireModel):
    id: str
    hash: str


class BundleManifest(WireModel):
    # Missing legacy scope/mapping metadata stays absent in reads. Eligibility
    # checks the frozen manifest itself and still requires a current successor.
    schema_version: int
    project_id: str
    base_version_id: str | None
    ontology: ArtifactRef
    shapes: ArtifactRef
    fixtures: ArtifactRef
    tests: ArtifactRef
    questions: ArtifactRef
    mappings: ArtifactRef | None = None
    canonical_ontology_sha256: str
    corpus_snapshot_id: str
    corpus_digest: str
    evidence: list[EvidenceHash]
    policy: JSON
    scope_digest: str | None = None
    profile: str
    assessment_mappings: list[ApprovedMapping]
    assessment_mappings_digest: str | None = None
    inference_graph: str
    mapping_decision_id: str | None = None
    mapping_source_snapshot_id: str | None = None
    mapping_evidence: list[EvidenceHash] | None = None
    engine_configuration: JSON


class VersionResponse(Record):
    label: str
    ontology: ArtifactRef
    parent_version_id: str | None
    commit: str | None
    source_snapshot_id: str | None
    triple_count: int
    class_count: int
    property_count: int
    triples: list[Triple]
    ttl: str
    bundle_digest: str | None = None
    publication_id: str | None = None
    reviewer: str | None = None
    manifest: BundleManifest | None = None


class Engine(DiagnosticRecord):
    name: str
    version: str | None = None
    runner_version: str | None = None
    isolation: JSON | None = None
    jar_sha256: str | None = None
    commit: str | None = None
    network: str | None = None
    network_control: str | None = None


class ValidationCase(DiagnosticRecord):
    id: str
    status: str
    name: str | None = None
    message: str | None = None
    kind: str | None = None
    expected: JsonValue = None
    actual: JsonValue = None


class ValidationStage(DiagnosticRecord):
    name: str
    status: str
    message: str | None = None


class ValidationReportResponse(DiagnosticRecord):
    id: str
    status: Literal['passed', 'failed', 'error', 'timeout', 'unsupported']
    bundle_digest: str | None = None
    profile: str = 'rdfs'
    engine: Engine | str | None = None
    validation_graph: str | None = None
    cases: list[ValidationCase]
    stages: list[ValidationStage] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None
    revision_id: str | None = None
    metrics: dict[str, Number] | None = None
    asserted_graph_sha256: str | None = None
    inferred_graph_sha256: str | None = None
    shacl: JSON | None = None
    input_manifest: JSON | None = None
    raw_artifacts: dict[str, JsonValue] | None = None


class AssessmentReportResponse(DiagnosticRecord):
    id: str
    status: Literal['completed', 'error', 'timeout', 'unsupported', 'not_run']
    bundle_digest: str | None = None
    vocabulary_coverage: Number | None = None
    vocabulary_utilisation: Number | None = None
    strict_fitness: Number | None = None
    approximate_fitness: Number | None = None
    structural_fitness: Number | None = None
    engine: Engine | None = None
    questions: list[QuestionResponse] | None = None
    mappings: list[ApprovedMapping] | None = None
    mappings_sha256: str | None = None
    mapping_diagnostics: JSON | None = None
    authorize_prefix_mapping: bool | None = None
    raw: JSON | None = None
    deltas: JSON | None = None
    denominators: JSON | None = None
    missing_reasons: JSON | None = None
    limitations: list[str] = Field(default_factory=list)
    created_at: str | None = None
    revision_id: str | None = None


class Eligibility(WireModel):
    eligible: bool
    reasons: list[str]


class RevisionHistory(WireModel):
    revision: int
    status: str
    created_at: str


class RevisionResponse(Record):
    proposal_id: str
    revision_id: str
    revision: int
    base_version_id: str | None
    title: str
    summary: str
    manifest: BundleManifest
    bundle_digest: str
    ontology: ArtifactRef
    shapes: ArtifactRef
    fixtures: ArtifactRef
    tests: ArtifactRef
    questions: ArtifactRef
    mappings: ArtifactRef | None = None
    additions: list[Triple]
    deletions: list[Triple]
    rationale: str
    evidence_ids: list[str]
    corpus_snapshot_id: str
    actor: Actor
    assumptions: list[str]
    experiment_run_id: str | None = None
    experiment_pre_candidate_digest: str | None = None
    evidence: list[EvidenceResponse]
    validation: ValidationReportResponse | None
    assessment: AssessmentReportResponse | None
    validation_run_id: str | None
    assessment_run_ids: list[str]
    approval_ids: list[str]
    stale: bool
    review_eligibility: Eligibility
    history: list[RevisionHistory]


class RetrievalSummary(WireModel):
    method: str
    evidence_available: int
    evidence_selected: int
    evidence_unresolved: int
    triples_available: int
    triples_selected: int
    truncated: bool


class AnswerResponse(WireModel):
    query: str | None = None
    answer: str
    evidence: list[EvidenceResponse]
    triples: list[Triple]
    version_id: str | None
    ontology_status: str
    limitations: list[str]
    unresolved_points: list[str] | None = None
    mode: str
    generation_run_id: str | None = None
    retrieval: RetrievalSummary | None = None
    corpus_snapshot_id: str | None
    source_selection: Literal['ontology_version', 'project_current', 'explicit']
    context_digest: str


class TestSpecResponse(TestSpec):
    # Existing mandatory tests predate generated-fixture metadata. Output preserves
    # that absence; accepted tests add immutable human oracle lineage.
    oracle_status: Literal['needs_review', 'required', 'accepted'] = 'required'
    oracle_decision_id: str | None = None
    rationale: str = 'Required competency question'
    name: str | None = None


class TestGenerator(WireModel):
    mode: str
    version: str
    implementation_sha256: str
    maximum_cases: int
    oracle_policy: str


class CoverageGap(WireModel):
    code: str
    detail: str
    shape: str | None = None


class TestSuiteResponse(Record):
    revision_id: str
    bundle_digest: str
    tests: list[TestSpecResponse]
    generator: TestGenerator
    input_manifest: JSON
    coverage_gaps: list[CoverageGap]
    fixture_artifacts: dict[str, ArtifactRef]
    split: Literal['development']
    origin: Literal['synthetic']
    digest: str
    actor: Actor


class OracleDecisionResponse(OracleDecision, Record):
    actor: Actor


class ReviewTimingResponse(Record):
    revision_id: str
    event: Literal['start', 'pause', 'resume', 'end']
    actor: Actor
    time: str
    active_seconds: Number


class ReviewResponse(ReviewRequest, Record):
    revision_id: str
    actor: Actor


class PublicationResponse(Record):
    proposal_id: str
    revision: int
    bundle_digest: str
    approval_ids: list[str]
    expected_head: str | None
    revision_id: str
    request_digest: str
    idempotency_key: str
    actor: Actor
    expected_commit: str | None
    new_version_id: str
    commit: str | None = None
    error: str | None = None


class AuditResponse(Record):
    sequence: int
    actor: Actor
    action: str
    entity: str
    detail_digest: str
    previous_event_hash: str | None
    time: str
    event_hash: str


class ModelProfileResponse(WireModel):
    id: str
    revision: str
    provider: str
    model: str
    purposes: list[str]
    structured_output: str
    max_output_tokens: int
    status: str
    is_default: bool


class GenerationResponse(DiagnosticRecord):
    id: str
    status: str
    created_at: str
    kind: str
    context: JSON
    provider: str
    model: str
    prompt_digest: str
    system_prompt: str
    temperature: Number | None
    seed: int | None
    cost: Number | None
    cost_missing_reason: str | None
    input_tokens: int | None = None
    output_tokens: int | None = None
    elapsed_seconds: Number | None = None
    raw_output: str | None = None
    output: JSON | None = None
    error: str | None = None
    validation_errors: list[JSON] | None = None
    job_id: str | None = None
    repair_attempt_id: str | None = None


class ProjectContext(WireModel):
    ontology_sha256: str | None = None
    base_version_id: str | None
    corpus_snapshot_id: str
    scope_digest: str
    evidence_ids: list[str]
    proposal_evidence_ids: list[str] | None = None
    engine_configuration: JSON
    assessment_mappings_digest: str | None = None
    registration_id: str | None = None


class SyntheticTaskResponse(Record):
    task_id: str
    instruction: str
    proposal_id: str
    revision: int
    bundle_digest: str
    protocol_id: Literal['synthetic-task-v1']
    classification: Literal['synthetic']
    revision_id: str
    registration_digest: str
    packet: ArtifactRef
    project_context: ProjectContext
    actor: Actor


class Measurement(WireModel):
    value: Number | None
    numerator: Number | None
    denominator: Number | None
    unit: str
    missing_reason: str | None


class ExperimentModel(WireModel):
    profile_id: str | None = None
    profile_revision: str | None = None
    structured_output: str | None = None
    effective_parameters: JSON | None = None
    provider: str
    name: str
    temperature: Number | None
    seed: int | None
    seed_missing_reason: str
    weights_digest: str | None
    weights_digest_missing_reason: str


class ValidationEvaluation(ValidationReportResponse):
    id: str | None = None
    status: Literal['passed', 'failed', 'error', 'timeout', 'unsupported', 'not_run']


class AssessmentEvaluation(AssessmentReportResponse):
    id: str | None = None


class ExperimentResponse(DiagnosticRecord):
    """Sealed records retain all experimental/provider diagnostics verbatim."""
    id: str
    status: str
    created_at: str
    protocol_id: str
    task_id: str
    replicate: int
    condition: Literal['A', 'B', 'C', 'D']
    mode: str
    evaluation_status: str
    study_status: str
    workload_id: str
    phase: str
    task_packet_digest: str
    agent_manifest: JSON
    source_bundle_digest: str
    initial_candidate_digest: str | None
    candidate_digest: str | None
    candidate_ttl: str | None
    evaluation_manifest: JSON
    budget: JSON
    repair_history: list[JSON]
    validation: ValidationEvaluation
    assessment: AssessmentEvaluation
    metrics: dict[str, Measurement]
    case_counts: dict[str, int]
    elapsed_seconds: Number | None
    review_status: str
    review_decisions: list[ReviewResponse]
    post_review_snapshot: JSON | None
    pre_review_snapshot: JSON | None
    limitations: list[str]
    vocabulary_coverage: Number | None
    vocabulary_utilisation: Number | None
    strict_fitness: Number | None
    approximate_fitness: Number | None
    structural_fitness: Number | None
    answer_precision: Number | None
    answer_recall: Number | None
    correction_seconds: Number | None
    model: ExperimentModel | None = None
    record_digest: str | None = None
    batch_id: str | None = None
    seed_ontology_digest: str | None = None
    initial_generation_call_id: str | None = None
    evaluation_inputs: JSON | None = None
    environment: JSON | None = None
    generation_calls: list[JSON] | None = None
    generation_call_ids: list[str] | None = None
    usage_accounting: str | None = None
    elapsed_seconds_scope: str | None = None
    task_registration_digest: str | None = None
    stored_at: str | None = None
    sealed_record: ArtifactRef | None = None
    project_context: ProjectContext | None = None
    parent_run_id: str | None = None
    parent_record_digest: str | None = None
    workflow_review_reports: JSON | None = None
    expert_active_seconds: Number | None = None
    time_to_acceptance_right_censored: bool | None = None
    linked_review_id: str | None = None
    linked_revision_id: str | None = None


class ExperimentProvenance(WireModel):
    project_context: ProjectContext
    sealed_record: ArtifactRef
    stored_at: str


class ExperimentExport(WireModel):
    schema_version: Literal[2]
    demo_only: bool
    items: list[ExperimentResponse]
    provenance: dict[str, ExperimentProvenance]


class TrustGraphPreparationResponse(Record):
    server_configuration: JSON | None = None
    llm_profile: JSON | None = None
    llm_session_id: str | None = None
    job_id: str
    document_id: str
    prepared: PreparedIngestion
    actor: Actor


class TrustGraphIngestionResponse(Record):
    llm_profile: JSON | None = None
    llm_session_id: str | None = None
    preparation_id: str
    document_id: str
    job_id: str
    receipt: IngestReceipt
    upstream_completion_supported: Literal[False]


class TrustGraphIngestionsResponse(WireModel):
    items: list[TrustGraphIngestionResponse]
    preparations: list[TrustGraphPreparationResponse]
    configured: bool
    next_cursor: str | None


class TrustGraphRegisteredChunksResponse(WireModel):
    chunk_uris: list[str]
    source_id: str
    provenance_artifact: ArtifactRef
    selection_required: Literal[True]
    upstream_completion_supported: Literal[False]
    next_cursor: str | None


class IngestionResult(WireModel):
    ingestion_run_id: str
    document_id: str
    status: Literal['completed', 'incomplete']
    extraction: ExtractionSummary | None = None


class ProposalJobResult(WireModel):
    proposal_id: str
    revision: int
    bundle_digest: str
    repair_attempt: int | None = None


class ExperimentBatch(WireModel):
    runs: list[ExperimentResponse]


class JobRefResponse(WireModel):
    job_id: str
    status_url: str
    correlation_id: str | None = None


class JobEnvelope(WireModel, Generic[T]):
    model_configuration: JSON | None = None
    id: str
    status: Literal['queued', 'running', 'succeeded', 'failed', 'cancelled']
    result: T | None
    error: str | None
    progress: Number
    created_at: str


class ProposalJob(JobEnvelope[ProposalJobResult]):
    stage: Literal['proposal', 'seed-import', 'repair']


class IngestionJob(JobEnvelope[IngestionResult]):
    stage: Literal['ingestion']


class ValidationJob(JobEnvelope[ValidationReportResponse]):
    stage: Literal['validation']


class AssessmentJob(JobEnvelope[AssessmentReportResponse]):
    stage: Literal['assessment']


class QuestionJob(JobEnvelope[AnswerResponse]):
    stage: Literal['question']


class ExperimentJob(JobEnvelope[ExperimentBatch]):
    stage: Literal['experiment', 'synthetic-experiment']


class TestGenerationJob(JobEnvelope[TestSuiteResponse]):
    stage: Literal['test-generation']


class TrustGraphIngestionJob(JobEnvelope[TrustGraphIngestionResponse]):
    stage: Literal['trustgraph-ingestion', 'trustgraph-recovery']


class TrustGraphSnapshotJob(JobEnvelope[CorpusResponse]):
    stage: Literal['trustgraph-snapshot']


class JobResponse(RootModel[Annotated[
    ProposalJob | IngestionJob | ValidationJob | AssessmentJob | QuestionJob |
    ExperimentJob | TestGenerationJob | TrustGraphIngestionJob | TrustGraphSnapshotJob,
    Field(discriminator='stage'),
]]):
    """The persisted job kind selects its exact result serializer and schema."""
