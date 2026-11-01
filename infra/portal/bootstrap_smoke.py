#!/usr/bin/env python3
"""Provision a synthetic user through the real, isolated TrustGraph IAM API."""
import json
from pathlib import Path
import secrets
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
runtime = HERE / "runtime"
environment = dict(line.split("=", 1) for line in (runtime / ".env").read_text().splitlines())
base = "http://127.0.0.1:18888/api/v1"


def post(path, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(base + path, data=json.dumps(body).encode(), headers=headers), timeout=40) as response:
        value = json.load(response)
    if "error" in value:
        raise RuntimeError(f"TrustGraph rejected {body.get('operation', path)}: {value['error']}")
    return value


token = environment["OE_PORTAL_BOOTSTRAP_TOKEN"]
workspaces = post("/iam", {"operation": "list-workspaces"}, token).get("workspaces", [])
if not any(row["id"] == "default" for row in workspaces):
    post("/iam", {"operation": "create-workspace", "workspace_record": {
        "id": "default", "name": "Ontology Studio synthetic smoke", "enabled": True}}, token)
credential_file = runtime / "login.json"
if not credential_file.exists():
    credentials = {"username": "oe-portal-smoke", "password": secrets.token_urlsafe(24)}
    post("/iam", {"operation": "create-user", "workspace": "default", "user": {
        **credentials, "name": "Synthetic portal smoke operator", "roles": ["admin"],
        "enabled": True, "must_change_password": False}}, token)
    credential_file.write_text(json.dumps(credentials))
    credential_file.chmod(0o600)
credentials = json.loads(credential_file.read_text())
login = post("/auth/login", credentials)
identity = post("/iam", {"operation": "whoami"}, login["jwt"])
workspaces = post("/iam", {"operation": "list-workspaces"}, login["jwt"])
proof = {"gateway": base, "authenticated": bool(login.get("jwt")),
         "identity": identity, "workspaces": workspaces}
(runtime / "authenticated-read.json").write_text(json.dumps(proof, indent=2))
print("Real IAM login and authenticated whoami/list-workspaces passed. Credentials remain in runtime/login.json.")
