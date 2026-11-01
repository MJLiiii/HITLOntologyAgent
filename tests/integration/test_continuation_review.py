"""Independent regressions for the continuation review's provenance boundaries."""
import asyncio
import copy
from uuid import UUID

import pytest

from oe_studio.integrations.trustgraph.gateway import GatewayError
from oe_studio.integrations.trustgraph.imports import configuration_digest
from tests.contracts.test_trustgraph_imports import context as gateway_context, populated
from tests.integration.test_job_recovery import ACTOR, store as workflow_store

context = gateway_context
store = workflow_store


def configure(context, cfg, *, idempotency_key):
    gateway, request, approved, _, _ = context
    config_hash = configuration_digest(cfg)
    gateway.configuration = copy.deepcopy(cfg)
    gateway.bindings[request.project_id] = gateway.bindings[request.project_id].model_copy(
        update={"config_digest": config_hash})
    request = request.model_copy(update={"config_digest": config_hash, "idempotency_key": idempotency_key})
    return asyncio.run(gateway.prepare_ingestion(request, approved_version_id=UUID(int=92),
        approved_ontology=approved, expected_configuration=cfg))


def test_new_ingestion_cannot_claim_old_extraction_under_new_configuration(context):
    gateway, original, _, old_chunk = populated(context)
    cfg = copy.deepcopy(context[3])
    cfg["prompt"]["template.extract-with-ontologies"]["prompt"] = "A different extraction policy"
    gateway.configuration_version += 1
    prepared = configure(context, cfg, idempotency_key="new-extraction-policy")
    receipt = asyncio.run(gateway.ingest_prepared(prepared))
    assert prepared.id != original.id
    assert prepared.configuration_artifact != original.configuration_artifact
    # The new processing is queued; every chunk/activity/fact is still from the old run.
    with pytest.raises(GatewayError):
        asyncio.run(gateway.import_snapshot(prepared, receipt, chunk_uris=(old_chunk,), corpus_id=UUID(int=94)))


@pytest.mark.parametrize("location", ["flow", "nested_processor"])
def test_private_configuration_cannot_enter_public_artifacts(context, location):
    cfg = copy.deepcopy(context[3])
    if location == "flow":
        cfg["flow"]["frozen-flow"]["parameters"]["api_key"] = "synthetic-private-review-marker"
    else:
        cfg["processor:kg-extract-ontology"]["frozen-flow"]["parameters"]["auth"] = {
            "api_key": "synthetic-private-review-marker"}
    with pytest.raises(GatewayError):
        configure(context, cfg, idempotency_key="private-configuration")


def test_configuration_cannot_omit_the_active_extraction_prompt(context):
    gateway, request, approved, original, _ = context
    selected = copy.deepcopy(original)
    selected["prompt"] = {"unused-review-template": {"prompt": "Unrelated retained prompt"}}
    gateway.configuration["prompt"].update(selected["prompt"])
    config_hash = configuration_digest(selected)
    gateway.bindings[request.project_id] = gateway.bindings[request.project_id].model_copy(
        update={"config_digest": config_hash})
    request = request.model_copy(update={"config_digest": config_hash})
    # The remote active ontology extraction template exists but is absent from the seal.
    with pytest.raises(GatewayError):
        asyncio.run(gateway.prepare_ingestion(request, approved_version_id=UUID(int=92),
            approved_ontology=approved, expected_configuration=selected))


def test_generated_regression_preserves_question_literal_semantics(store):
    from rdflib import Graph
    from oe_studio.demo import ONTOLOGY
    from oe_studio.schemas import ScopeUpload

    studio, project = store
    fixture = '<https://example.org/oe-demo/Service> <http://www.w3.org/2000/01/rdf-schema#label> "demo:service" .'
    query = 'ASK { ' + fixture + ' }'
    studio.upload_scope(project.id, ScopeUpload(title="Literal regression", purpose="Preserve exact quoted values",
        competency_questions=[{"id": "literal-question", "question": "Is the literal label preserved?",
            "sparql_query": query, "expected": True}], fixtures_ttl=fixture), ACTOR)
    proposal = studio.seed_import(project.id, {"ontology_ttl": ONTOLOGY, "rationale": "Synthetic review fixture",
        "corpus_snapshot_id": project.corpus_snapshot_id}, ACTOR)
    suite = studio.generate_tests(project.id, {"proposal_id": proposal["proposal_id"], "revision": 1}, ACTOR)
    case = next(case for case in suite["tests"] if case["scenario"] == "regression")
    graph = Graph().parse(data=ONTOLOGY + '\n' + fixture, format="turtle")
    assert bool(graph.query(query)) is True
    assert bool(graph.query(case["query"])) is case["expected"], "A generated regression must preserve frozen query semantics"
