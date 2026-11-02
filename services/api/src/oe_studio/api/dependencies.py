"""Resolve per-application services and enforce existing route roles."""
from typing import Annotated

from fastapi import Depends, Request

from ..auth import require_actor
from ..workflow import Studio


def get_studio(request: Request) -> Studio:
    return request.app.state.studio


StudioDependency = Annotated[Studio, Depends(get_studio)]


def project_actor(request: Request, studio: StudioDependency):
    actor = require_actor(request)
    project_id = request.path_params.get('p')
    if project_id:
        action = request.scope['route'].name
        role = 'viewer'
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            role = {'scope': 'approver', 'mapping_decision': 'reviewer', 'oracle_decision': 'reviewer',
                    'review_session': 'viewer', 'withdraw': 'approver', 'publish': 'approver',
                    'review': 'viewer', 'experiment_review': 'approver'}.get(action, 'researcher')
        if action == 'review_session':
            return studio.authorize_human(project_id, actor, 'review_participant')
        actor = studio.authorize(project_id, actor, role)
    return actor
