"""Local and team sessions."""
import hmac

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import Response

from .. import responses as wire
from ..auth import require_actor
from ..errors import Problem
from ..llm_profiles import model_configured
from ..schemas import LoginRequest
from .dependencies import StudioDependency

router = APIRouter()


def team_session(studio, actor, csrf):
    from ..accounts import session_payload
    return {**session_payload(studio.db, studio.settings, actor), 'csrf_token': csrf, 'mode': 'team',
            'model_mode': 'model' if model_configured(studio.settings) else 'local',
            'integrations': {'identity': 'team_accounts'}}


@router.post('/api/v1/login', response_model=wire.SessionResponse, response_model_exclude_unset=True)
def login(studio: StudioDependency, body: LoginRequest, request: Request, response: Response):
    from ..accounts import check_origin
    from ..accounts import login as account_login
    if studio.settings.mode != 'team':
        raise Problem(404, 'not_found', 'Team sign-in is not enabled')
    check_origin(request)
    actor, token, csrf = account_login(studio.db, studio.settings, body.username, body.password,
                                      request.client.host if request.client else 'unknown')
    response.set_cookie('oe_session', token, httponly=True, samesite='strict', path='/',
                        secure=studio.settings.team_origin.startswith('https://'), max_age=studio.settings.session_hours * 3600)
    return team_session(studio, actor, csrf)


@router.post('/api/v1/logout', response_model=wire.LogoutResponse)
def logout(studio: StudioDependency, response: Response, actor=Depends(require_actor)):
    if studio.settings.mode == 'team':
        from ..accounts import revoke_session
        revoke_session(studio.db, actor['session_id'], actor['subject'])
    response.delete_cookie('oe_session', path='/')
    return {'status': 'logged_out'}


@router.get("/api/v1/session", response_model=wire.SessionResponse, response_model_exclude_unset=True)
def session(studio: StudioDependency, request: Request, response: Response, x_oe_session_token: str | None = Header(None), authorization: str | None = Header(None)):
    if studio.settings.mode == 'team':
        from ..accounts import rotate_csrf
        actor = require_actor(request)
        return team_session(studio, actor, rotate_csrf(studio.db, actor, request.cookies.get('oe_session', '')))
    host, peer = request.url.hostname, request.client.host if request.client else ""
    if host not in {"127.0.0.1", "localhost", "testserver", "::1"} or peer not in {"127.0.0.1", "::1", "testclient"}:
        raise Problem(403, "local_only", "Local session is only available on loopback")
    if authorization:
        actor = require_actor(request)
        return {"actor": actor, "mode": "local", "model_mode": "model" if model_configured(studio.settings) else "local"}
    if not (hmac.compare_digest(request.cookies.get("oe_session", ""), request.app.state.local_cookie)
            or hmac.compare_digest(x_oe_session_token or "", request.app.state.bootstrap_token)):
        raise Problem(401, "operator_session_required", "Open the private operator link printed by the local server, or enter its session token")
    response.set_cookie("oe_session", request.app.state.local_cookie, httponly=True, samesite="strict", path="/", max_age=86400)
    return {"actor": {"subject": "local-human", "kind": "human", "roles": ["researcher", "reviewer", "approver", "viewer"]},
            "mode": "local", "model_mode": "model" if model_configured(studio.settings) else "local", "integrations": {"trustgraph": "configured_on_demand" if studio.settings.trustgraph_config_file else "not_configured", "identity": "loopback_single_user"}}
