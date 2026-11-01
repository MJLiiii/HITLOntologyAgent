import re
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


IRI_PATTERN = r"^https?://[^\s<>\"{}|^`\\]+$"


def valid_iri(value: str) -> bool:
    return bool(re.match(IRI_PATTERN, value))


class Triple(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    subject: str = Field(max_length=2048, pattern=IRI_PATTERN)
    predicate: str = Field(max_length=2048, pattern=IRI_PATTERN)
    object: str = Field(max_length=8000, description="Full HTTP(S) IRI when object_type is iri; exact lexical text when literal. Never use a prefixed name such as demo:Service.")
    object_type: Literal["iri", "literal"] = "iri"
    datatype: str | None = None
    language: str | None = None

    @model_validator(mode="after")
    def valid_terms(self):
        if not all(valid_iri(v) for v in [self.subject, self.predicate]):
            raise ValueError("Subject and predicate must be absolute HTTP(S) IRIs")
        if self.object_type == "iri" and (not valid_iri(self.object) or self.datatype or self.language):
            raise ValueError("Invalid IRI object")
        if self.datatype and (self.language or not valid_iri(self.datatype)):
            raise ValueError("Literal requires either datatype or language")
        if self.language and not re.fullmatch(r"[a-zA-Z]+(?:-[a-zA-Z0-9]+)*", self.language):
            raise ValueError("Invalid language tag")
        return self


class ChangeSet(StrictModel):
    additions: list[Triple] = Field(default_factory=list, max_length=100)
    deletions: list[Triple] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def bounded(self):
        if len(self.additions) + len(self.deletions) > 100:
            raise ValueError("At most 100 triple operations")
        return self


class ProjectCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    domain: Literal["unselected", "demo"] = "unselected"


class ScopeDecision(StrictModel):
    scope_digest: str
    decision: Literal["accept", "reject"]
    rationale: str = Field(min_length=5, max_length=4000)


class CompetencyQuestion(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=5, max_length=1000)
    sparql_query: str = Field(min_length=5, max_length=4000)
    expected: bool
    required: Literal[True] = True


class ScopeUpload(StrictModel):
    title: str = Field(min_length=3, max_length=120)
    purpose: str = Field(min_length=5, max_length=4000)
    namespace: Literal["https://example.org/oe-demo/"] = "https://example.org/oe-demo/"
    competency_questions: list[CompetencyQuestion] = Field(min_length=1, max_length=20)
    shapes_ttl: str = Field(default="", max_length=100000)
    fixtures_ttl: str = Field(default="", max_length=100000)

    @model_validator(mode="after")
    def unique_questions(self):
        ids = [q.id for q in self.competency_questions]
        if len(set(ids)) != len(ids):
            raise ValueError("Competency-question IDs must be unique")
        return self


class SeedImportRequest(StrictModel):
    ontology_ttl: str = Field(min_length=1, max_length=1048576)
    corpus_snapshot_id: str
    rationale: str = Field(min_length=5, max_length=4000)
    profile: Literal["rdfs"] = "rdfs"


class IngestRequest(StrictModel):
    document_id: str
    configured_flow_key: Literal["default"] = "default"


class ProposalRequest(StrictModel):
    base_version_id: str | None = None
    corpus_snapshot_id: str | None = None
    competency_question_ids: list[str] = Field(default_factory=list, max_length=20)
    instruction: str = Field(default="Create an ontology from the demo evidence", min_length=1, max_length=4000)


class RevisionRequest(StrictModel):
    parent_revision: int = Field(ge=1)
    structured_changes: ChangeSet
    rationale: str = Field(min_length=5, max_length=4000)


class BundleRequest(StrictModel):
    proposal_id: str
    revision: int = Field(ge=1)
    bundle_digest: str


class Submission(StrictModel):
    proposal_id: str
    revision: int = Field(ge=1)
    validation_run_id: str
    required_assessment_run_ids: list[str] = Field(max_length=10)


class ReviewRequest(BundleRequest):
    validation_run_id: str
    required_assessment_run_ids: list[str] = Field(max_length=10)
    decision: Literal["accept", "request_changes", "reject"]
    rationale: str = Field(min_length=5, max_length=4000)
    review_policy_id: str


class PublishRequest(BundleRequest):
    approval_ids: list[str] = Field(min_length=1, max_length=10)
    expected_head: str | None = None


class Message(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class QuestionRequest(StrictModel):
    question: str = Field(min_length=1, max_length=4000)
    proposal_id: str | None = None
    revision: int | None = Field(default=None, ge=1)
    history: list[Message] = Field(default_factory=list, max_length=12)
    conversation_id: str | None = None

    @model_validator(mode="after")
    def paired(self):
        if (self.proposal_id is None) != (self.revision is None):
            raise ValueError("Proposal and revision must be supplied together")
        return self


class TestSpec(StrictModel):
    test_id: str = Field(min_length=1, max_length=80)
    kind: Literal["ask", "select_rows", "shacl"]
    split: Literal["development"] = "development"
    origin: Literal["synthetic", "manual"] = "synthetic"
    query: str | None = Field(default=None, max_length=4000)
    expected: bool | list[dict] | None = None
    expected_conforms: bool | None = None
    fixtures_ttl: str = Field(default="", max_length=20000)
    rationale: str = Field(min_length=5, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    oracle_status: Literal["needs_review"] = "needs_review"


class TestGenerationRequest(StrictModel):
    proposal_id: str
    revision: int = Field(ge=1)


class OracleDecision(StrictModel):
    test_suite_id: str
    test_suite_digest: str
    decision: Literal["accept", "reject"]
    rationale: str = Field(min_length=5, max_length=4000)


class ReviewSessionEvent(StrictModel):
    revision_id: str
    event: Literal["start", "pause", "resume", "end"]


class RationaleRequest(StrictModel):
    rationale: str = Field(min_length=5, max_length=4000)


class ExperimentRequest(StrictModel):
    protocol_id: Literal["demo-v1", "model-pilot-v1"] = "demo-v1"
    condition: Literal["A", "B", "C", "D", "all"] = "all"
    task_ids: list[Literal["demo-ownership"]] = Field(default_factory=lambda: ["demo-ownership"], min_length=1, max_length=1)
    replicate_ids: list[Annotated[int, Field(ge=1, le=3)]] = Field(default_factory=lambda: [1], min_length=1, max_length=3)
