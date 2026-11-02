"""Opt-in PostgreSQL checks; only scripts/check_postgres.py provisions the isolated server."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Barrier
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

pytestmark = [pytest.mark.live, pytest.mark.skipif(not os.environ.get('OE_POSTGRES_CHECK_URL'),
                                                   reason='run scripts/check_postgres.py for an isolated PostgreSQL server')]
ROOT = Path(__file__).resolve().parents[2]
HUMAN_FIXTURE = {'kind': 'human', 'subject': 'synthetic-postgres-test-reviewer', 'roles': ['approver', 'researcher']}


def migrate(url, data_dir):
    env = {**os.environ, 'OE_DATABASE_URL': url.render_as_string(hide_password=False), 'OE_DATA_DIR': str(data_dir)}
    result = subprocess.run([sys.executable, 'scripts/migrate.py'], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, (result.stdout + result.stderr).replace(url.password or 'NO_SECRET', '<redacted>')


@pytest.fixture
def pg_case(request, monkeypatch):
    url = make_url(os.environ['OE_POSTGRES_CHECK_URL'])
    state = Path(os.environ['OE_POSTGRES_CHECK_STATE']).resolve()
    owner = json.loads((state / 'owner.json').read_text())
    assert owner['nonce'] == os.environ['OE_POSTGRES_CHECK_OWNER']
    assert (url.host, url.port, url.database) == ('127.0.0.1', 54329, 'ontology_studio')
    name = 'oe_check_' + re.sub('[^a-z0-9_]', '_', request.node.name.lower())[:32] + '_' + uuid4().hex[:8]
    admin = create_engine(url, isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    admin.dispose()
    case_url, data_dir = url.set(database=name), state / 'cases' / name
    data_dir.mkdir(parents=True)
    migrate(case_url, data_dir)
    monkeypatch.setenv('OE_DATABASE_URL', case_url.render_as_string(hide_password=False))
    monkeypatch.setenv('OE_DATA_DIR', str(data_dir))
    from fastapi.testclient import TestClient
    from oe_studio.db import Base
    from oe_studio.main import create_app
    from oe_studio.settings import Settings
    monkeypatch.setattr('oe_studio.workflow.run_validation', lambda ttl, **kw: {
        'id': str(uuid4()), 'status': 'passed', 'bundle_digest': kw['bundle_digest'],
        'engine': 'postgres-contract-fixture', 'profile': 'rdfs', 'cases': [], 'stages': [], 'limitations': []})
    monkeypatch.setattr('oe_studio.workflow.run_assessment', lambda ttl, **kw: {
        'id': str(uuid4()), 'status': 'completed', 'bundle_digest': kw['bundle_digest'],
        'vocabulary_coverage': 1., 'vocabulary_utilisation': .5, 'strict_fitness': 1.,
        'approximate_fitness': 1., 'limitations': []})
    settings = Settings(data_dir=data_dir, database_url=case_url.render_as_string(hide_password=False),
                        eager_jobs=True, model_url='', model_name='', service_token='')
    app = create_app(settings)
    with app.state.studio.db.engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0002'
    with TestClient(app) as client:
        assert client.get('/api/v1/session', headers={'X-OE-Session-Token': app.state.bootstrap_token}).status_code == 200
        yield client, case_url, data_dir
    app.state.studio.db.engine.dispose()
    # Public synthetic verification metadata only; no URL, password or session key.
    (state / (name + '.json')).write_text(json.dumps({'database': name, 'data_relative': str(data_dir.relative_to(state)),
                                                    'test': request.node.name, 'schema_matches_models': True}, indent=2))


def approved_candidate(client):
    project = client.get('/api/v1/projects').json()['items'][0]
    base = f"/api/v1/projects/{project['id']}"
    def job(kind, payload):
        response = client.post(f'{base}/{kind}-jobs', json=payload, headers={'Idempotency-Key': str(uuid4())})
        assert response.status_code == 202, response.text
        result = client.get('/api/v1/jobs/' + response.json()['job_id']).json()
        assert result['status'] == 'succeeded', result
        return result['result']
    proposal = job('proposal', {'corpus_snapshot_id': project['corpus_snapshot_id'], 'instruction': 'Create synthetic seed ontology'})
    revision = client.get(f"{base}/proposals/{proposal['proposal_id']}/revisions/1").json()
    bundle = {'proposal_id': proposal['proposal_id'], 'revision': 1, 'bundle_digest': revision['bundle_digest']}
    validation, assessment = job('validation', bundle), job('assessment', bundle)
    assert client.post(base + '/scope-decisions', json={'scope_digest': project['scope_digest'], 'decision': 'accept',
                                                       'rationale': 'Synthetic automated PostgreSQL test fixture only'}).status_code == 201
    submission = {'proposal_id': proposal['proposal_id'], 'revision': 1, 'validation_run_id': validation['id'],
                  'required_assessment_run_ids': [assessment['id']]}
    assert client.post(base + '/review-submissions', json=submission, headers={'If-Match': '1'}).status_code == 201
    review = client.post(base + '/reviews', json={**submission, 'bundle_digest': revision['bundle_digest'],
        'decision': 'accept', 'rationale': 'Synthetic software test approval, not a study observation',
        'review_policy_id': project['review_policy_id']})
    assert review.status_code == 201, review.text
    return project['id'], {**bundle, 'approval_ids': [review.json()['id']], 'expected_head': None}


def assert_single_release(studio, project_id):
    with studio.db.session() as session:
        project = studio.project(session, project_id)
        versions = [v for v in studio.items(session, project_id, 'version') if v.status == 'approved']
        assert len(versions) == 1 and project.approved_version_id == versions[0].id
        assert project.pending_publication_id is None
        assert studio.git.head(project_id) == versions[0].data['commit']


def test_postgres_migrations_and_verified_existing_schema_adoption(pg_case):
    client, url, data_dir = pg_case
    studio = client.app.state.studio
    before = client.get('/api/v1/projects').json()
    with studio.db.engine.begin() as connection:
        for name in ('login_throttles', 'project_memberships', 'account_sessions', 'accounts'):
            connection.exec_driver_sql(f'DROP TABLE {name}')
        connection.exec_driver_sql('DROP TABLE alembic_version')
    migrate(url, data_dir)
    assert client.get('/api/v1/projects').json() == before
    with studio.db.engine.connect() as connection:
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0002'


def test_postgres_two_independent_publishers_advance_only_once(pg_case):
    from oe_studio.errors import Problem
    from oe_studio.schemas import PublishRequest
    from oe_studio.workflow import Studio
    client, _, _ = pg_case
    project_id, payload = approved_candidate(client)
    first = client.app.state.studio
    second = Studio(first.settings)
    barrier = Barrier(2)
    def publish(studio):
        barrier.wait(timeout=10)
        try:
            studio.publish(project_id, PublishRequest(**payload), str(uuid4()), HUMAN_FIXTURE)
            return 202
        except Problem as exc:
            return exc.status
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(publish, (first, second)))
        assert sorted(results) == [202, 409]
        assert_single_release(second, project_id)
    finally:
        second.db.engine.dispose()


@pytest.mark.parametrize('stage', ['reserved', 'commit_created', 'ref_advanced', 'finalized'])
def test_postgres_fresh_instance_recovers_publication(pg_case, monkeypatch, stage):
    from oe_studio.schemas import PublishRequest
    from oe_studio.workflow import Studio
    client, _, _ = pg_case
    project_id, payload = approved_candidate(client)
    original = client.app.state.studio
    def stop(point):
        if point == stage:
            raise RuntimeError('synthetic process interruption')
    monkeypatch.setattr(original, 'publication_checkpoint', stop)
    with pytest.raises(RuntimeError, match='synthetic'):
        original.publish(project_id, PublishRequest(**payload), 'interrupted-publication', HUMAN_FIXTURE)
    restarted = Studio(original.settings)
    try:
        restarted.reconcile_pending()
        assert_single_release(restarted, project_id)
        restarted.reconcile_pending()
        assert_single_release(restarted, project_id)
    finally:
        restarted.db.engine.dispose()


def test_postgres_team_account_authority_and_revocation(pg_case):
    from oe_studio import accounts
    from oe_studio.errors import Problem
    from oe_studio.settings import Settings
    client, url, data_dir = pg_case
    db = client.app.state.studio.db
    settings = Settings(mode='team', data_dir=data_dir, database_url=url.render_as_string(hide_password=False),
                        team_origin='https://studio.example')
    user = accounts.create_account(db, 'synthetic-team-member', 'synthetic password only')
    project_id = client.get('/api/v1/projects').json()['items'][0]['id']
    accounts.grant_project(db, user.id, project_id, ['researcher'])
    actor, token, csrf = accounts.login(db, settings, user.username, 'synthetic password only', 'synthetic-peer')
    assert accounts.rotate_csrf(db, actor, token) == csrf
    assert accounts.rotate_csrf(db, actor, token) == csrf
    assert accounts.authorize_project(db, actor, project_id, 'viewer')['subject'] == user.id
    with pytest.raises(Problem):
        accounts.authorize_project(db, actor, project_id, 'approver')
    accounts.reset_password(db, user.id, 'replacement synthetic password')
    with pytest.raises(Problem):
        accounts.authorize_project(db, actor, project_id, 'researcher')
