"""Real isolated engines through the HTTP workflow; approval is never simulated in app data."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from oe_studio.main import create_app
from oe_studio.settings import Settings
from oe_studio.rdf import NS


@pytest.fixture
def real_client(tmp_path):
    app = create_app(Settings(_env_file=None, llm_config_file=None, data_dir=tmp_path, eager_jobs=True))
    with TestClient(app) as client:
        client.get("/api/v1/session", headers={"X-OE-Session-Token": app.state.bootstrap_token})
        yield client


def job(client, root, kind, payload):
    queued = client.post(root + f"/{kind}-jobs", json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert queued.status_code == 202, queued.text
    result = client.get("/api/v1/jobs/" + queued.json()["job_id"]).json()
    assert result["status"] == "succeeded", result
    return result["result"]


def candidate(client):
    p = client.get("/api/v1/projects").json()["items"][0]
    root = f"/api/v1/projects/{p['id']}"
    r = job(client, root, "proposal", {"base_version_id": None, "corpus_snapshot_id": p["corpus_snapshot_id"], "instruction": "Create a synthetic candidate"})
    return p, root, r


def test_real_engine_failure_then_corrected_successor_preserves_reference(real_client):
    c = real_client
    p, root, r = candidate(c)
    reference = c.get(root + "/versions").json()["items"][0]
    original = c.get(root + "/versions/" + reference["id"]).json()["ttl"]
    inference = [{"subject": NS + "CriticalService", "predicate": "http://www.w3.org/2000/01/rdf-schema#subClassOf", "object": NS + "Service"},
                 {"subject": NS + "hasOwner", "predicate": "http://www.w3.org/2000/01/rdf-schema#domain", "object": NS + "Service"}]
    broken = c.post(root + f"/proposals/{r['proposal_id']}/revisions", json={"parent_revision": 1, "structured_changes": {"deletions": inference}, "rationale": "Remove both service inference paths to exercise the competency question"}, headers={"If-Match": "1"}).json()
    request = {"proposal_id": r["proposal_id"], "revision": 2, "bundle_digest": broken["bundle_digest"]}
    failed = job(c, root, "validation", request)
    assert failed["status"] == "failed", failed
    repaired = c.post(root + f"/proposals/{r['proposal_id']}/revisions", json={"parent_revision": 2, "structured_changes": {"additions": inference}, "rationale": "Restore the source-supported service inference relationships"}, headers={"If-Match": "2"}).json()
    request.update(revision=3, bundle_digest=repaired["bundle_digest"])
    assert job(c, root, "validation", request)["status"] == "passed"
    assert job(c, root, "assessment", request)["status"] == "completed"
    assert c.get(root + "/validation-runs/" + failed["id"]).json()["status"] == "failed"
    assert c.get(root + "/versions/" + reference["id"]).json()["ttl"] == original
    assert c.get(root).json()["approved_version_id"] is None


def test_unsupported_construct_blocks_publication(real_client):
    c = real_client
    p, root, r = candidate(c)
    bad = c.post(root + f"/proposals/{r['proposal_id']}/revisions", json={"parent_revision": 1, "structured_changes": {"additions": [{"subject": NS + "Service", "predicate": "http://www.w3.org/2002/07/owl#equivalentClass", "object": NS + "Team"}]}, "rationale": "Deliberate unsupported OWL construct test"}, headers={"If-Match": "1"}).json()
    request = {"proposal_id": r["proposal_id"], "revision": 2, "bundle_digest": bad["bundle_digest"]}
    report = job(c, root, "validation", request)
    assert report["status"] == "unsupported", report
    c.post(root + "/scope-decisions", json={"scope_digest": p["scope_digest"], "decision": "accept", "rationale": "Isolated synthetic test scope"})
    submit = c.post(root + "/review-submissions", json={"proposal_id": r["proposal_id"], "revision": 2, "validation_run_id": report["id"], "required_assessment_run_ids": []}, headers={"If-Match": "2"})
    assert submit.status_code == 409 and "validation" in submit.text.lower()
    publication = c.post(root + "/publications", json={**request, "approval_ids": [], "expected_head": None}, headers={"Idempotency-Key": str(uuid4())})
    assert publication.status_code in {409, 422}
    assert c.get(root).json()["approved_version_id"] is None


def test_actual_pdf_without_text_remains_incomplete_in_http_workflow(real_client):
    import io
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    source = io.BytesIO()
    writer.write(source)
    c = real_client
    p = c.get("/api/v1/projects").json()["items"][0]
    root = f"/api/v1/projects/{p['id']}"
    doc = c.post(root + "/documents", files={"file": ("blank.pdf", source.getvalue(), "application/pdf")}, data={"title": "No text layer"})
    assert doc.status_code == 201, doc.text
    queued = c.post(root + "/ingestions", json={"document_id": doc.json()["id"]}, headers={"Idempotency-Key": str(uuid4())}).json()
    result = c.get("/api/v1/jobs/" + queued["job_id"]).json()["result"]
    assert result["status"] == "incomplete", result
    assert all(isinstance(d, str) for d in result["extraction"]["diagnostics"])
    assert c.post(root + "/corpus-snapshots", json={"ingestion_run_ids": [result["ingestion_run_id"]]}).status_code == 409
