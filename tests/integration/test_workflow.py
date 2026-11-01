from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from oe_studio.main import create_app
from oe_studio.settings import Settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    # External engines are covered by their own real-process contract tests.
    monkeypatch.setattr("oe_studio.workflow.run_validation", lambda ttl, **kw: {
        "id": str(uuid4()), "status": "passed", "bundle_digest": kw["bundle_digest"],
        "engine": "fixture", "profile": "rdfs", "cases": [], "stages": [], "limitations": []})
    monkeypatch.setattr("oe_studio.workflow.run_assessment", lambda ttl, **kw: {
        "id": str(uuid4()), "status": "completed", "bundle_digest": kw["bundle_digest"],
        "vocabulary_coverage": 1, "vocabulary_utilisation": .5, "strict_fitness": 1,
        "approximate_fitness": 1, "limitations": []})
    app = create_app(Settings(data_dir=tmp_path, eager_jobs=True, service_token="service-test-token"))
    with TestClient(app) as c:
        assert c.get("/api/v1/session", headers={"X-OE-Session-Token": app.state.bootstrap_token}).status_code == 200
        yield c


def project(c):
    return c.get("/api/v1/projects").json()["items"][0]


def job(c, p, kind, payload):
    r = c.post(f"/api/v1/projects/{p}/{kind}-jobs", json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert r.status_code == 202, r.text
    data = c.get(f"/api/v1/jobs/{r.json()['job_id']}").json()
    assert data["status"] == "succeeded", data
    return data["result"]


def candidate(c):
    p = project(c)
    result = job(c, p["id"], "proposal", {"base_version_id": p["approved_version_id"],
                 "corpus_snapshot_id": p["corpus_snapshot_id"], "instruction": "Create seed ontology"})
    rev = c.get(f"/api/v1/projects/{p['id']}/proposals/{result['proposal_id']}/revisions/1").json()
    return p, rev


def checked(c):
    p, r = candidate(c)
    payload = {"proposal_id": r["id"], "revision": 1, "bundle_digest": r["bundle_digest"]}
    v = job(c, p["id"], "validation", payload)
    a = job(c, p["id"], "assessment", payload)
    return p, r, v, a


def accept(c):
    p, r, v, a = checked(c)
    root = f"/api/v1/projects/{p['id']}"
    assert c.post(root + "/scope-decisions", json={"scope_digest": p["scope_digest"], "decision": "accept", "rationale": "Synthetic demo only"}).status_code == 201
    submission = {"proposal_id": r["id"], "revision": 1, "validation_run_id": v["id"], "required_assessment_run_ids": [a["id"]]}
    assert c.post(root + "/review-submissions", json=submission, headers={"If-Match": "1"}).status_code == 201
    review = c.post(root + "/reviews", json={**submission, "bundle_digest": r["bundle_digest"], "decision": "accept", "rationale": "Reviewed exact evidence and checks", "review_policy_id": p["review_policy_id"]})
    assert review.status_code == 201, review.text
    pub = {"proposal_id": r["id"], "revision": 1, "bundle_digest": r["bundle_digest"], "approval_ids": [review.json()["id"]], "expected_head": None}
    return p, r, pub


def test_demo_does_not_start_with_automatic_approval(client):
    p = project(client)
    assert p["approved_version_id"] is None
    assert not p["scope_accepted"]
    assert client.get(f"/api/v1/projects/{p['id']}/versions").json()["items"][0]["status"] == "reference"


def test_review_list_includes_non_acceptance_and_is_revision_scoped(client):
    p, r, v, a = checked(client)
    root = f"/api/v1/projects/{p['id']}"
    client.post(root + "/scope-decisions", json={"scope_digest": p["scope_digest"], "decision": "accept", "rationale": "Synthetic test only"})
    submission = {"proposal_id": r["id"], "revision": 1, "validation_run_id": v["id"], "required_assessment_run_ids": [a["id"]]}
    assert client.post(root + "/review-submissions", json=submission, headers={"If-Match": "1"}).status_code == 201
    decision = client.post(root + "/reviews", json={**submission, "bundle_digest": r["bundle_digest"], "decision": "request_changes", "rationale": "Source interpretation needs another check", "review_policy_id": p["review_policy_id"]})
    assert decision.status_code == 201, decision.text
    response = client.get(root + "/reviews", params={"revision_id": r["revision_id"], "limit": 1})
    assert response.status_code == 200, response.text
    records = response.json()
    assert records["items"] == [decision.json()]
    assert records["next_cursor"] is None
    assert client.get(root + "/reviews", params={"revision_id": str(uuid4())}).status_code == 404


def test_corpus_listing_and_chat_retrieve_beyond_twenty_chunks(client):
    p = client.post("/api/v1/projects", json={"name": "Long source fixture", "domain": "demo"}).json()
    root = f"/api/v1/projects/{p['id']}"
    content = ("Unrelated record. " + "x" * 1582 + " ") * 21 + "Zephyr costs forty credits."
    document = client.post(root + "/documents", files={"file": ("long.txt", content.encode(), "text/plain")}, data={"title": "Catalog", "classification": "synthetic"}).json()
    ref = client.post(root + "/ingestions", json={"document_id": document["id"]}, headers={"Idempotency-Key": str(uuid4())}).json()
    ingestion = client.get("/api/v1/jobs/" + ref["job_id"]).json()["result"]
    corpus = client.post(root + "/corpus-snapshots", json={"ingestion_run_ids": [ingestion["ingestion_run_id"]]})
    assert corpus.status_code == 201
    first = client.get(root + "/corpus-evidence", params={"limit": 20}).json()
    assert len(first["items"]) == 20 and first["next_cursor"]
    final = client.get(root + "/corpus-evidence", params={"cursor": first["next_cursor"]}).json()
    assert len(final["items"]) == 2 and final["next_cursor"] is None
    assert "Zephyr" in final["items"][-1]["quote"]
    answer = job(client, p["id"], "question", {"question": "How much does Zephyr cost?"})
    assert "forty credits" in answer["answer"]


def test_readiness_fails_when_mandatory_engine_is_missing(client, tmp_path, monkeypatch):
    monkeypatch.setattr("oe_studio.validation.RUNNER_JAR", tmp_path / "absent.jar")
    result = client.get("/health/ready")
    assert result.status_code == 503
    assert result.json()["status"] == "not_ready"
    assert result.json()["jena"] != "available"


def test_grounded_question_is_read_only(client):
    p = project(client)
    answer = job(client, p["id"], "question", {"question": "Who owns Payroll Service?"})
    assert "Operations" in answer["answer"]
    assert answer["evidence"] and all(e["resolved"] for e in answer["evidence"])
    assert any(t["predicate"].endswith("hasOwner") for t in answer["triples"])
    assert project(client)["approved_version_id"] is None


def test_fabricated_model_citations_are_retained_but_never_answered(client, monkeypatch):
    from oe_studio.model import GroundedAnswer
    studio = client.app.state.studio
    studio.settings.model_url, studio.settings.model_name = "http://localhost:11434", "fixture-model"
    monkeypatch.setattr("oe_studio.model.ModelClient.generate", lambda *args: (GroundedAnswer(answer="Unsupported claim", evidence_ids=["fabricated"], triple_indices=[], unresolved_points=[]), {"provider": "fixture"}))
    p = project(client)
    response = client.post(f"/api/v1/projects/{p['id']}/question-jobs", json={"question": "Who owns Payroll Service?"}, headers={"Idempotency-Key": str(uuid4())})
    result = client.get("/api/v1/jobs/" + response.json()["job_id"]).json()
    assert result["status"] == "failed" and result["result"] is None
    with studio.db.session() as s:
        generations = studio.items(s, p["id"], "generation")
        assert len(generations) == 1
        record = studio.body(generations[0])
        assert record["status"] == "failed"
        assert record["output"]["evidence_ids"] == ["fabricated"]


def test_unmaterializable_model_output_is_recorded_as_failed(client, monkeypatch):
    studio = client.app.state.studio
    studio.settings.model_url, studio.settings.model_name = "http://localhost:11434", "fixture-model"
    def generate(self, system, context, schema):
        change = {"operation": "add", "triple": {"subject": "https://example.org/oe-demo/Service", "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "object": "http://www.w3.org/2002/07/owl#Class"}, "evidence_ids": [context["evidence"][0]["id"]], "rationale": "Source names the service concept"}
        return schema.model_validate({"summary": "A deliberately duplicate edit fixture", "changes": [change, change]}), {"provider": "fixture"}
    monkeypatch.setattr("oe_studio.model.ModelClient.generate", generate)
    p = project(client)
    response = client.post(f"/api/v1/projects/{p['id']}/proposal-jobs", json={"instruction": "Create a source-backed proposal"}, headers={"Idempotency-Key": str(uuid4())}).json()
    assert client.get("/api/v1/jobs/" + response["job_id"]).json()["status"] == "failed"
    records = client.get(f"/api/v1/projects/{p['id']}/generation-runs").json()["items"]
    assert records[0]["status"] == "failed"
    assert "Duplicate" in records[0]["error"]
    assert records[0]["job_id"] == response["job_id"]


def test_unknown_question_has_no_fabricated_answer(client):
    p = project(client)
    answer = job(client, p["id"], "question", {"question": "What is the moon's market price?"})
    assert answer["unresolved_points"]
    assert not answer["triples"]


def test_unselected_domain_blocks_publication(client):
    p, r, v, a = checked(client)
    resp = client.post(f"/api/v1/projects/{p['id']}/review-submissions", headers={"If-Match": "1"}, json={"proposal_id": r["id"], "revision": 1, "validation_run_id": v["id"], "required_assessment_run_ids": [a["id"]]})
    assert resp.status_code == 409
    assert "scope" in resp.text.lower()


def test_publish_without_human_approval_forbidden(client):
    p, r = candidate(client)
    response = client.post(f"/api/v1/projects/{p['id']}/publications", json={"proposal_id": r["id"], "revision": 1, "bundle_digest": r["bundle_digest"], "approval_ids": [str(uuid4())], "expected_head": None}, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code in (404, 409)
    assert project(client)["approved_version_id"] is None


def test_agent_cannot_write_approved_ref(client):
    p, r, payload = accept(client)
    response = client.post(f"/api/v1/projects/{p['id']}/publications", json=payload, headers={"Authorization": "Bearer service-test-token", "Idempotency-Key": str(uuid4())})
    assert response.status_code == 403
    assert project(client)["approved_version_id"] is None


def test_native_editor_cannot_modify_canonical_release(client):
    p = project(client)
    assert client.put(f"/api/v1/projects/{p['id']}/ontology/latest", json={"ttl": "bad"}).status_code in (404, 405)


def test_duplicate_key_returns_same_publication(client):
    p, r, payload = accept(client)
    headers = {"Idempotency-Key": str(uuid4())}
    url = f"/api/v1/projects/{p['id']}/publications"
    a = client.post(url, json=payload, headers=headers)
    b = client.post(url, json=payload, headers=headers)
    assert a.status_code == b.status_code == 202, a.text
    assert a.json()["id"] == b.json()["id"]
    assert project(client)["approved_version_id"] == a.json()["new_version_id"]
    assert len(client.get(f"/api/v1/projects/{p['id']}/versions").json()["items"]) == 2
    conflict = client.post(url, json={**payload, "bundle_digest": "changed"}, headers=headers)
    assert conflict.status_code == 409


def test_two_publishers_only_one_advances_head(client):
    p, r, payload = accept(client)
    url = f"/api/v1/projects/{p['id']}/publications"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post(url, json=payload, headers={"Idempotency-Key": str(uuid4())}), range(2)))
    assert sorted(x.status_code for x in results) == [202, 409]
    assert len(client.get(f"/api/v1/projects/{p['id']}/versions").json()["items"]) == 2


def test_changed_bundle_invalidates_approval(client):
    p, r, payload = accept(client)
    response = client.post(f"/api/v1/projects/{p['id']}/publications", json={**payload, "bundle_digest": "sha256:" + "0" * 64}, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 409


def test_stale_revision_returns_409(client):
    p, r = candidate(client)
    body = {"parent_revision": 1, "structured_changes": {"additions": [{"subject": "https://example.org/oe-demo/Service", "predicate": "http://www.w3.org/2000/01/rdf-schema#comment", "object": "A service", "object_type": "literal"}]}, "rationale": "Explicit expert definition"}
    url = f"/api/v1/projects/{p['id']}/proposals/{r['id']}/revisions"
    assert client.post(url, json=body, headers={"If-Match": "1"}).status_code == 201
    assert client.post(url, json=body, headers={"If-Match": "1"}).status_code == 409
    old = client.get(url + "/1").json()
    assert old["bundle_digest"] == r["bundle_digest"]
    new = client.get(url + "/2").json()
    assert new["bundle_digest"] != old["bundle_digest"]
    assert not new["validation"] and not new["approval_ids"]


def test_cross_project_reads_hidden(client):
    p, r = candidate(client)
    other = client.post("/api/v1/projects", json={"name": "Other"}).json()
    assert client.get(f"/api/v1/projects/{other['id']}/proposals/{r['id']}/revisions/1").status_code == 404


def test_csrf_and_client_identity_rejected(client):
    assert client.post("/api/v1/projects", json={"name": "bad"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/v1/projects", json={"name": "bad", "actor": "approver"}).status_code == 422


def test_upload_is_not_processing_complete(client):
    p = project(client)
    r = client.post(f"/api/v1/projects/{p['id']}/documents", files={"file": ("source.txt", b"Backup Service is owned by Reliability Team.", "text/plain")}, data={"title": "Backup policy", "classification": "synthetic", "edition": "1", "rights": "demo"})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "uploaded"
    response = client.post(f"/api/v1/projects/{p['id']}/ingestions", json={"document_id": r.json()["id"], "configured_flow_key": "default"}, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 202
    docs = client.get(f"/api/v1/projects/{p['id']}/documents").json()["items"]
    assert next(d for d in docs if d["id"] == r.json()["id"])["status"] == "complete"


@pytest.mark.parametrize("processed", [False, True])
def test_withdrawn_source_cannot_be_reactivated_by_ingestion(client, processed):
    p = project(client)
    root = f"/api/v1/projects/{p['id']}"
    document = client.post(root + "/documents", files={"file": ("source.txt", b"Explicitly withdrawn source.", "text/plain")}, data={"title": "Withdrawn test", "classification": "synthetic"}).json()
    if processed:
        response = client.post(root + "/ingestions", json={"document_id": document["id"]}, headers={"Idempotency-Key": str(uuid4())})
        assert client.get("/api/v1/jobs/" + response.json()["job_id"]).json()["status"] == "succeeded"
    assert client.post(root + f"/documents/{document['id']}/withdrawal", json={"rationale": "Human withdrew this test source"}).status_code == 201
    response = client.post(root + "/ingestions", json={"document_id": document["id"]}, headers={"Idempotency-Key": str(uuid4()), "Authorization": "Bearer service-test-token"})
    assert response.status_code == 202
    result = client.get("/api/v1/jobs/" + response.json()["job_id"]).json()
    assert result["status"] == "failed"
    assert "withdrawn" in result["error"].lower()
    doc = next(d for d in client.get(root + "/documents").json()["items"] if d["id"] == document["id"])
    assert doc["status"] == "withdrawn"
    assert doc["chunk_count"] == (1 if processed else 0)


@pytest.mark.parametrize("stage", ["reserved", "commit_created", "ref_advanced", "finalized"])
def test_publication_recovers_after_crash(client, monkeypatch, stage):
    p, r, payload = accept(client)
    studio = client.app.state.studio
    def crash(point):
        if point == stage:
            raise RuntimeError("simulated process stop")
    monkeypatch.setattr(studio, "publication_checkpoint", crash)
    from oe_studio.schemas import PublishRequest
    with pytest.raises(RuntimeError, match="simulated"):
        studio.publish(p["id"], PublishRequest(**payload), "crash-key", {"subject": "local-human", "kind": "human", "roles": ["approver"]})
    monkeypatch.setattr(studio, "publication_checkpoint", lambda _: None)
    studio.reconcile_pending()
    current = project(client)
    assert current["approved_version_id"]
    assert current["pending_publication_id"] is None
    versions = client.get(f"/api/v1/projects/{p['id']}/versions").json()["items"]
    assert len([v for v in versions if v["status"] == "approved"]) == 1
    assert studio.git.head(p["id"]) == next(v["commit"] for v in versions if v["status"] == "approved")


def test_source_withdrawal_blocks_new_publication(client):
    p, r, payload = accept(client)
    studio = client.app.state.studio
    with studio.db.session(write=True) as s:
        doc = studio.items(s, p["id"], "document")[0]
        doc.status = "withdrawn"
    response = client.post(f"/api/v1/projects/{p['id']}/publications", json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 409
    assert "withdrawn" in response.text


def test_required_assessment_matches_approval_bundle(client):
    p, r, v, a = checked(client)
    _, other, _, other_assessment = checked(client)
    root = f"/api/v1/projects/{p['id']}"
    client.post(root + "/scope-decisions", json={"scope_digest": p["scope_digest"], "decision": "accept", "rationale": "Synthetic demo only"})
    response = client.post(root + "/review-submissions", headers={"If-Match": "1"}, json={"proposal_id": r["id"], "revision": 1, "validation_run_id": v["id"], "required_assessment_run_ids": [other_assessment["id"]]})
    assert response.status_code == 409


def test_fabricated_quote_blocks_review(client):
    p, r, v, a = checked(client)
    studio = client.app.state.studio
    with studio.db.session(write=True) as s:
        e = studio.items(s, p["id"], "evidence")[0]
        e.data = {**e.data, "quote": "Fabricated quote"}
    response = client.post(f"/api/v1/projects/{p['id']}/review-submissions", headers={"If-Match": "1"}, json={"proposal_id": r["id"], "revision": 1, "validation_run_id": v["id"], "required_assessment_run_ids": [a["id"]]})
    assert response.status_code == 409
    assert "integrity" in response.text


def test_new_domain_oracle_needs_review(client):
    p, r = candidate(client)
    suite = job(client, p["id"], "test-generation", {"proposal_id": r["id"], "revision": 1})
    assert suite["status"] == "needs_review"
    response = client.post(f"/api/v1/projects/{p['id']}/test-oracle-decisions", json={"test_suite_id": suite["id"], "test_suite_digest": suite["digest"], "decision": "accept", "rationale": "Reviewed all four expected outcomes"}, headers={"Authorization": "Bearer service-test-token"})
    assert response.status_code == 403
    response = client.post(f"/api/v1/projects/{p['id']}/test-oracle-decisions", json={"test_suite_id": suite["id"], "test_suite_digest": suite["digest"], "decision": "accept", "rationale": "Reviewed all four expected outcomes"})
    assert response.status_code == 201, response.text
    successor = response.json()
    assert successor["revision"] == 2 and successor["bundle_digest"] != r["bundle_digest"]
    assert not successor["validation"] and not successor["approval_ids"]
    studio = client.app.state.studio
    import json
    with studio.db.session() as s:
        rev = studio.revision(s, p["id"], r["id"], 2)
        tests = json.loads(studio.artifacts.get_verified(rev.data["tests"]))
        assert {"CQ-01", "CQ-02"}.issubset(t["test_id"] for t in tests)
        assert {t['test_id'] for t in suite['tests']}.issubset(t['test_id'] for t in tests)
        assert {t['scenario'] for t in suite['tests']} >= {"positive", "negative", "missing_data", "boundary", "regression"}


def test_service_session_does_not_issue_human_cookie(client):
    client.cookies.clear()
    response = client.get("/api/v1/session", headers={"Authorization": "Bearer service-test-token"})
    assert response.status_code == 200
    assert response.json()["actor"]["kind"] == "service"
    assert "oe_session" not in response.cookies
    assert client.get("/api/v1/projects").status_code == 401


def test_omitted_service_credential_cannot_bootstrap_human(client):
    client.cookies.clear()
    assert client.get("/api/v1/session").status_code == 401
    assert client.get("/api/v1/session", headers={"X-OE-Session-Token": "made-up"}).status_code == 401
    response = client.get("/api/v1/session", headers={"X-OE-Session-Token": client.app.state.bootstrap_token})
    assert response.status_code == 200
    assert response.cookies.get("oe_session")


def test_changed_scope_blocks_recovery_before_ref_advance(client, monkeypatch):
    p, r, payload = accept(client)
    studio = client.app.state.studio
    def crash(stage):
        if stage == "commit_created":
            raise RuntimeError("stop before CAS")
    monkeypatch.setattr(studio, "publication_checkpoint", crash)
    from oe_studio.schemas import PublishRequest
    with pytest.raises(RuntimeError):
        studio.publish(p["id"], PublishRequest(**payload), "recover-scope", {"subject": "local-human", "kind": "human", "roles": ["approver"]})
    with studio.db.session(write=True) as s:
        record = studio.project(s, p["id"])
        record.data = {**record.data, "scope_accepted": False}
    monkeypatch.setattr(studio, "publication_checkpoint", lambda _: None)
    from oe_studio.errors import Problem
    with pytest.raises(Problem, match="scope"):
        studio.reconcile_pending()
    assert studio.git.head(p["id"]) is None


def test_followup_context_digest_includes_history(client):
    p = project(client)
    one = job(client, p["id"], "question", {"question": "Who owns it?", "history": [{"role": "user", "content": "Tell me about Payroll Service"}]})
    two = job(client, p["id"], "question", {"question": "Who owns it?", "history": [{"role": "user", "content": "Tell me about Analytics Service"}]})
    assert one["context_digest"] != two["context_digest"]


def test_tampered_assessment_report_blocks_publication(client):
    p, r, payload = accept(client)
    studio = client.app.state.studio
    with studio.db.session(write=True) as s:
        report = studio.items(s, p["id"], "assessment")[0]
        report.data = {**report.data, "strict_fitness": 0.0}
    response = client.post(f"/api/v1/projects/{p['id']}/publications", json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 409
    assert studio.git.head(p["id"]) is None


def test_changed_runner_invalidates_bundle(client, tmp_path, monkeypatch):
    from oe_studio import validation
    runner = tmp_path / "fake.jar"
    runner.write_bytes(b"runner-v1")
    monkeypatch.setattr(validation, "RUNNER_JAR", runner)
    p, r, payload = accept(client)
    runner.write_bytes(b"runner-v2")
    response = client.post(f"/api/v1/projects/{p['id']}/publications", json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 409
    assert "Engine configuration changed" in response.text


def test_blocked_reconciliation_does_not_starve_other_projects(client, monkeypatch):
    p, r, payload = accept(client)
    studio = client.app.state.studio
    from oe_studio.schemas import PublishRequest
    def crash(stage):
        if stage == "reserved":
            raise RuntimeError("stop")
    monkeypatch.setattr(studio, "publication_checkpoint", crash)
    with pytest.raises(RuntimeError):
        studio.publish(p["id"], PublishRequest(**payload), "starvation", {"subject": "local-human", "kind": "human", "roles": ["approver"]})
    monkeypatch.setattr(studio, "publication_checkpoint", lambda _: None)
    with studio.db.session(write=True) as s:
        record = studio.project(s, p["id"])
        record.data = {**record.data, "scope_accepted": False}
    errors = studio.reconcile_pending(continue_on_error=True)
    assert errors and errors[0]["project_id"] == p["id"]
    other = client.post("/api/v1/projects", json={"name": "Independent"}).json()
    result = job(client, other["id"], "question", {"question": "What sources are here?"})
    assert result["unresolved_points"]


def test_demo_generator_cannot_attribute_seed_to_unrelated_corpus(client):
    other = client.post("/api/v1/projects", json={"name": "Other demo", "domain": "demo"}).json()
    root = f"/api/v1/projects/{other['id']}"
    document = client.post(root + "/documents", files={"file": ("unrelated.txt", b"The sky is blue.", "text/plain")}, data={"title": "Unrelated", "classification": "synthetic"}).json()
    ref = client.post(root + "/ingestions", json={"document_id": document["id"]}, headers={"Idempotency-Key": str(uuid4())}).json()
    ingestion = client.get("/api/v1/jobs/" + ref["job_id"]).json()["result"]
    corpus = client.post(root + "/corpus-snapshots", json={"ingestion_run_ids": [ingestion["ingestion_run_id"]]}).json()
    ref = client.post(root + "/proposal-jobs", json={"corpus_snapshot_id": corpus["id"], "instruction": "Create an ontology"}, headers={"Idempotency-Key": str(uuid4())}).json()
    result = client.get("/api/v1/jobs/" + ref["job_id"]).json()
    assert result["status"] == "failed"
    assert "model" in result["error"].lower()


def test_review_sessions_reject_impossible_order(client):
    p, r = candidate(client)
    url = f"/api/v1/projects/{p['id']}/review-sessions"
    body = {"revision_id": r["revision_id"]}
    assert client.post(url, json={**body, "event": "pause"}).status_code == 409
    assert client.post(url, json={**body, "event": "start"}).status_code == 201
    assert client.post(url, json={**body, "event": "pause"}).status_code == 201
    assert client.post(url, json={**body, "event": "resume"}).status_code == 201
    result = client.post(url, json={**body, "event": "end"})
    assert result.status_code == 201 and result.json()["active_seconds"] >= 0
    assert client.post(url, json={**body, "event": "resume"}).status_code == 409


def test_repair_uses_frozen_question_ids_without_a_naming_convention(client, monkeypatch):
    from oe_studio.demo import QUESTIONS, SHAPES, FIXTURES
    p = project(client)
    root = f"/api/v1/projects/{p['id']}"
    questions = [{**question, "id": "owner-required" if index == 0 else question["id"], "expected": True} for index, question in enumerate(QUESTIONS)]
    assert client.post(root + "/scope", json={"title": "Named questions", "purpose": "Synthetic non-prefixed question IDs", "competency_questions": questions, "shapes_ttl": SHAPES, "fixtures_ttl": FIXTURES}).status_code == 201
    p, r = candidate(client)
    monkeypatch.setattr("oe_studio.workflow.run_validation", lambda ttl, **kw: {"id": str(uuid4()), "status": "failed", "bundle_digest": kw["bundle_digest"], "cases": [{"id": "owner-required", "status": "failed", "expected": True, "actual": False}, {"id": "CQ-unregistered", "status": "failed", "expected": True, "actual": False}]})
    payload = {"proposal_id": r["id"], "revision": 1, "bundle_digest": r["bundle_digest"]}
    job(client, p["id"], "validation", payload)
    studio = client.app.state.studio
    studio.settings.model_url, studio.settings.model_name = "http://localhost:11434", "fixture-model"
    def generate(self, system, context, schema):
        assert [case["id"] for case in context["failed_entailment_cases"]] == ["owner-required"]
        return schema.model_validate({"summary": "A cited repair test fixture", "changes": [{"operation": "add", "triple": {"subject": "https://example.org/oe-demo/Service", "predicate": "http://www.w3.org/2000/01/rdf-schema#comment", "object": "A source-backed repair fixture", "object_type": "literal"}, "evidence_ids": [context["evidence"][0]["id"]], "rationale": "Controlled source-backed repair fixture"}]}), {"provider": "fixture"}
    monkeypatch.setattr("oe_studio.model.ModelClient.generate", generate)
    result = job(client, p["id"], "repair", payload)
    assert result["revision"] == 2


def test_repair_stops_after_two_attempts(client, monkeypatch):
    from rdflib import RDFS, URIRef
    from oe_studio.rdf import parse_ttl, NS
    def validate(ttl, **kwargs):
        status = "passed" if (URIRef(NS + "CriticalService"), RDFS.subClassOf, URIRef(NS + "Service")) in parse_ttl(ttl) else "failed"
        return {"id": str(uuid4()), "status": status, "bundle_digest": kwargs["bundle_digest"], "profile": "rdfs", "engine": "fixture", "cases": [{"id": "CQ-01", "status": status, "expected": True, "actual": status == "passed"}], "stages": []}
    monkeypatch.setattr("oe_studio.workflow.run_validation", validate)
    p, r = candidate(client)
    revision_number = 1
    for attempt in range(3):
        broken = client.post(f"/api/v1/projects/{p['id']}/proposals/{r['id']}/revisions", headers={"If-Match": str(revision_number)}, json={"parent_revision": revision_number, "structured_changes": {"deletions": [{"subject": NS + "CriticalService", "predicate": str(RDFS.subClassOf), "object": NS + "Service"}]}, "rationale": "Deliberate negative test fixture"}).json()
        request = {"proposal_id": r["id"], "revision": broken["revision"], "bundle_digest": broken["bundle_digest"]}
        assert job(client, p["id"], "validation", request)["status"] == "failed"
        response = client.post(f"/api/v1/projects/{p['id']}/repair-jobs", json=request, headers={"Idempotency-Key": str(uuid4())})
        assert response.status_code == 202, response.text
        result = client.get("/api/v1/jobs/" + response.json()["job_id"]).json()
        if attempt < 2:
            assert result["status"] == "succeeded", result
            revision_number = result["result"]["revision"]
            repaired = {"proposal_id": r["id"], "revision": revision_number, "bundle_digest": result["result"]["bundle_digest"]}
            assert job(client, p["id"], "validation", repaired)["status"] == "passed"
        else:
            assert result["status"] == "failed"
            assert "two" in result["error"]
    assert project(client)["approved_version_id"] is None


def test_artifact_download_is_scoped_and_verified(client):
    p = project(client)
    version = client.get(f"/api/v1/projects/{p['id']}/versions").json()["items"][0]
    ref = version["ontology"]
    assert "id" in ref
    url = f"/api/v1/projects/{p['id']}/artifacts/{ref['id']}"
    response = client.get(url)
    assert response.status_code == 200 and "PayrollService" in response.text
    other = client.post("/api/v1/projects", json={"name": "Other"}).json()
    assert client.get(f"/api/v1/projects/{other['id']}/artifacts/{ref['id']}").status_code == 404
    path = client.app.state.studio.artifacts.root / ref["sha256"]
    path.write_text("changed")
    assert client.get(url).status_code == 409


def test_new_scope_invalidates_older_bundle(client):
    p, r, payload = accept(client)
    root = f"/api/v1/projects/{p['id']}"
    upload = client.post(root + "/scope", json={"title": "Revised demo scope", "purpose": "Test a smaller ontology task", "competency_questions": [{"id": "CQ-custom", "question": "Does a service exist?", "sparql_query": "PREFIX demo: <https://example.org/oe-demo/> ASK { ?x a demo:Service }", "expected": True}], "shapes_ttl": "", "fixtures_ttl": ""})
    assert upload.status_code == 201, upload.text
    updated = client.get(root).json()
    assert not updated["scope_accepted"]
    selected_scope = client.get(root + "/scope").json()
    assert selected_scope["id"] == upload.json()["id"]
    assert selected_scope["digest"] == updated["scope_digest"]
    assert selected_scope["title"] == "Revised demo scope"
    assert client.get(root + "/scopes").json()["items"][0]["id"] == selected_scope["id"]
    client.post(root + "/scope-decisions", json={"scope_digest": updated["scope_digest"], "decision": "accept", "rationale": "Review the revised synthetic scope"})
    response = client.post(root + "/publications", json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 409 and "scope" in response.text.lower()


def test_mapping_change_needs_reassessment_and_review(client):
    from oe_studio.rdf import NS
    p, r, payload = accept(client)
    root = f"/api/v1/projects/{p['id']}"
    draft = client.post(root + "/mapping-sets", json={"mappings": [{"requirement_iri": NS + "Service", "ontology_iri": NS + "Service", "relation_type": "canonical_correspondence", "rationale": "Explicit reviewed requirement correspondence", "evidence_ids": [r["evidence_ids"][0]]}]})
    assert draft.status_code == 201, draft.text
    mapping = draft.json()
    decision = client.post(root + "/mapping-decisions", json={"mapping_set_id": mapping["id"], "digest": mapping["digest"], "decision": "accept", "rationale": "Reviewed full IRI correspondence"})
    assert decision.status_code == 201, decision.text
    assert decision.json()["mappings"][0]["reviewer"] == "local-human"
    assert client.get(root + "/mapping-config").json()["decision_id"] == decision.json()["id"]
    assert r["evidence_ids"][0] in {e["id"] for e in client.get(root + "/corpus-evidence").json()["items"]}
    assert client.post(root + "/publications", json=payload, headers={"Idempotency-Key": str(uuid4())}).status_code == 409
    successor = client.post(root + f"/proposals/{r['id']}/revisions", headers={"If-Match": "1"}, json={"parent_revision": 1, "structured_changes": {}, "rationale": "Freeze the newly reviewed mapping set"})
    assert successor.status_code == 201, successor.text
    newer = successor.json()
    assert newer["bundle_digest"] != r["bundle_digest"]
    assert newer["validation"] is None and newer["assessment"] is None
    assert newer["manifest"]["assessment_mappings"][0]["review_id"] == decision.json()["id"]
    assert client.get(root + "/mapping-sets").json()["items"][0]["id"] == mapping["id"]


def test_service_cannot_accept_mappings(client):
    p = project(client)
    root = f"/api/v1/projects/{p['id']}"
    draft = client.post(root + "/mapping-sets", json={"mappings": []})
    assert draft.status_code == 201
    result = client.post(root + "/mapping-decisions", headers={"Authorization": "Bearer service-test-token"}, json={"mapping_set_id": draft.json()["id"], "digest": draft.json()["digest"], "decision": "accept", "rationale": "Attempted automated mapping approval"})
    assert result.status_code == 403


@pytest.mark.parametrize("status", ["error", "timeout", "unsupported", "not_run"])
def test_assessment_error_blocks_required_report_gate(client, monkeypatch, status):
    monkeypatch.setattr("oe_studio.workflow.run_assessment", lambda ttl, **kw: {"id": str(uuid4()), "status": status, "bundle_digest": kw["bundle_digest"]})
    p, r, v, a = checked(client)
    root = f"/api/v1/projects/{p['id']}"
    client.post(root + "/scope-decisions", json={"scope_digest": p["scope_digest"], "decision": "accept", "rationale": "Isolated synthetic test scope"})
    result = client.post(root + "/review-submissions", json={"proposal_id": r["id"], "revision": 1, "validation_run_id": v["id"], "required_assessment_run_ids": [a["id"]]}, headers={"If-Match": "1"})
    assert result.status_code == 409 and "assessment" in result.text.lower()
    assert a["status"] == status and project(client)["approved_version_id"] is None


def test_stale_base_returns_409(client):
    p, _, payload = accept(client)
    _, old = candidate(client)
    root = f"/api/v1/projects/{p['id']}"
    assert client.post(root + "/publications", json=payload, headers={"Idempotency-Key": str(uuid4())}).status_code == 202
    stale = client.post(root + f"/proposals/{old['id']}/revisions", json={"parent_revision": 1, "structured_changes": {}, "rationale": "Try to revise a proposal based on an older head"}, headers={"If-Match": "1"})
    assert stale.status_code == 409 and "head" in stale.text.lower()


def test_agent_candidate_edits_do_not_change_approved_ref_or_bytes(client):
    p, _, payload = accept(client)
    root = f"/api/v1/projects/{p['id']}"
    assert client.post(root + "/publications", json=payload, headers={"Idempotency-Key": str(uuid4())}).status_code == 202
    p = project(client)
    before = client.get(root + "/versions/" + p["approved_version_id"]).json()
    ref = client.app.state.studio.git.head(p["id"])
    headers = {"Authorization": "Bearer service-test-token", "Idempotency-Key": str(uuid4())}
    queued = client.post(root + "/proposal-jobs", json={"base_version_id": p["approved_version_id"], "instruction": "Clarify service ownership"}, headers=headers).json()
    created = client.get("/api/v1/jobs/" + queued["job_id"]).json()["result"]
    assert created
    edited = client.post(root + f"/proposals/{created['proposal_id']}/revisions", headers={"Authorization": "Bearer service-test-token", "If-Match": "1"}, json={"parent_revision": 1, "structured_changes": {}, "rationale": "Create a candidate successor without publication"})
    assert edited.status_code == 201
    assert project(client)["approved_version_id"] == p["approved_version_id"]
    assert client.app.state.studio.git.head(p["id"]) == ref
    assert client.get(root + "/versions/" + p["approved_version_id"]).json()["ttl"] == before["ttl"]


def test_agent_cannot_remove_required_sentinel(client):
    p, r = candidate(client)
    response = client.post(f"/api/v1/projects/{p['id']}/proposals/{r['id']}/revisions", headers={"Authorization": "Bearer service-test-token", "If-Match": "1"}, json={"parent_revision": 1, "structured_changes": {}, "rationale": "Attempt to replace the frozen required test policy", "tests": []})
    assert response.status_code == 422
    with client.app.state.studio.db.session() as s:
        revision = client.app.state.studio.revision(s, p["id"], r["id"], 1)
        import json
        tests = json.loads(client.app.state.studio.artifacts.get_verified(revision.data["tests"]))
        assert {t["test_id"] for t in tests} >= {"CQ-01", "CQ-02"}


def test_model_experiment_enters_real_review_and_preserves_pre_post(client, monkeypatch):
    from oe_studio import experiments as ex
    studio = client.app.state.studio
    studio.settings.model_url, studio.settings.model_name = "http://localhost:11434", "fixture-model"
    def generate(self, system, context, schema):
        return schema.model_validate({"summary": "Reviewed frozen synthetic source requirements", "changes": []}), {"elapsed_seconds": .1, "input_tokens": 10, "output_tokens": 10}
    monkeypatch.setattr("oe_studio.model.ModelClient.generate", generate)
    monkeypatch.setattr(ex, "validate", lambda ttl, **kw: {"status": "passed", "cases": [{"id": t["test_id"], "status": "passed", "expected": t["expected"], "actual": t["expected"]} for t in kw["tests"]]})
    monkeypatch.setattr(ex, "assess", lambda ttl, **kw: {"status": "completed"})
    p = project(client)
    root = f"/api/v1/projects/{p['id']}"
    runs = job(client, p["id"], "experiment", {"protocol_id": "model-pilot-v1", "condition": "all", "task_ids": ["demo-ownership"], "replicate_ids": [1]})["runs"]
    assert len(runs) == 4 and len({r["initial_generation_call_id"] for r in runs}) == 1
    d = next(r for r in runs if r["condition"] == "D")
    staged = client.post(root + f"/experiments/{d['id']}/proposal")
    assert staged.status_code == 201, staged.text
    r = staged.json()
    request = {"proposal_id": r["id"], "revision": 1, "bundle_digest": r["bundle_digest"]}
    v = job(client, p["id"], "validation", request)
    a = job(client, p["id"], "assessment", request)
    client.post(root + "/scope-decisions", json={"scope_digest": p["scope_digest"], "decision": "accept", "rationale": "Synthetic test scope only"})
    submission = {"proposal_id": r["id"], "revision": 1, "validation_run_id": v["id"], "required_assessment_run_ids": [a["id"]]}
    assert client.post(root + "/review-submissions", json=submission, headers={"If-Match": "1"}).status_code == 201
    review = client.post(root + "/reviews", json={**submission, "bundle_digest": r["bundle_digest"], "decision": "accept", "rationale": "Isolated test review of exact candidate", "review_policy_id": p["review_policy_id"]})
    assert review.status_code == 201, review.text
    post = client.post(root + f"/experiments/{d['id']}/review-results", json={"review_id": review.json()["id"]})
    assert post.status_code == 201, post.text
    result = post.json()
    assert result["parent_run_id"] == d["id"] and result["phase"] == "post_review"
    assert result["correction_seconds"] is None
    assert result["pre_review_snapshot"] == d["pre_review_snapshot"]
    assert result["post_review_snapshot"]["bundle_digest"] == r["bundle_digest"]
    duplicate = client.post(root + f"/experiments/{d['id']}/review-results", json={"review_id": review.json()["id"]})
    assert duplicate.json()["id"] == result["id"]
    originals = client.get(root + "/experiments").json()["items"]
    assert next(run for run in originals if run["id"] == d["id"])["post_review_snapshot"] is None
    assert project(client)["approved_version_id"] is None


def test_default_scope_is_readable_with_explicit_oracles(client):
    p = project(client)
    scope = client.get(f"/api/v1/projects/{p['id']}/scope")
    assert scope.status_code == 200
    assert scope.json()["digest"] == p["scope_digest"]
    assert scope.json()["competency_questions"] and all(q["expected"] is True for q in scope.json()["competency_questions"])
    assert scope.json()["accepted"] is False


def test_seed_import_is_a_candidate_until_human_approval(client):
    from oe_studio.demo import ONTOLOGY
    p = project(client)
    response = client.post(f"/api/v1/projects/{p['id']}/seed-imports", json={"ontology_ttl": ONTOLOGY, "corpus_snapshot_id": p["corpus_snapshot_id"], "rationale": "An explicitly staged synthetic seed"}, headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 202, response.text
    value = client.get("/api/v1/jobs/" + response.json()["job_id"]).json()
    assert value["status"] == "succeeded"
    assert project(client)["approved_version_id"] is None
