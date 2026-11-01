"""Reviewed tool correspondences, distinct from asserted RDF equivalence axioms."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .schemas import valid_iri

Identifier = Annotated[str, Field(min_length=1, max_length=200)]


class MappingDraft(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)

    requirement_iri: str = Field(min_length=1, max_length=2048)
    ontology_iri: str = Field(min_length=1, max_length=2048)
    relation_type: Literal['canonical_correspondence']
    rationale: str = Field(min_length=5, max_length=4000)
    evidence_ids: list[Identifier] = Field(min_length=1, max_length=20)

    @field_validator('requirement_iri', 'ontology_iri')
    @classmethod
    def absolute_iri(cls, value):
        if not valid_iri(value):
            raise ValueError('Mapping terms must be full HTTP(S) IRIs, never prefixes or labels')
        return value

    @field_validator('rationale')
    @classmethod
    def substantive_rationale(cls, value):
        if len(value.strip()) < 5:
            raise ValueError('A substantive mapping rationale is required')
        return value

    @field_validator('evidence_ids')
    @classmethod
    def distinct_evidence(cls, value):
        if any(not item.strip() for item in value) or len(value) != len(set(value)):
            raise ValueError('Mapping evidence IDs must be nonempty and unique')
        return value


class ApprovedMapping(MappingDraft):
    # The workflow derives these from an authenticated immutable review. The adapter
    # validates the record shape; it cannot independently authenticate an API actor.
    reviewer: Identifier
    review_id: Identifier

    @field_validator('reviewer', 'review_id')
    @classmethod
    def nonblank_review(cls, value):
        if not value.strip():
            raise ValueError('Mapping review identity is required')
        return value
