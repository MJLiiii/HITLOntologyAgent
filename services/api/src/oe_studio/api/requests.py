"""Request envelopes specific to HTTP operations."""
from typing import Annotated, Literal

from pydantic import Field

from ..assessment_contracts import MappingDraft
from ..schemas import BundleRequest, StrictModel


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
    model_profile_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$")
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
