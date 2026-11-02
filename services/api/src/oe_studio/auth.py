import hashlib
import hmac
import secrets
import os
from urllib.parse import urlparse
from fastapi import Request
from .errors import Problem


def require_actor(request: Request):
    settings = request.app.state.settings
    if settings.mode == "team":
        from .accounts import authenticate_request
        return authenticate_request(request)
    host = request.url.hostname
    peer = request.client.host if request.client else ""
    if host not in {"localhost", "127.0.0.1", "[::1]", "::1", "testserver"} or peer not in {"127.0.0.1", "::1", "testclient"}:
        raise Problem(403, "local_only", "This demo accepts loopback connections only")
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
        parsed = urlparse(origin)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "testserver"} or parsed.port not in {None, 8000, 5173, 5183}:
            raise Problem(403, "origin_forbidden", "Request origin is not the local Studio")
    authorization = request.headers.get("authorization", "")
    if authorization:
        if settings.service_token and hmac.compare_digest(authorization, "Bearer " + settings.service_token):
            return {"subject": "local-generator", "kind": "service", "roles": ["researcher", "viewer"]}
        raise Problem(401, "invalid_token", "Invalid service credential")
    cookie = request.cookies.get("oe_session", "")
    if not hmac.compare_digest(cookie, request.app.state.local_cookie):
        raise Problem(401, "session_required", "Open the local Studio session first")
    return {"subject": "local-human", "kind": "human", "roles": ["researcher", "reviewer", "approver", "viewer"]}


def init_cookie(data_dir):
    path = data_dir / "session.key"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(secrets.token_bytes(32))
    except FileExistsError:
        pass
    return hmac.new(path.read_bytes(), b"ontology-studio-local-human-v2", hashlib.sha256).hexdigest()


def bootstrap_token(data_dir):
    init_cookie(data_dir)
    return hmac.new((data_dir / "session.key").read_bytes(), b"ontology-studio-operator-bootstrap-v1", hashlib.sha256).hexdigest()


def human(actor):
    if actor["kind"] != "human" or "approver" not in actor["roles"]:
        raise Problem(403, "human_required", "Only an authorized human can approve or publish")
