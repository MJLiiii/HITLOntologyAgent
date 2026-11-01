"""Response changes must keep scripted outcomes and historical demo data readable."""
import json
import hashlib
from uuid import uuid4

from oe_studio import demo, experiments
from oe_studio.artifacts import canonical_json
from tests.integration.test_workflow import client as workflow_client, project

client = workflow_client


def demo_engine_doubles(monkeypatch):
    monkeypatch.setattr(experiments, "validate", lambda *args, **kwargs: {
        "id": str(uuid4()), "status": "failed", "cases": [
            {"id": "CQ-01", "status": "failed", "expected": True, "actual": False}],
    })
    monkeypatch.setattr(experiments, "assess", lambda *args, **kwargs: {
        "id": str(uuid4()), "status": "completed",
    })


def test_scripted_demo_failed_evaluation_is_a_successfully_recorded_job(client, monkeypatch):
    demo_engine_doubles(monkeypatch)
    p = project(client)
    root = f"/api/v1/projects/{p['id']}"
    queued = client.post(root + "/experiment-jobs", json={"protocol_id": "demo-v1", "condition": "A"},
                         headers={"Idempotency-Key": str(uuid4())})
    assert queued.status_code == 202, queued.text
    result = client.get(queued.json()["status_url"]).json()
    assert result["status"] == "succeeded", result
    run = result["result"]["runs"][0]
    assert run["status"] == run["evaluation_status"] == "failed"
    listed = client.get(root + "/experiments")
    exported = client.get(root + "/experiments/export", params={"format": "json"})
    assert listed.status_code == exported.status_code == 200
    assert listed.json()["items"][0]["id"] == run["id"]
    payload = exported.json()
    frozen = payload["items"][0]
    assert "record_digest" not in frozen  # The scripted protocol uses its immutable artifact hash.
    assert hashlib.sha256(canonical_json(frozen)).hexdigest() == payload["provenance"][run["id"]]["sealed_record"]["sha256"]
    assert frozen["validation"]["cases"][0]["actual"] is False


def test_historical_demo_without_record_digest_remains_readable_without_rewriting_artifact(client, monkeypatch):
    demo_engine_doubles(monkeypatch)
    p, studio = project(client), client.app.state.studio
    legacy = experiments.execute_demo(demo.ONTOLOGY, bundle_digest="a" * 64, condition="A")[0]
    legacy.pop("record_digest", None)  # Actual pre-response-contract demo-v1 format.
    ref = studio.artifacts.put(canonical_json(legacy), "application/json")
    context = {"base_version_id": None, "corpus_snapshot_id": p["corpus_snapshot_id"],
               "scope_digest": p["scope_digest"], "evidence_ids": [], "engine_configuration": {}}
    with studio.db.session(write=True) as session:
        studio.add(session, p["id"], "experiment", {**legacy, "sealed_record": ref,
                   "project_context": context}, legacy["status"], legacy["id"])
    original = studio.artifacts.get_verified(ref)
    root = f"/api/v1/projects/{p['id']}"
    listed = client.get(root + "/experiments")
    exported = client.get(root + "/experiments/export", params={"format": "json"})
    assert listed.status_code == exported.status_code == 200, (listed.text, exported.text)
    assert listed.json()["items"][0]["id"] == legacy["id"]
    published = exported.json()["items"][0]
    assert canonical_json(published) == original
    assert hashlib.sha256(canonical_json(published)).hexdigest() == ref["sha256"]
    assert exported.json()["provenance"][legacy["id"]]["sealed_record"] == ref
    assert studio.artifacts.get_verified(ref) == original
    assert "record_digest" not in json.loads(original)
