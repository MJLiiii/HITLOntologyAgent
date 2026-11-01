"""Optional local Ollama generation. Model output has no tool or publication capability."""
import json
import asyncio
import time
import httpx
from pydantic import Field, ValidationError
from .artifacts import digest
from .schemas import ChangeSet, StrictModel, Triple
from typing import Literal


class GroundedAnswer(StrictModel):
    answer: str = Field(min_length=1, max_length=8000)
    evidence_ids: list[str] = Field(max_length=20)
    triple_indices: list[int] = Field(max_length=100)
    unresolved_points: list[str] = Field(default_factory=list, max_length=20)


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


class ModelGenerationError(ValueError):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


class ModelClient:
    def __init__(self, settings, transport=None):
        self.settings, self.transport = settings, transport

    async def _request(self, payload, headers):
        async with httpx.AsyncClient(timeout=self.settings.model_timeout, transport=self.transport, follow_redirects=False) as client:
            async with client.stream("POST", self.settings.model_url.rstrip("/") + "/api/chat", json=payload, headers=headers) as response:
                response.raise_for_status()
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > 1_048_576:
                        raise ValueError("Model response exceeded the output bound")
                    chunks.append(chunk)
                return json.loads(b"".join(chunks))

    async def _bounded_request(self, payload, headers):
        return await asyncio.wait_for(self._request(payload, headers), timeout=self.settings.model_timeout)

    def generate(self, system, context, schema):
        if not self.settings.model_url or not self.settings.model_name:
            raise ValueError("No language model configured")
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
        payload = {"model": self.settings.model_name, "stream": False, "think": False,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
                   "format": output_schema, "options": {"temperature": 0, "num_predict": 4096}}
        headers = {"Authorization": "Bearer " + self.settings.model_api_key} if self.settings.model_api_key else {}
        started = time.monotonic()
        raw = {}
        metadata = {"provider": "ollama", "model": self.settings.model_name, "prompt_digest": digest(payload),
                    "system_prompt": system, "temperature": 0, "seed": None, "cost": None,
                    "cost_missing_reason": "Provider did not report cost"}
        try:
            raw = asyncio.run(self._bounded_request(payload, headers))
            if raw.get("done") is not True:
                raise ValueError("Model response was incomplete")
            parsed = schema.model_validate_json(raw["message"]["content"])
        except (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError, TimeoutError) as exc:
            message = "Configured model unavailable or returned an invalid response: " + type(exc).__name__
            response_message = raw.get("message") if isinstance(raw, dict) else None
            raise ModelGenerationError(message, {**metadata, "status": "failed", "error": message,
                                       "validation_errors": exc.errors(include_input=False, include_context=False, include_url=False) if isinstance(exc, ValidationError) else [],
                                       "raw_output": response_message.get("content") if isinstance(response_message, dict) else None,
                                       "input_tokens": raw.get("prompt_eval_count") if isinstance(raw, dict) else None,
                                       "output_tokens": raw.get("eval_count") if isinstance(raw, dict) else None,
                                       "elapsed_seconds": time.monotonic() - started}) from exc
        return parsed, {**metadata, "returned_model": raw.get("model"), "output_digest": digest(parsed.model_dump()),
                        "raw_output": raw["message"]["content"], "input_tokens": raw.get("prompt_eval_count"),
                        "output_tokens": raw.get("eval_count"), "elapsed_seconds": time.monotonic() - started}


def checked_answer(value: GroundedAnswer, evidence, triples):
    allowed = {e["id"]: e for e in evidence if e["resolved"]}
    if any(i not in allowed for i in value.evidence_ids) or (not value.evidence_ids and not value.unresolved_points):
        raise ValueError("Model answer has missing or fabricated evidence")
    if any(type(i) is not int or i < 0 or i >= len(triples) for i in value.triple_indices):
        raise ValueError("Model answer has fabricated triple references")
    return {"answer": value.answer, "evidence": [allowed[i] for i in dict.fromkeys(value.evidence_ids)],
            "triples": [triples[i] for i in dict.fromkeys(value.triple_indices)], "unresolved_points": value.unresolved_points,
            "mode": "model", "limitations": ["AI explanation based on the cited evidence; citation validity does not establish semantic correctness."]}


def checked_proposal(value: ProposalDraft, evidence):
    allowed = {e["id"] for e in evidence if e["resolved"]}
    if any(not set(change.evidence_ids) <= allowed for change in value.changes):
        raise ValueError("Proposal contains evidence outside the frozen context")
    if value.unresolved_questions:
        raise ValueError("Proposal has unresolved modelling questions: " + "; ".join(value.unresolved_questions))
    return ChangeSet(additions=[c.triple for c in value.changes if c.operation == "add"],
                     deletions=[c.triple for c in value.changes if c.operation == "delete"])
