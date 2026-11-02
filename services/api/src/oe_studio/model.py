"""Schema-validated generation. Model output has no tool or publication capability."""
import asyncio
import time
from pydantic import Field, ValidationError
from .artifacts import digest
from .llm_runtime import complete, CompletionError
from .schemas import StrictModel
from .agents.proposal import (
    GeneratedChange as GeneratedChange, ProposalDraft as ProposalDraft, checked_proposal as checked_proposal,
)


class GroundedAnswer(StrictModel):
    answer: str = Field(min_length=1, max_length=8000)
    evidence_ids: list[str] = Field(max_length=20)
    triple_indices: list[int] = Field(max_length=100)
    unresolved_points: list[str] = Field(default_factory=list, max_length=20)


class ModelGenerationError(ValueError):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


class ModelClient:
    def __init__(self, settings, transport=None):
        self.settings, self.transport = settings, transport

    def generate(self, system, context, schema):
        output_schema = schema.model_json_schema()
        evidence_ids = [item["id"] for item in context.get("evidence", []) if item.get("resolved")]
        references = [output_schema.get("properties", {}).get("evidence_ids")]
        references.extend(definition.get("properties", {}).get("evidence_ids")
                          for definition in output_schema.get("$defs", {}).values())
        for reference in references:
            if reference is not None:
                if evidence_ids:
                    reference["items"]["enum"] = evidence_ids
                else:
                    reference["maxItems"] = 0
        triple_indices = output_schema.get("properties", {}).get("triple_indices")
        if triple_indices is not None:
            if context.get("ontology_triples"):
                triple_indices["items"].update(minimum=0, maximum=len(context["ontology_triples"]) - 1)
            else:
                triple_indices["maxItems"] = 0
        started = time.monotonic()
        metadata = {}
        try:
            text, metadata = asyncio.run(complete(self.settings, system, context, output_schema,
                                                  transport=self.transport))
            parsed = schema.model_validate_json(text)
        except CompletionError as exc:
            raise ModelGenerationError(str(exc), exc.record) from None
        except (ValueError, TypeError, AttributeError) as exc:
            message = "Configured model unavailable or returned an invalid response: " + type(exc).__name__
            raise ModelGenerationError(message, {**metadata, "status": "failed", "error": message,
                                       "validation_errors": exc.errors(include_input=False, include_context=False, include_url=False) if isinstance(exc, ValidationError) else [],
                                       "elapsed_seconds": time.monotonic() - started}) from None
        return parsed, {**metadata, "output_digest": digest(parsed.model_dump()),
                        "elapsed_seconds": time.monotonic() - started}



def checked_answer(value: GroundedAnswer, evidence, triples):
    allowed = {e["id"]: e for e in evidence if e["resolved"]}
    if any(i not in allowed for i in value.evidence_ids) or (not value.evidence_ids and not value.unresolved_points):
        raise ValueError("Model answer has missing or fabricated evidence")
    if any(type(i) is not int or i < 0 or i >= len(triples) for i in value.triple_indices):
        raise ValueError("Model answer has fabricated triple references")
    return {"answer": value.answer, "evidence": [allowed[i] for i in dict.fromkeys(value.evidence_ids)],
            "triples": [triples[i] for i in dict.fromkeys(value.triple_indices)], "unresolved_points": value.unresolved_points,
            "mode": "model", "limitations": ["AI explanation based on the cited evidence; citation validity does not establish semantic correctness."]}
