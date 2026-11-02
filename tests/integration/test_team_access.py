"""Synthetic team authorization checks; SQLite only via the explicit test setting."""
from tests.llm_fixtures import configure_studio_model
import re
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from oe_studio import accounts
from oe_studio.db import Job, Project
from oe_studio.main import create_app
from oe_studio.settings import Settings


@pytest.fixture
def team(tmp_path):
    settings = Settings(mode='team', team_test_sqlite=True, team_origin='https://studio.example',
                        data_dir=tmp_path, eager_jobs=True)
    app = create_app(settings)
    db = app.state.studio.db
    user = accounts.create_account(db, 'member', 'synthetic test password')
    with db.session(write=True) as s:
        s.add(Project(id='private-project', name='Private synthetic project', data={}))
    actor, token, csrf = accounts.login(db, settings, user.username, 'synthetic test password', 'synthetic-peer')
    with TestClient(app, base_url='https://studio.example') as client:
        client.cookies.set('oe_session', token)
        client.headers.update({'Origin': settings.team_origin, 'X-CSRF-Token': csrf})
        yield client, db, user, actor
    db.engine.dispose()


def test_every_project_read_rejects_nonmember(team):
    client, _, _, _ = team
    for route in client.app.routes:
        if 'GET' not in getattr(route, 'methods', set()) or '/projects/{p}' not in route.path:
            continue
        path = route.path.replace('{p}', 'private-project')
        path = re.sub(r'\{revision\}', '1', path)
        path = re.sub(r'\{[^}]+\}', 'unknown', path)
        response = client.get(path)
        assert response.status_code in {403, 404}, (path, response.status_code, response.text)
        assert 'Private synthetic project' not in response.text
    assert client.get('/api/v1/projects').json()['items'] == []


def test_viewer_cannot_mutate_and_membership_removal_is_immediate(team):
    client, db, user, _ = team
    accounts.grant_project(db, user.id, 'private-project', ['viewer'])
    response = client.post('/api/v1/projects/private-project/proposal-jobs',
                           json={'instruction': 'Create a synthetic ontology', 'corpus_snapshot_id': 'synthetic'},
                           headers={'Idempotency-Key': str(uuid4())})
    assert response.status_code == 403, response.text
    assert client.get('/api/v1/projects/private-project/documents').status_code == 200
    accounts.grant_project(db, user.id, 'private-project', [])
    assert client.get('/api/v1/projects/private-project/documents').status_code in {403, 404}


def test_cookie_revocation_and_jobs_do_not_dispatch(team):
    client, db, user, actor = team
    accounts.grant_project(db, user.id, 'private-project', ['researcher'])
    with db.session(write=True) as s:
        s.add(Job(id='queued-before-revocation', project_id='private-project', kind='question',
                  idempotency_key=str(uuid4()), payload_digest='synthetic', payload={'question': 'Synthetic?'}, actor=actor))
    accounts.revoke_session(db, actor['session_id'], user.id)
    assert client.get('/api/v1/projects').status_code == 401
    client.app.state.studio.work_once()
    with db.session() as s:
        job = s.get(Job, 'queued-before-revocation')
        assert job.status == 'failed'
        assert job.result is None


def test_login_logout_exact_origin_and_csrf(team):
    client, _, _, _ = team
    client.cookies.clear()
    client.headers.pop('X-CSRF-Token', None)
    assert client.get('/api/v1/session').status_code == 401
    credentials = {'username': 'member', 'password': 'synthetic test password'}
    rejected = client.post('/api/v1/login', json=credentials, headers={'Origin': 'https://studio.example.attacker'})
    assert rejected.status_code == 403, rejected.text
    response = client.post('/api/v1/login', json=credentials)
    assert response.status_code == 200, response.text
    assert 'Secure' in response.headers['set-cookie']
    assert 'HttpOnly' in response.headers['set-cookie']
    csrf = response.json()['csrf_token']
    assert csrf and 'synthetic test password' not in response.text
    assert client.post('/api/v1/logout').status_code == 403
    assert client.post('/api/v1/logout', headers={'X-CSRF-Token': csrf}).status_code in {200, 204}
    assert client.get('/api/v1/session').status_code == 401


@pytest.fixture
def team_candidate(team, monkeypatch):
    from sqlalchemy import select
    client, db, user, actor = team
    with db.session() as session:
        project_id = session.scalar(select(Project.id).where(Project.domain == 'demo'))
    accounts.grant_project(db, user.id, project_id, ['researcher', 'reviewer', 'approver'])
    root = '/api/v1/projects/' + project_id
    project = client.get(root).json()
    assert client.post(root + '/scope-decisions', json={'scope_digest': project['scope_digest'],
        'decision': 'accept', 'rationale': 'Synthetic team workflow scope acceptance'}).status_code == 201
    def job(kind, payload):
        response = client.post(root + '/' + kind + '-jobs', json=payload,
                               headers={'Idempotency-Key': str(uuid4())})
        assert response.status_code == 202, response.text
        result = client.get(response.json()['status_url']).json()
        assert result['status'] == 'succeeded', result
        return result['result']
    proposal = job('proposal', {'instruction': 'Create neutral synthetic ontology'})
    revision = client.get(root + '/proposals/' + proposal['proposal_id'] + '/revisions/1').json()
    return client, db, user, actor, root, revision, job


def test_reviewer_accepts_oracles_but_researcher_cannot(team_candidate):
    client, db, user, _, root, revision, job = team_candidate
    suite = job('test-generation', {'proposal_id': revision['id'], 'revision': 1})
    body = {'test_suite_id': suite['id'], 'test_suite_digest': suite['digest'], 'decision': 'accept',
            'rationale': 'Synthetic software verification only; review immutable generated test expectations'}
    accounts.grant_project(db, user.id, root.rsplit('/', 1)[1], ['researcher'])
    assert client.post(root + '/test-oracle-decisions', json=body).status_code == 403
    accounts.grant_project(db, user.id, root.rsplit('/', 1)[1], ['reviewer'])
    accepted = client.post(root + '/test-oracle-decisions', json=body)
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()['revision'] == 2
    assert accepted.json()['bundle_digest'] != revision['bundle_digest']


def test_only_approver_accepts_checked_ontology(team_candidate, monkeypatch):
    client, db, user, _, root, revision, job = team_candidate
    monkeypatch.setattr('oe_studio.workflow.run_validation', lambda ttl, **kw: {
        'id': str(uuid4()), 'status': 'passed', 'bundle_digest': kw['bundle_digest'],
        'engine': 'synthetic-role-fixture', 'profile': 'rdfs', 'cases': [], 'stages': [], 'limitations': []})
    monkeypatch.setattr('oe_studio.workflow.run_assessment', lambda ttl, **kw: {
        'id': str(uuid4()), 'status': 'completed', 'bundle_digest': kw['bundle_digest'],
        'vocabulary_coverage': 1., 'vocabulary_utilisation': .5, 'strict_fitness': 1.,
        'approximate_fitness': 1., 'limitations': []})
    bundle = {'proposal_id': revision['id'], 'revision': 1, 'bundle_digest': revision['bundle_digest']}
    validation, assessment = job('validation', bundle), job('assessment', bundle)
    project = client.get(root).json()
    assert client.post(root + '/scope-decisions', json={'scope_digest': project['scope_digest'],
        'decision': 'accept', 'rationale': 'Synthetic software check only'}).status_code == 201
    submission = {'proposal_id': revision['id'], 'revision': 1, 'validation_run_id': validation['id'],
                  'required_assessment_run_ids': [assessment['id']]}
    assert client.post(root + '/review-submissions', json=submission, headers={'If-Match': '1'}).status_code == 201
    body = {**submission, 'bundle_digest': revision['bundle_digest'], 'decision': 'accept',
            'rationale': 'Synthetic authorized software decision only', 'review_policy_id': project['review_policy_id']}
    for role in ['viewer', 'researcher', 'reviewer']:
        accounts.grant_project(db, user.id, project['id'], [role])
        assert client.post(root + '/reviews', json=body).status_code == 403
    accounts.grant_project(db, user.id, project['id'], ['approver'])
    response = client.post(root + '/reviews', json=body)
    assert response.status_code == 201, response.text
    assert response.json()['actor']['subject'] == user.id


def test_queued_membership_change_blocks_model_dispatch(team, monkeypatch):
    client, db, user, actor = team
    accounts.grant_project(db, user.id, 'private-project', ['researcher'])
    with db.session(write=True) as session:
        session.add(Job(id='permission-removed', project_id='private-project', kind='question',
                        idempotency_key=str(uuid4()), payload_digest='synthetic', payload={'question': 'Synthetic?'},
                        actor={**actor, 'roles': ['researcher']}))
    accounts.grant_project(db, user.id, 'private-project', ['viewer'])
    calls = []
    monkeypatch.setattr(client.app.state.studio, 'question', lambda *args: calls.append(args))
    client.app.state.studio.work_once()
    with db.session() as session:
        job = session.get(Job, 'permission-removed')
        assert job.status == 'failed'
        assert job.result is None
    assert calls == []


def test_viewer_blocked_on_every_existing_project_write(team):
    client, db, user, _ = team
    accounts.grant_project(db, user.id, 'private-project', ['viewer'])
    for route in client.app.routes:
        if '/projects/{p}' not in route.path:
            continue
        for method in getattr(route, 'methods', set()) & {'POST', 'PUT', 'PATCH', 'DELETE'}:
            path = route.path.replace('{p}', 'private-project')
            path = re.sub(r'\{revision\}', '1', path)
            path = re.sub(r'\{[^}]+\}', 'unknown', path)
            body = {}
            if path.endswith('/reviews'):
                body = {'proposal_id': 'unknown', 'revision': 1, 'bundle_digest': 'sha256:' + 'a' * 64,
                        'validation_run_id': 'unknown', 'required_assessment_run_ids': [], 'decision': 'accept',
                        'rationale': 'Synthetic unauthorized decision', 'review_policy_id': 'unknown'}
            response = client.request(method, path, json=body, headers={'Idempotency-Key': str(uuid4())})
            assert response.status_code == 403, (method, path, response.status_code, response.text)


def test_direct_mutators_recheck_membership(team):
    from oe_studio.errors import Problem
    from oe_studio.schemas import ScopeUpload, ScopeDecision
    client, db, user, actor = team
    studio = client.app.state.studio
    accounts.grant_project(db, user.id, 'private-project', ['researcher'])
    stale = accounts.authorize_project(db, actor, 'private-project', 'researcher')
    accounts.grant_project(db, user.id, 'private-project', ['viewer'])
    calls = [lambda: studio.upload('private-project', 'Synthetic', b'Synthetic', 'v1', 'public', 'owned', stale),
             lambda: studio.upload_scope('private-project', ScopeUpload(title='Synthetic', purpose='Synthetic scope', competency_questions=[{'id': 'CQ-1', 'question': 'Synthetic question?', 'sparql_query': 'ASK {}', 'expected': True}]), stale),
             lambda: studio.scope_decision('private-project', ScopeDecision(scope_digest='sha256:' + 'a' * 64,
                            decision='accept', rationale='Synthetic scope decision'), stale),
             lambda: studio.create_job('private-project', 'question', {'question': 'Synthetic?'}, str(uuid4()), stale)]
    for call in calls:
        with pytest.raises(Problem) as failure:
            call()
        assert failure.value.status == 403


def test_queued_profile_permission_change_blocks_dispatch(team, monkeypatch):
    import json
    from oe_studio.llm_profiles import resolve_profile
    client, db, user, actor = team
    settings = client.app.state.settings
    profile_file = configure_studio_model(client.app.state.studio, monkeypatch, id='controlled',
                                         model='controlled', purposes=['chat'])
    config = json.loads(profile_file.read_text())
    accounts.grant_project(db, user.id, 'private-project', ['researcher'])
    frozen = resolve_profile(settings, 'private-project', 'chat', 'controlled')
    with db.session(write=True) as session:
        session.add(Job(id='profile-permission-removed', project_id='private-project', kind='question',
                        idempotency_key=str(uuid4()), payload_digest='synthetic',
                        payload={'question': 'Synthetic?', '_resolved_llm_profile': frozen}, actor=actor))
    config['projects'] = {}
    profile_file.write_text(json.dumps(config))
    calls = []
    monkeypatch.setattr(client.app.state.studio, 'question', lambda *args: calls.append(args))
    client.app.state.studio.work_once()
    with db.session() as session:
        job = session.get(Job, 'profile-permission-removed')
        assert job.status == 'failed'
        assert 'profile' in job.error.lower()
    assert calls == []


def test_team_proposal_requires_accepted_scope_before_enqueue(team, monkeypatch):
    from sqlalchemy import select
    client, db, user, _ = team
    with db.session() as session:
        project_id = session.scalar(select(Project.id).where(Project.domain == 'demo'))
    accounts.grant_project(db, user.id, project_id, ['researcher'])
    calls = []
    monkeypatch.setattr('oe_studio.model.ModelClient.generate', lambda *args: calls.append(args))
    response = client.post('/api/v1/projects/' + project_id + '/proposal-jobs',
                           json={'instruction': 'Unaccepted scope must not generate'},
                           headers={'Idempotency-Key': str(uuid4())})
    assert response.status_code == 409
    assert response.json()['code'] == 'scope_acceptance_required'
    assert calls == []


def test_scope_acceptance_revoked_during_model_call_retains_output_but_no_suite(team_candidate, monkeypatch):
    from oe_studio.schemas import ScopeDecision
    from tests.integration.test_model_test_generation import controlled
    client, _, _, actor, root, revision, _ = team_candidate
    studio = client.app.state.studio
    configure_studio_model(studio, monkeypatch, model='controlled')
    project = client.get(root).json()
    def reject(*args):
        studio.scope_decision(project['id'], ScopeDecision(scope_digest=project['scope_digest'],
            decision='reject', rationale='Synthetic scope revocation while a controlled model runs'), actor)
        return controlled(*args)
    monkeypatch.setattr('oe_studio.model.ModelClient.generate', reject)
    response = client.post(root + '/test-generation-jobs', json={'proposal_id': revision['id'],
        'revision': 1, 'generator_mode': 'model', 'bundle_digest': revision['bundle_digest']},
        headers={'Idempotency-Key': str(uuid4())})
    assert response.status_code == 202
    assert client.get(response.json()['status_url']).json()['status'] == 'failed'
    assert client.get(root + '/test-suites').json()['items'] == []
    assert client.get(root + '/generation-runs').json()['items'][-1]['status'] == 'completed'
