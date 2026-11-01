"""Application ledger tests; the upstream wire/provenance boundary has separate contracts."""
import json
from uuid import uuid4

import pytest

from oe_studio.artifacts import digest
from tests.integration.test_workflow import client as workflow_client, project

client = workflow_client


def run(c, p, path, payload, key="provider-test"):
    response = c.post(f"/api/v1/projects/{p}/{path}", json=payload, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    return c.get(response.json()["status_url"]).json()


def test_unconfigured_provider_is_explicit_and_cannot_override_workspace(client):
    p = project(client)
    doc = client.get(f"/api/v1/projects/{p['id']}/documents").json()["items"][0]
    result = run(client, p["id"], "trustgraph-ingestions", {"document_id": doc["id"]})
    assert result["status"] == "failed" and "not configured" in result["error"]
    response = client.post(f"/api/v1/projects/{p['id']}/trustgraph-ingestions",
        json={"document_id": doc["id"], "workspace": "another-workspace"}, headers={"Idempotency-Key": "override"})
    assert response.status_code == 422


@pytest.fixture
def provider(client, monkeypatch, tmp_path):
    from oe_studio.integrations.trustgraph.contracts import Artifact, PreparedIngestion, IngestReceipt, ImportedChunk, ImportedSnapshot
    from oe_studio.integrations.trustgraph.gateway import PinnedTrustGraphGateway
    studio, p = client.app.state.studio, project(client)
    root = f"/api/v1/projects/{p['id']}"
    doc = client.post(root + "/documents", files={"file": ("atlas.txt", b"Atlas belongs to Platform.\r\n", "text/plain")},
                      data={"title": "Synthetic Atlas", "classification": "synthetic"}).json()
    config_path = tmp_path / "provider.json"
    config_path.write_text(json.dumps({"projects": [{"binding": {
        "project_id": p["id"], "url": "http://127.0.0.1:18888", "workspace": "isolated-synthetic",
        "flow": "graph", "collection": "fixture", "seed_digest": "0" * 64, "config_digest": "1" * 64,
        "token": "PRIVATE-TEST-TOKEN"}, "seed_mode": "ordinary", "expected_configuration": {}}]}))
    studio.settings.trustgraph_config_file = config_path
    def artifact(value, media="application/json"):
        return Artifact(**studio.artifacts.put(value if isinstance(value, bytes) else json.dumps(value).encode(), media))
    metadata = artifact({"synthetic_test": True})

    async def prepare(gateway, request, **kwargs):
        return PreparedIngestion(id=uuid4(), request=request,
            binding_digest=gateway._binding_digest(request.project_id), source=gateway._document(request.project_id, request.source_id),
            seed_mode="ordinary", approved_version_id=None, approved_ontology=None,
            configuration_artifact=metadata, configuration_version=1, manifest_artifact=metadata, manifest_digest=digest({"fixture": True}))

    async def ingest(gateway, prepared, **kwargs):
        # Verify the preparation was committed before an external side effect.
        with studio.db.session() as session:
            records = studio.items(session, p["id"], "trustgraph_preparation")
            assert len(records) == 1 and records[0].data["prepared"]["id"] == str(prepared.id)
        return IngestReceipt(ingestion_id=prepared.id, project_id=prepared.request.project_id,
            source_id=prepared.source.source_id, document_uri=prepared.source.upstream_document_id,
            processing_id="urn:test:processing", binding_digest=prepared.binding_digest,
            seed_digest=prepared.request.seed_digest, config_digest=prepared.request.config_digest,
            status="queued", raw_artifact=metadata)

    async def snapshot(gateway, prepared, receipt, *, chunk_uris, corpus_id):
        source = prepared.source.artifact
        quote = "Atlas belongs to Platform.\n"
        chunk = artifact(quote.encode(), "text/plain")
        return ImportedSnapshot(id=corpus_id, project_id=prepared.request.project_id, ingestion_id=prepared.id,
            source_artifact=source, configuration_artifact=metadata, provenance_artifact=metadata,
            chunks=(ImportedChunk(evidence_id=uuid4(), upstream_chunk_uri=chunk_uris[0], source_id=prepared.source.source_id,
                source_artifact=source, upstream_chunk_artifact=source, normalized_source_artifact=chunk,
                chunk_artifact=chunk, metadata_artifact=metadata, quote=quote, byte_start=0, byte_end=28,
                span_start=0, span_end=len(quote), subgraph_uris=("urn:test:subgraph",), extracted_triples=()),),
            manifest_artifact=metadata, manifest_digest=digest({"corpus_id": str(corpus_id)}))

    monkeypatch.setattr(PinnedTrustGraphGateway, "prepare_ingestion", prepare)
    monkeypatch.setattr(PinnedTrustGraphGateway, "ingest_prepared", ingest)
    monkeypatch.setattr(PinnedTrustGraphGateway, "import_snapshot", snapshot)
    return studio, p, doc, config_path


def test_selected_remote_snapshot_becomes_immutable_local_evidence(provider, client):
    studio, p, doc, config_path = provider
    receipt = run(client, p["id"], "trustgraph-ingestions", {"document_id": doc["id"]})
    assert receipt["status"] == "succeeded", receipt
    assert receipt["result"]["status"] == "queued"
    assert project(client)["corpus_snapshot_id"] == p["corpus_snapshot_id"]
    selected = run(client, p["id"], "trustgraph-snapshots", {
        "ingestion_run_id": receipt["result"]["id"], "chunk_uris": ["urn:test:chunk"]}, "snapshot")
    assert selected["status"] == "succeeded", selected
    corpus = selected["result"]
    assert corpus["provider"] == "trustgraph" and corpus["selection_kind"] == "explicit_registered_chunks"
    assert corpus["upstream_completion_supported"] is False
    evidence = client.get(f"/api/v1/projects/{p['id']}/corpus-evidence").json()["items"]
    assert len(evidence) == 1 and evidence[0]["resolved"]
    assert evidence[0]["quote"] == "Atlas belongs to Platform.\n"
    assert "PRIVATE-TEST-TOKEN" not in json.dumps([receipt, selected, evidence])
    config_path.unlink()  # Reading the frozen selection never depends on mutable upstream state.
    again = client.get(f"/api/v1/projects/{p['id']}/evidence/{evidence[0]['id']}").json()
    assert again["resolved"] and again["quote"] == evidence[0]["quote"]
    historical = run(client, p["id"], "question-jobs", {"question": "Which team owns the Atlas service?"}, "historical-question")
    assert historical["result"]["corpus_snapshot_id"] == p["corpus_snapshot_id"]
    explicit = run(client, p["id"], "question-jobs", {
        "question": "Which team owns the Atlas service?", "corpus_snapshot_id": corpus["id"]}, "selected-question")
    assert explicit["status"] == "succeeded", explicit
    answer = explicit["result"]
    assert answer["source_selection"] == "explicit" and answer["corpus_snapshot_id"] == corpus["id"]
    assert answer["evidence"][0]["quote"] == "Atlas belongs to Platform.\n"
    assert any("ontology version" in text.lower() for text in answer["limitations"])
    other = client.post("/api/v1/projects", json={"name": "Question isolation", "domain": "demo"}).json()
    denied = run(client, other["id"], "question-jobs", {
        "question": "Who owns Atlas?", "corpus_snapshot_id": corpus["id"]}, "foreign-corpus")
    assert denied["status"] == "failed"
    assert project(client)["approved_version_id"] is None
    client.post(f"/api/v1/projects/{p['id']}/documents/{doc['id']}/withdrawal", json={"rationale": "Synthetic source withdrawn"})
    with studio.db.session() as session:
        assert not studio.evidence(session, p["id"], evidence[0]["id"])["resolved"]


def test_remote_source_cannot_cross_project_and_seed_must_be_approved(provider, client):
    studio, p, doc, config_path = provider
    other = client.post("/api/v1/projects", json={"name": "Other synthetic project", "domain": "demo"}).json()
    denied = client.post(f"/api/v1/projects/{other['id']}/trustgraph-ingestions",
        json={"document_id": doc["id"]}, headers={"Idempotency-Key": "wrong-project"})
    assert denied.status_code == 403 and denied.json()["code"] == "trustgraph_project_denied"
    data = json.loads(config_path.read_text())
    data["projects"][0]["seed_mode"] = "approved_ontology"
    config_path.write_text(json.dumps(data))
    result = run(client, p["id"], "trustgraph-ingestions", {"document_id": doc["id"]}, "unapproved-seed")
    assert result["status"] == "failed" and "approved" in result["error"]
    with studio.db.session() as session:
        assert not studio.items(session, p["id"], "trustgraph_preparation")


def test_expired_worker_cannot_submit_remote_ingestion(provider, client, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from oe_studio.db import Job
    from oe_studio.integrations.trustgraph.gateway import PinnedTrustGraphGateway
    studio, p, doc, _ = provider
    prepare = PinnedTrustGraphGateway.prepare_ingestion
    async def expired(gateway, request, **kwargs):
        result = await prepare(gateway, request, **kwargs)
        with studio.db.session(write=True) as session:
            session.get(Job, request.idempotency_key).lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        return result
    monkeypatch.setattr(PinnedTrustGraphGateway, "prepare_ingestion", expired)
    result = run(client, p["id"], "trustgraph-ingestions", {"document_id": doc["id"]})
    assert result["status"] == "failed" and "lease" in result["error"]
    with studio.db.session() as session:
        assert not studio.items(session, p["id"], "trustgraph_preparation"), "Expired worker must stop before starting an external submission"


def test_lost_submission_reply_can_only_reconcile_the_prepared_attempt(provider, client, monkeypatch):
    from oe_studio.integrations.trustgraph.gateway import PinnedTrustGraphGateway
    from tests.integration.test_job_recovery import ACTOR, ProcessLost
    studio, p, doc, _ = provider
    original = PinnedTrustGraphGateway.ingest_prepared
    async def lost(gateway, prepared, **kwargs):
        await original(gateway, prepared, **kwargs)
        raise ProcessLost()
    studio.settings.eager_jobs = False
    handle = studio.create_job(p["id"], "trustgraph-ingestion", {"document_id": doc["id"]}, "lost-reply", ACTOR)
    monkeypatch.setattr(PinnedTrustGraphGateway, "ingest_prepared", lost)
    with pytest.raises(ProcessLost):
        studio.execute_job(handle["job_id"])
    with studio.db.session() as session:
        preparations = studio.items(session, p["id"], "trustgraph_preparation")
        assert len(preparations) == 1
        preparation_id = preparations[0].id
        assert not studio.items(session, p["id"], "trustgraph_ingestion")
    async def recover(gateway, prepared, **kwargs):
        assert kwargs["may_have_submitted"] is True, "A lost reply must never trigger a fresh submission"
        return await original(gateway, prepared, **kwargs)
    monkeypatch.setattr(PinnedTrustGraphGateway, "ingest_prepared", recover)
    studio.settings.eager_jobs = True
    result = run(client, p["id"], "trustgraph-ingestion-recoveries", {"preparation_id": preparation_id}, "recover-reply")
    assert result["status"] == "succeeded", result
    assert result["result"]["preparation_id"] == preparation_id
    with studio.db.session() as session:
        assert len(studio.items(session, p["id"], "trustgraph_ingestion")) == 1
        assert len(studio.items(session, p["id"], "trustgraph_preparation")) == 1


def test_remote_operation_has_a_total_deadline_and_keeps_its_preparation(provider, client, monkeypatch):
    import asyncio
    from oe_studio.integrations.trustgraph.gateway import PinnedTrustGraphGateway
    studio, p, doc, _ = provider
    async def stalled(*args, **kwargs):
        await asyncio.sleep(60)
    monkeypatch.setattr(PinnedTrustGraphGateway, "ingest_prepared", stalled)
    monkeypatch.setattr("oe_studio.trustgraph_workflow.REMOTE_DEADLINE_SECONDS", 0.01)
    result = run(client, p["id"], "trustgraph-ingestions", {"document_id": doc["id"]})
    assert result["status"] == "failed" and "deadline" in result["error"]
    with studio.db.session() as session:
        assert len(studio.items(session, p["id"], "trustgraph_preparation")) == 1
        assert not studio.items(session, p["id"], "trustgraph_ingestion")
