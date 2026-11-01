#!/usr/bin/env python3
"""Real native-editor boundary check; run prepare, perform the UI edit, then verify.

Uses only synthetic local data. The populated Studio release uses the real engines
and workflow with explicitly simulated decisions; it is not a research observation.
Credentials and temporary state stay in ignored runtime/. No browser automation is
hidden here: the native class must be added using the actual ontology editor.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = HERE / "runtime/native-boundary-state.json"
EVIDENCE = ROOT / "docs/native-editor-boundary-evidence.json"
WORKSPACE = "oe-native-boundary"
ONTOLOGY = "native-boundary-candidate"
CLASS = "NativeBoundaryOnly"
RATIONALE = "SIMULATED ENGINEERING TEST: native-editor boundary fixture; not a human-study observation."


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def files(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file()}


def canonical_snapshot(data):
    """Read file bytes, every Git ref, and canonical DB projections without writes."""
    with sqlite3.connect(f"file:{data / 'studio.sqlite'}?mode=ro", uri=True) as db:
        projects = db.execute("SELECT id,approved_version_id,pending_publication_id FROM projects ORDER BY id").fetchall()
        records = db.execute("SELECT id,project_id,kind,status,data FROM items WHERE kind IN ('version','publication','review','audit') ORDER BY id").fetchall()
    refs = subprocess.check_output(["git", f"--git-dir={data / 'ontology.git'}", "for-each-ref", "--format=%(refname) %(objectname)"]).decode().splitlines()
    return {"artifacts": files(data / "artifacts"), "git_files": files(data / "ontology.git"),
            "git_refs": refs, "projects": projects, "canonical_records_sha256": digest(records),
            "canonical_record_count": len(records)}


def request(base, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urlopen(req, timeout=45) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def native(path, body, token):
    status, value = request("http://127.0.0.1:18888/api/v1", path, body, token)
    assert status == 200 and not value.get("error"), (path, status, value.get("error"))
    return value


def login():
    credentials = json.loads((HERE / "runtime/login.json").read_text())
    return native("/auth/login", credentials, None)["jwt"]


def native_ontology(token):
    value = native("/config", {"operation": "get", "workspace": WORKSPACE,
                   "keys": [{"type": "ontology", "key": ONTOLOGY}]}, token)
    return json.loads(value["values"][0]["value"])


def app(data):
    from oe_studio.main import create_app
    from oe_studio.settings import Settings
    return create_app(Settings(data_dir=data, database_url="", eager_jobs=True,
                              model_url="", model_name="", model_api_key="", service_token=""))


def populate(data):
    from fastapi.testclient import TestClient
    application = app(data)
    with TestClient(application) as client:
        assert client.get("/api/v1/session", headers={"X-OE-Session-Token": application.state.bootstrap_token}).status_code == 200
        project = client.get("/api/v1/projects").json()["items"][0]
        base = f"/api/v1/projects/{project['id']}"

        def post(path, body, expected, headers=None):
            response = client.post(base + path, json=body, headers=headers or {})
            assert response.status_code == expected, response.text
            return response.json()

        def job(kind, body):
            ref = post(f"/{kind}-jobs", body, 202, {"Idempotency-Key": str(uuid4())})
            result = client.get("/api/v1/jobs/" + ref["job_id"]).json()
            assert result["status"] == "succeeded", result
            return result["result"]

        candidate = job("proposal", {"corpus_snapshot_id": project["corpus_snapshot_id"], "instruction": RATIONALE})
        revision = client.get(base + f"/proposals/{candidate['proposal_id']}/revisions/1").json()
        bundle = {"proposal_id": revision["id"], "revision": 1, "bundle_digest": revision["bundle_digest"]}
        validation = job("validation", bundle)
        assessment = job("assessment", bundle)
        assert validation["status"] == "passed" and assessment["status"] == "completed"
        post("/scope-decisions", {"scope_digest": project["scope_digest"], "decision": "accept", "rationale": RATIONALE}, 201)
        submission = {"proposal_id": revision["id"], "revision": 1, "validation_run_id": validation["id"], "required_assessment_run_ids": [assessment["id"]]}
        post("/review-submissions", submission, 201, {"If-Match": "1"})
        review = post("/reviews", {**submission, "bundle_digest": revision["bundle_digest"], "decision": "accept", "rationale": RATIONALE, "review_policy_id": project["review_policy_id"]}, 201)
        payload = {**bundle, "approval_ids": [review["id"]], "expected_head": None}
        publication = post("/publications", payload, 202, {"Idempotency-Key": str(uuid4())})
        assert publication["status"] == "completed", publication
        return {"project_id": project["id"], "publication": publication, "payload": payload,
                "validation_engine": validation["engine"], "assessment_engine": assessment.get("engine"),
                "review_id": review["id"], "rationale": RATIONALE}


def prepare():
    assert not STATE.exists(), "Finish or clean the existing boundary run first"
    token = login()
    workspaces = native("/iam", {"operation": "list-workspaces"}, token)["workspaces"]
    assert not any(w["id"] == WORKSPACE for w in workspaces), "Refuse to reuse a native workspace"
    native("/iam", {"operation": "create-workspace", "workspace_record": {
        "id": WORKSPACE, "name": "SIMULATED native editor boundary sandbox", "enabled": True}}, token)
    ontology = {"metadata": {"name": "SIMULATED native boundary candidate", "description": RATIONALE,
                "version": "1.0.0", "namespace": "https://example.org/native-boundary#", "creator": "engineering-test"},
                "classes": {}, "objectProperties": {}, "datatypeProperties": {}}
    native("/config", {"operation": "put", "workspace": WORKSPACE, "values": [
        {"type": "ontology", "key": ONTOLOGY, "value": json.dumps(ontology)}]}, token)
    fixture = Path(tempfile.mkdtemp(prefix="oe-native-boundary-", dir="/private/tmp"))
    state = {"workspace": WORKSPACE, "fixture": str(fixture), "fixture_release": populate(fixture),
             "native_before": native_ontology(token),
             "main_before": canonical_snapshot(ROOT / ".data"), "fixture_before": canonical_snapshot(fixture)}
    assert state["fixture_before"]["git_refs"], "Need a real populated canonical ref"
    STATE.write_text(json.dumps(state, indent=2))
    STATE.chmod(0o600)
    print(f"Prepared actual approved simulated fixture and fresh native workspace {WORKSPACE}. Add class {CLASS} through the native UI, then run verify.")


def verify():
    global WORKSPACE
    from fastapi.testclient import TestClient
    state = json.loads(STATE.read_text())
    WORKSPACE = state.get("workspace", WORKSPACE)
    fixture = Path(state["fixture"])
    token = login()
    after = native_ontology(token)
    assert CLASS not in state["native_before"]["classes"] and CLASS in after["classes"], "UI class edit not persisted"
    assert digest(state["native_before"]) != digest(after)
    main_project = state["main_before"]["projects"][0][0]
    status, _ = request("http://127.0.0.1:5183/api/v1", f"/projects/{main_project}/publications", state["fixture_release"]["payload"], token)
    assert status == 401, f"Actual native JWT reached live publication path: HTTP {status}"
    with TestClient(app(fixture)) as client:
        response = client.post(f"/api/v1/projects/{state['fixture_release']['project_id']}/publications", json=state["fixture_release"]["payload"], headers={"Authorization": "Bearer " + token, "Idempotency-Key": str(uuid4())})
        assert response.status_code == 401, response.text
    main_after = canonical_snapshot(ROOT / ".data")
    fixture_after = canonical_snapshot(fixture)
    # JSON normalizes SQLite tuples into lists, including the baseline persisted above.
    assert digest(state["main_before"]) == digest(main_after), "Main canonical store changed"
    assert digest(state["fixture_before"]) == digest(fixture_after), "Populated fixture canonical store changed"
    evidence = {"classification": "SIMULATED ENGINEERING TEST; no study participant or observation",
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "workspace": WORKSPACE, "ontology_id": ONTOLOGY, "native_edit_class": CLASS,
                "native_before": state["native_before"], "native_after": after,
                "native_before_sha256": digest(state["native_before"]), "native_after_sha256": digest(after),
                "main_before": state["main_before"], "main_after": main_after,
                "fixture_before": state["fixture_before"], "fixture_after": fixture_after,
                "fixture_release": state["fixture_release"],
                "main_native_jwt_publication_http": status, "fixture_native_jwt_publication_http": response.status_code,
                "main_unchanged": True, "populated_fixture_unchanged": True,
                "limits": ["Native editor changes its workspace ontology configuration, not a Studio release.",
                           "Live main publication denial uses HTTP through the real portal; populated fixture denial uses the real ASGI app without mocks.",
                           "Local API/store separation is verified; OS credential/process isolation and shared identity remain unverified."]}
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n")
    print("PASS: native UI class persisted; live main and populated canonical fixture byte-identical; actual native JWT publication HTTP 401 in both apps.")


def cleanup():
    global WORKSPACE
    state = json.loads(STATE.read_text())
    WORKSPACE = state.get("workspace", WORKSPACE)
    fixture = Path(state["fixture"])
    assert fixture.parent == Path("/private/tmp") and fixture.name.startswith("oe-native-boundary-")
    assert EVIDENCE.exists(), "Retain sanitized verification evidence before cleanup"
    shutil.rmtree(fixture)
    native("/iam", {"operation": "disable-workspace", "workspace_record": {"id": WORKSPACE}}, login())
    STATE.unlink()
    evidence = json.loads(EVIDENCE.read_text())
    evidence["cleanup"] = {"temporary_studio_fixture_removed": True, "native_workspace_disabled": True}
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n")
    print("Removed disposable Studio fixture and disabled only the synthetic native workspace.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "verify", "cleanup"])
    parser.add_argument("--workspace", default=WORKSPACE, help="Fresh synthetic workspace ID for prepare; later phases use saved state")
    args = parser.parse_args()
    WORKSPACE = args.workspace
    globals()[args.phase]()
