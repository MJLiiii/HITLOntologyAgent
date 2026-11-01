"""Live synthetic low-privilege workspace denial; no Study or Studio writes."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import time
from uuid import uuid4

from check_native_boundary import login, native, request


def run(output):
    if output.exists():
        raise ValueError("Refuse to overwrite prior verification evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    admin = login()
    suffix = uuid4().hex[:10]
    own, foreign = "oe-denial-own-" + suffix, "oe-denial-other-" + suffix
    workspaces, user_id = [], None
    report = {"classification": "synthetic_engineering_test", "study_observations": False,
              "verified_at": datetime.now(timezone.utc).isoformat(), "checks": {}, "status": "incomplete"}
    def probe(path, body, token):
        return request("http://127.0.0.1:18888/api/v1", path, body, token)
    def document(workspace, identity, content):
        return {"operation": "add-document", "workspace": workspace,
                "document-metadata": {"id": identity, "time": int(time.time()), "kind": "text/plain",
                    "title": "Synthetic isolation fixture", "comments": "No real study data", "metadata": [], "tags": ["synthetic"]},
                "content": base64.b64encode(content).decode()}
    try:
        for workspace in (own, foreign):
            native("/iam", {"operation": "create-workspace", "workspace_record": {
                "id": workspace, "name": "Synthetic workspace isolation probe", "enabled": True}}, admin)
            workspaces.append(workspace)
            deadline = time.monotonic() + 30
            while True:
                status, body = probe("/config", {"operation": "getvalues", "type": "ontology", "workspace": workspace}, admin)
                if status == 200 and not body.get("error"):
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("Synthetic workspace was not ready")
                time.sleep(.5)
        username, password = "oe-synthetic-writer-" + suffix, secrets.token_urlsafe(32)
        user = native("/iam", {"operation": "create-user", "workspace": own,
            "user": {"username": username, "password": password, "roles": ["writer"]}}, admin)["user"]
        user_id = user["id"]
        assert user["roles"] == ["writer"], "Probe must use a non-administrator"
        token = native("/auth/login", {"username": username, "password": password}, None)["jwt"]
        identity = "urn:oe:workspace-probe:" + suffix
        original = b"Private synthetic fixture in foreign workspace.\n"
        native("/librarian", document(foreign, identity, original), admin)
        query = {"operation": "get-document-content", "workspace": foreign, "document-id": identity}
        before = native("/librarian", query, admin)
        own_write, own_body = probe("/librarian", document(own, identity, b"Own synthetic workspace fixture.\n"), token)
        own_read, own_content = probe("/librarian", {**query, "workspace": own}, token)
        foreign_read, _ = probe("/librarian", query, token)
        foreign_write, _ = probe("/librarian", document(foreign, identity, b"Unauthorized synthetic replacement.\n"), token)
        own_config, _ = probe("/config", {"operation": "getvalues", "type": "ontology", "workspace": own}, token)
        foreign_config, _ = probe("/config", {"operation": "getvalues", "type": "ontology", "workspace": foreign}, token)
        after = native("/librarian", query, admin)
        before_bytes, after_bytes = base64.b64decode(before["content"]), base64.b64decode(after["content"])
        report["checks"] = {"own_document_write": own_write, "own_document_read": own_read,
            "foreign_document_read": foreign_read, "foreign_document_write": foreign_write,
            "own_config_read": own_config, "foreign_config_read": foreign_config,
            "foreign_source_before_sha256": hashlib.sha256(before_bytes).hexdigest(),
            "foreign_source_after_sha256": hashlib.sha256(after_bytes).hexdigest(),
            "foreign_source_unchanged": before_bytes == after_bytes == original}
        assert own_write == own_read == own_config == 200 and not own_body.get("error")
        assert base64.b64decode(own_content["content"]) == b"Own synthetic workspace fixture.\n"
        assert foreign_read == foreign_write == foreign_config == 403
        assert before_bytes == after_bytes == original
        report.update(status="passed", principal_role="writer", own_workspace=own, foreign_workspace=foreign)
    finally:
        if user_id:
            native("/iam", {"operation": "disable-user", "workspace": own, "user_id": user_id}, admin)
        for workspace in workspaces:
            native("/iam", {"operation": "disable-workspace", "workspace_record": {"id": workspace}}, admin)
        report["cleanup"] = "Synthetic user and created workspaces disabled; evidence retained"
        output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
