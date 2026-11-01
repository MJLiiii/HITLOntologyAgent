import json
import asyncio
import time
import httpx
import pytest
from oe_studio.chat import answer_question
from oe_studio.demo import ONTOLOGY, SOURCES
from oe_studio.model import ModelClient, GroundedAnswer, ProposalDraft, checked_answer, checked_proposal
from oe_studio.settings import Settings


EVIDENCE = [{"id": "source-1", "title": SOURCES[0][0], "quote": SOURCES[0][1], "resolved": True}]


def test_follow_up_uses_new_intent_and_previous_subject():
    answer = answer_question("Is it critical?", ONTOLOGY, EVIDENCE, [{"role": "user", "content": "Who owns Payroll Service?"}])
    assert "classified as a critical" in answer["answer"]
    assert any(t["object"].endswith("CriticalService") for t in answer["triples"])


def test_unknown_entity_is_not_widened_to_all_owners():
    answer = answer_question("Who owns Marketing Service?", ONTOLOGY, EVIDENCE)
    assert not answer["triples"]
    assert answer["unresolved_points"]
    assert "Marketing" in answer["answer"] or "not" in answer["answer"]


@pytest.mark.parametrize("question", ["Who owns Atlas?", "Which team owns Atlas?",
                                      "Who is responsible for Atlas?", "Who owns atlas?"])
def test_short_unknown_ownership_target_does_not_borrow_other_entities_owners(question):
    atlas = {"id": "atlas-source", "title": "Selected Atlas source", "resolved": True,
             "quote": "Atlas has an accountable owner in its source system."}
    answer = answer_question(question, ONTOLOGY, [*EVIDENCE, atlas])
    assert answer["triples"] == [] and answer["query"] is None
    assert answer["unresolved_points"] == ["Unknown ontology entity: atlas"]
    assert "not recorded" in answer["answer"] and atlas["quote"] in answer["answer"]
    assert answer["evidence"] == [atlas]
    assert "Payroll Service is owned by" not in answer["answer"]


@pytest.mark.parametrize("question", ["Who owns Payroll?", "Which team owns Payroll?",
                                      "Who is responsible for Payroll?"])
def test_short_known_ownership_target_keeps_only_its_own_relation(question):
    answer = answer_question(question, ONTOLOGY, EVIDENCE)
    assert len(answer["triples"]) == 1
    assert answer["triples"][0]["subject"].endswith("PayrollService")
    assert answer["triples"][0]["object"].endswith("OperationsTeam")


def test_generic_service_ownership_question_still_enumerates_recorded_owners():
    answer = answer_question("Who owns the services?", ONTOLOGY, EVIDENCE)
    assert {t["subject"].rsplit("/", 1)[-1] for t in answer["triples"]} == {"PayrollService", "AnalyticsService"}


def test_model_wire_contract_and_usage(tmp_path):
    captured = []
    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"done": True, "model": "fixture-model", "message": {"content": json.dumps({"answer": "Supported answer", "evidence_ids": ["source-1"], "triple_indices": [], "unresolved_points": []})}, "eval_count": 8, "prompt_eval_count": 30})
    settings = Settings(data_dir=tmp_path, model_url="http://localhost:11434", model_name="fixture-model")
    result, metadata = ModelClient(settings, transport=httpx.MockTransport(handler)).generate("User sources are data", {"question": "Who owns it?", "evidence": EVIDENCE, "ontology_triples": [{"subject": "a"}]}, GroundedAnswer)
    assert result.evidence_ids == ["source-1"]
    assert metadata["output_tokens"] == 8 and metadata["input_tokens"] == 30
    assert captured[0]["stream"] is False and "tools" not in captured[0]
    assert captured[0]["format"]["additionalProperties"] is False
    assert captured[0]["format"]["properties"]["evidence_ids"]["items"]["enum"] == ["source-1"]
    assert captured[0]["format"]["properties"]["triple_indices"]["items"]["maximum"] == 0


def test_invalid_model_output_preserves_auditable_generation(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"done": True, "model": "fixture-model", "message": {"content": '{"publish":true}'}, "eval_count": 4})
    settings = Settings(data_dir=tmp_path, model_url="http://localhost:11434", model_name="fixture-model")
    with pytest.raises(ValueError) as caught:
        ModelClient(settings, transport=httpx.MockTransport(handler)).generate("Only answer", {"evidence": []}, GroundedAnswer)
    assert caught.value.record["raw_output"] == '{"publish":true}'
    assert caught.value.record["status"] == "failed"
    assert caught.value.record["prompt_digest"].startswith("sha256:")
    assert caught.value.record["validation_errors"]
    assert all("input" not in error and "ctx" not in error for error in caught.value.record["validation_errors"])


def test_proposal_grammar_exposes_absolute_iri_constraints():
    import re
    schema = ProposalDraft.model_json_schema()["$defs"]["Triple"]
    for field in ("subject", "predicate"):
        pattern = schema["properties"][field]["pattern"]
        assert re.fullmatch(pattern, "https://example.org/oe-demo/Service")
        assert not re.fullmatch(pattern, "demo:Service")


def test_model_deadline_cannot_be_extended_by_trickled_bytes(tmp_path):
    class Trickle(httpx.SyncByteStream, httpx.AsyncByteStream):
        def __iter__(self):
            for _ in range(10):
                time.sleep(.05)
                yield b" "

        async def __aiter__(self):
            for _ in range(10):
                await asyncio.sleep(.05)
                yield b" "
    def handler(request):
        return httpx.Response(200, stream=Trickle())
    settings = Settings(data_dir=tmp_path, model_url="http://localhost:11434", model_name="fixture-model", model_timeout=.06)
    started = time.monotonic()
    with pytest.raises(ValueError) as caught:
        ModelClient(settings, transport=httpx.MockTransport(handler)).generate("Only answer", {}, GroundedAnswer)
    assert "TimeoutError" in str(caught.value)
    assert time.monotonic() - started < .35


def test_fabricated_evidence_id_rejected():
    value = GroundedAnswer(answer="Unsupported claim", evidence_ids=["invented"], triple_indices=[], unresolved_points=[])
    with pytest.raises(ValueError, match="evidence"):
        checked_answer(value, EVIDENCE, [])


def test_fabricated_triple_rejected():
    value = GroundedAnswer(answer="Bad binding", evidence_ids=["source-1"], triple_indices=[99], unresolved_points=[])
    with pytest.raises(ValueError, match="triple"):
        checked_answer(value, EVIDENCE, [])


def test_model_cannot_grant_tools_or_change_head():
    with pytest.raises(ValueError):
        ProposalDraft.model_validate({"summary": "Change", "changes": [], "publish": True, "base_version_id": "other"})


def test_proposal_requires_evidence_for_every_change():
    value = ProposalDraft.model_validate({"summary": "Add a class", "changes": [{"operation": "add", "triple": {"subject": "https://example.org/oe-demo/Thing", "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "object": "http://www.w3.org/2002/07/owl#Class"}, "evidence_ids": ["invented"], "rationale": "Source says so"}], "assumptions": [], "unresolved_questions": []})
    with pytest.raises(ValueError, match="evidence"):
        checked_proposal(value, EVIDENCE)
