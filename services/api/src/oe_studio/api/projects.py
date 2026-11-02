"""Projects, scope, mappings and configuration discovery."""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from .. import responses as wire
from ..db import Project
from ..llm_profiles import catalog
from ..schemas import ProjectCreate, ScopeDecision, ScopeUpload
from .dependencies import StudioDependency, project_actor
from .pagination import page
from .requests import MappingDecision, MappingSetRequest

router = APIRouter()


@router.get("/api/v1/projects", response_model=wire.Page[wire.ProjectResponse], response_model_exclude_unset=True)
def projects(studio: StudioDependency, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        allowed = None
        if studio.settings.mode == 'team':
            from ..db import ProjectMembership
            allowed = {m.project_id for m in s.scalars(select(ProjectMembership).where(ProjectMembership.account_id == actor['subject'])) if m.roles}
        return page([studio.project_body(p) for p in s.scalars(select(Project).order_by(Project.id))
                     if allowed is None or p.id in allowed], cursor, limit)


@router.post("/api/v1/projects", status_code=201, response_model=wire.ProjectResponse, response_model_exclude_unset=True)
def new_project(studio: StudioDependency, body: ProjectCreate, actor=Depends(project_actor)):
    return studio.create_project(body.name, body.domain, actor)


@router.get("/api/v1/projects/{p}", response_model=wire.ProjectResponse, response_model_exclude_unset=True)
def get_project(studio: StudioDependency, p: str, actor=Depends(project_actor)):
    with studio.db.session() as s:
        return studio.project_body(studio.project(s, p))


@router.post("/api/v1/projects/{p}/scope-decisions", status_code=201, response_model=wire.ScopeDecisionResponse, response_model_exclude_unset=True)
def scope(studio: StudioDependency, p: str, body: ScopeDecision, actor=Depends(project_actor)):
    return studio.scope_decision(p, body, actor)


@router.post("/api/v1/projects/{p}/scope", status_code=201, response_model=wire.ScopeResponse, response_model_exclude_unset=True)
def upload_scope(studio: StudioDependency, p: str, body: ScopeUpload, actor=Depends(project_actor)):
    return studio.upload_scope(p, body, actor)


@router.get("/api/v1/projects/{p}/scope", response_model=wire.ScopeResponse, response_model_exclude_unset=True)
def get_scope(studio: StudioDependency, p: str, actor=Depends(project_actor)):
    return studio.current_scope(p)


@router.get("/api/v1/projects/{p}/scopes", response_model=wire.Page[wire.ScopeResponse], response_model_exclude_unset=True)
def scopes(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        return page([studio.body(i) for i in studio.items(s, p, "scope")], cursor, limit)


@router.post("/api/v1/projects/{p}/mapping-sets", status_code=201, response_model=wire.MappingSetResponse, response_model_exclude_unset=True)
def mapping_set(studio: StudioDependency, p: str, body: MappingSetRequest, actor=Depends(project_actor)):
    return studio.draft_mappings(p, body, actor)


@router.get("/api/v1/projects/{p}/mapping-sets", response_model=wire.Page[wire.MappingSetResponse], response_model_exclude_unset=True)
def mapping_sets(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        return page([studio.body(i) for i in studio.items(s, p, "mapping_set")], cursor, limit)


@router.post("/api/v1/projects/{p}/mapping-decisions", status_code=201, response_model=wire.MappingDecisionResponse, response_model_exclude_unset=True)
def mapping_decision(studio: StudioDependency, p: str, body: MappingDecision, actor=Depends(project_actor)):
    return studio.decide_mappings(p, body, actor)


@router.get("/api/v1/projects/{p}/mapping-config", response_model=wire.MappingConfigResponse, response_model_exclude_unset=True)
def mapping_config(studio: StudioDependency, p: str, actor=Depends(project_actor)):
    from ..artifacts import digest
    with studio.db.session() as s:
        project = studio.project(s, p)
        mappings = studio.approved_mappings(s, project)
        return {"decision_id": project.data.get("assessment_mapping_decision_id"), "digest": digest(mappings),
                "scope_digest": project.data["scope_digest"], "mappings": mappings}


@router.get("/api/v1/projects/{p}/model-profiles", response_model=wire.Page[wire.ModelProfileResponse], response_model_exclude_unset=True)
def model_profiles(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
    return page(catalog(studio.settings, p), cursor, limit)


@router.get("/api/v1/projects/{p}/generation-runs", response_model=wire.Page[wire.GenerationResponse], response_model_exclude_unset=True)
def generations(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        return page([studio.body(i) for i in studio.items(s, p, "generation")], cursor, limit)


@router.get("/api/v1/projects/{p}/audit", response_model=wire.Page[wire.AuditResponse], response_model_exclude_unset=True)
def audit(studio: StudioDependency, p: str, cursor: str | None = None, limit: int = 50, actor=Depends(project_actor)):
    with studio.db.session() as s:
        studio.project(s, p)
        return page([studio.body(i) for i in studio.items(s, p, "audit")], cursor, limit)
