#!/usr/bin/env python3
"""Exercise both real APIs through the portal without changing ontology state."""
import hashlib
import hmac
from http.cookiejar import CookieJar
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = "http://127.0.0.1:5183/api/v1"
client = build_opener(HTTPCookieProcessor(CookieJar()))


def request(path, body=None, headers=None, expected=200):
    headers = {"Content-Type": "application/json", **(headers or {})}
    req = Request(BASE + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with client.open(req, timeout=40) as response:
            status, data = response.status, json.load(response)
    except HTTPError as error:
        status, data = error.code, json.load(error)
    if status != expected:
        raise RuntimeError(f"{path}: expected HTTP {expected}, received {status}")
    return data


credentials = json.loads((HERE / "runtime/login.json").read_text())
native_login = request("/auth/login", credentials)
native_headers = {"Authorization": f"Bearer {native_login['jwt']}"}
identity = request("/iam", {"operation": "whoami"}, native_headers)
assert identity["user"]["username"] == credentials["username"]
request("/session", expected=401)
request("/session", headers=native_headers, expected=401)
token = hmac.new((ROOT / ".data/session.key").read_bytes(),
                 b"ontology-studio-operator-bootstrap-v1", hashlib.sha256).hexdigest()
request("/session", headers={"X-OE-Session-Token": token})
projects = request("/projects")
assert projects["items"], "Expected the existing synthetic Studio project"
print("PASS: native IAM authenticated read; native JWT does not unlock Studio; explicit Studio session reads existing projects.")
