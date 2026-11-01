"""Synthetic task registration uses persisted scope/oracle decisions, never caller flags."""
import json
from uuid import uuid4

from tests.integration.test_workflow import client as workflow_client, candidate, job

client = workflow_client


def registration(client, *, generated=False):
    p, revision = candidate(client)
    root = f"/api/v1/projects/{p['id']}"
    client.post(root + "/scope-decisions", json={"scope_digest": p["scope_digest"], "decision": "accept", "rationale": "Synthetic task-registration fixture only"})
    if generated:
        suite = job(client, p["id"], "test-generation", {"proposal_id": revision["id"], "revision": 1})
        accepted = client.post(root + "/test-oracle-decisions", json={"test_suite_id": suite["id"], "test_suite_digest": suite["digest"],
            "decision": "accept", "rationale": "Synthetic engineering oracle fixture, not study observations"})
        assert accepted.status_code == 201
        revision = accepted.json()
    request = {"proposal_id": revision["id"], "revision": revision["revision"], "bundle_digest": revision["bundle_digest"],
               "task_id": "synthetic-ownership", "instruction": "Preserve the source-backed ownership requirements"}
    response = client.post(root + "/synthetic-tasks", json=request)
    assert response.status_code == 201, response.text
    return p, revision, request, response.json()


def test_registration_requires_human_accepted_scope_and_unique_task_identity(client):
    p, revision = candidate(client)
    root = f"/api/v1/projects/{p['id']}"
    request = {"proposal_id": revision["id"], "revision": 1, "bundle_digest": revision["bundle_digest"],
               "task_id": "synthetic-example", "instruction": "Preserve the frozen synthetic task requirements"}
    assert client.post(root + "/synthetic-tasks", json=request).status_code == 409
    client.post(root + "/scope-decisions", json={"scope_digest": p["scope_digest"], "decision": "accept", "rationale": "Synthetic engineering test only"})
    assert client.post(root + "/synthetic-tasks", json=request, headers={"Authorization": "Bearer service-test-token"}).status_code == 403
    response = client.post(root + "/synthetic-tasks", json=request)
    assert response.status_code == 201, response.text
    assert client.post(root + "/synthetic-tasks", json=request).status_code == 409
    item = response.json()
    store = client.app.state.studio
    packet = json.loads(store.artifacts.get_verified(item["packet"]))
    assert packet["classification"] == "synthetic" and packet["split"] == "development"
    assert packet["questions"][0]["sparql_query"] == p["competency_questions"][0]["sparql_query"]
    assert client.get(root + "/synthetic-tasks").json()["items"][0]["registration_digest"] == item["registration_digest"]
    assert client.get(root).json()["approved_version_id"] is None


def test_registered_experiment_rejects_changed_digest_and_preserves_oracles_when_staging_d(client, monkeypatch):
    p, revision, request, registration_record = registration(client, generated=True)
    root, store = f"/api/v1/projects/{p['id']}", client.app.state.studio
    store.settings.model_url, store.settings.model_name = "http://localhost:11434", "fixture"
    monkeypatch.setattr("oe_studio.model.ModelClient.generate", lambda self, system, context, schema: (
        schema.model_validate({"summary": "Keep the supplied source-backed model", "changes": []}), {"provider": "fixture", "elapsed_seconds": 0.01}))
    monkeypatch.setattr("oe_studio.experiments.validate", lambda ttl, **kw: {
        "id": str(uuid4()), "status": "passed", "bundle_digest": kw["bundle_digest"], "cases": []})
    monkeypatch.setattr("oe_studio.experiments.assess", lambda ttl, **kw: {
        "id": str(uuid4()), "status": "completed", "bundle_digest": kw["bundle_digest"]})
    payload = {"registration_id": registration_record["id"], "registration_digest": "sha256:" + "0" * 64,
               "condition": "all", "replicate_ids": [1]}
    queued = client.post(root + "/synthetic-task-jobs", json=payload, headers={"Idempotency-Key": "bad-digest"})
    assert queued.status_code == 202, queued.text
    assert client.get(queued.json()["status_url"]).json()["status"] == "failed"
    payload["registration_digest"] = registration_record["registration_digest"]
    queued = client.post(root + "/synthetic-task-jobs", json=payload, headers={"Idempotency-Key": "registered-run"})
    assert queued.status_code == 202, queued.text
    completed = client.get(queued.json()["status_url"]).json()
    assert completed["status"] == "succeeded", completed
    runs = completed["result"]["runs"]
    assert {r["condition"] for r in runs} == {"A", "B", "C", "D"}
    assert {r["task_id"] for r in runs} == {"synthetic-ownership"}
    assert len({r["task_packet_digest"] for r in runs}) == 1
    d = next(r for r in runs if r["condition"] == "D")
    staged = client.post(root + f"/experiments/{d['id']}/proposal")
    assert staged.status_code == 201, staged.text
    with store.db.session() as session:
        original = store.revision(session, p["id"], revision["id"], revision["revision"])
        successor = store.revision(session, p["id"], staged.json()["id"], 1)
        assert store.artifacts.get_verified(successor.data["tests"]) == store.artifacts.get_verified(original.data["tests"])
    assert staged.json()["approval_ids"] == []
    assert client.get(root).json()["approved_version_id"] is None
