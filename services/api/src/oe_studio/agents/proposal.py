"""Proposal generation boundary shared by initial proposals and constrained repairs."""
from typing import Literal
from pydantic import ConfigDict, Field, StrictBool, model_validator
from ..schemas import ChangeSet, StrictModel, Triple


class GeneratedChange(StrictModel):
    operation: Literal["add", "delete"]
    triple: Triple
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    rationale: str = Field(min_length=5, max_length=2000)


class ProposalDraft(StrictModel):
    summary: str = Field(min_length=5, max_length=1000)
    changes: list[GeneratedChange] = Field(min_length=1, max_length=100)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=20)


def checked_proposal(value: ProposalDraft, evidence):
    allowed = {e["id"] for e in evidence if e["resolved"]}
    if any(not set(change.evidence_ids) <= allowed for change in value.changes):
        raise ValueError("Proposal contains evidence outside the frozen context")
    if value.unresolved_questions:
        raise ValueError("Proposal has unresolved modelling questions: " + "; ".join(value.unresolved_questions))
    return ChangeSet(additions=[c.triple for c in value.changes if c.operation == "add"],
                     deletions=[c.triple for c in value.changes if c.operation == "delete"])


class FailedEntailmentCase(StrictModel):
    """Only failed frozen ASK diagnostics; caller selects authorized question IDs."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    id: str = Field(min_length=1, max_length=200)
    status: Literal['failed']
    expected: StrictBool
    actual: StrictBool
    message: str | None = None

    @model_validator(mode='after')
    def named_case(self):
        if not self.id.strip():
            raise ValueError('Failed entailment case requires a question identity')
        return self


class ProposalContext(StrictModel):
    """Named frozen inputs, without workflow authority or additional feedback."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    evidence: list[dict]
    ontology: str = ''
    namespace: str | None = None
    instruction: str | None = None
    competency_questions: list[dict] | None = None
    frozen_inputs: dict | None = None
    corpus_snapshot_id: str | None = None
    retrieval: dict | None = None
    failed_entailment_cases: list[FailedEntailmentCase] | None = None
    remaining_attempts: int | None = Field(default=None, ge=0)

    @model_validator(mode='after')
    def development_only(self):
        if any(question.get('split', 'development') != 'development'
               for question in self.competency_questions or []):
            raise ValueError('Proposal context admits development questions only')
        return self


class ProposalAgentInput(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    version: Literal['proposal-agent-v1'] = 'proposal-agent-v1'
    operation: Literal['proposal', 'repair'] = 'proposal'
    system_prompt: str
    context: ProposalContext

    @model_validator(mode='after')
    def operation_feedback(self):
        feedback_fields = {'failed_entailment_cases', 'remaining_attempts'}
        if self.operation == 'proposal' and self.context.model_fields_set & feedback_fields:
            raise ValueError('Initial proposal generation cannot receive repair feedback')
        if self.operation == 'repair' and not self.context.failed_entailment_cases:
            raise ValueError('Repair generation requires failed entailment diagnostics')
        return self


class ProposalAgentOutput(StrictModel):
    version: Literal['proposal-agent-v1'] = 'proposal-agent-v1'
    draft: ProposalDraft
    changes: ChangeSet
    generation_record: dict


class ProposalAgent:
    def __init__(self, client):
        self.client = client

    def run(self, inputs: ProposalAgentInput):
        from ..model import ModelGenerationError
        context = inputs.context.model_dump(exclude_unset=True)
        draft, record = self.client.generate(inputs.system_prompt, context, ProposalDraft)
        try:
            changes = checked_proposal(draft, context['evidence'])
        except ValueError as error:
            raise ModelGenerationError(str(error), {**record, 'status': 'failed',
                                       'output': draft.model_dump(), 'error': str(error)}) from error
        return ProposalAgentOutput(draft=draft, changes=changes, generation_record=record)
