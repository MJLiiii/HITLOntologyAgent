"""Liveness and dependency readiness."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .. import responses as wire
from ..db import Project
from .dependencies import StudioDependency

router = APIRouter()


@router.get("/health/live", response_model=wire.LiveResponse, response_model_exclude_unset=True)
@router.get("/api/v1/health/live", response_model=wire.LiveResponse, response_model_exclude_unset=True)
def live(studio: StudioDependency):
    return {"status": "ok"}


@router.get("/health/ready", response_model=wire.ReadyResponse, response_model_exclude_unset=True, responses={503: {"model": wire.ReadyResponse}})
@router.get("/api/v1/health/ready", response_model=wire.ReadyResponse, response_model_exclude_unset=True, responses={503: {"model": wire.ReadyResponse}})
def ready(studio: StudioDependency):
    from sqlalchemy.exc import SQLAlchemyError

    from ..health import dependencies
    checks = dependencies(studio)
    try:
        with studio.db.session() as s:
            s.execute(select(Project.id).limit(1))
        checks["database"] = "available"
    except SQLAlchemyError:
        checks["database"] = "unavailable"
    available = all(value in {"available", "not_configured", "configured_unverified"} for value in checks.values())
    return JSONResponse(status_code=200 if available else 503,
                        content=wire.ReadyResponse.model_validate({"status": "ready" if available else "not_ready", "mode": studio.settings.mode, **checks,
                                 "trustgraph": "configured_on_demand" if studio.settings.trustgraph_config_file else "not_configured", "shared_auth": "team_accounts" if studio.settings.mode == 'team' else "not_configured"}).model_dump())
