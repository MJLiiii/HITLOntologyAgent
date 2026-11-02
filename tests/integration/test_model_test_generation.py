"""Controlled completions exercise the persisted test-agent path, without providers."""
from uuid import uuid4
import json

import pytest
from fastapi.testclient import TestClient
from oe_studio.main import create_app
from oe_studio.settings import Settings
from oe_studio.db import Job
from tests.llm_fixtures import configure_studio_model


@pytest.fixture
def prepared(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, eager_jobs=True))
    with TestClient(app) as client:
        client.get('/api/v1/session', headers={'X-OE-Session-Token': app.state.bootstrap_token})
        project = client.get('/api/v1/projects').json()['items'][0]
        root = '/api/v1/projects/' + project['id']
        queued = client.post(root + '/proposal-jobs', json={'instruction': 'Create synthetic ontology'},
                             headers={'Idempotency-Key': str(uuid4())})
        result = client.get(queued.json()['status_url']).json()['result']
        revision = client.get(root + '/proposals/' + result['proposal_id'] + '/revisions/1').json()
        yield app, client, root, revision


def test_explicit_model_requires_bundle_and_configured_profile(prepared):
    _, client, root, revision = prepared
    body = {'proposal_id': revision['id'], 'revision': 1, 'generator_mode': 'model'}
    response = client.post(root + '/test-generation-jobs', json=body, headers={'Idempotency-Key': str(uuid4())})
    assert response.status_code == 422
    response = client.post(root + '/test-generation-jobs', json={**body, 'bundle_digest': revision['bundle_digest']},
                           headers={'Idempotency-Key': str(uuid4())})
    assert response.status_code == 422
    assert response.json()['code'] == 'model_required'


def test_model_tests_freeze_inputs_and_keep_failure_without_fallback(prepared, monkeypatch):
    app, client, root, revision = prepared
    configure_studio_model(app.state.studio, monkeypatch, model='controlled')
    app.state.settings.eager_jobs = False
    body = {'proposal_id': revision['id'], 'revision': 1, 'generator_mode': 'model',
            'bundle_digest': revision['bundle_digest']}
    response = client.post(root + '/test-generation-jobs', json=body, headers={'Idempotency-Key': str(uuid4())})
    assert response.status_code == 202, response.text
    with app.state.studio.db.session() as session:
        queued = session.get(Job, response.json()['job_id'])
        assert queued.payload['_agent_input']['bundle_digest'] == revision['bundle_digest']
        assert queued.payload['_resolved_llm_profile']['model'] == 'controlled'
    def failure(*args, **kwargs):
        from oe_studio.model import ModelGenerationError
        raise ModelGenerationError('controlled failure', {'status': 'failed', 'elapsed_seconds': .1})
    monkeypatch.setattr('oe_studio.model.ModelClient.generate', failure)
    app.state.studio.work_once()
    assert client.get(response.json()['status_url']).json()['status'] == 'failed'
    assert client.get(root + '/test-suites').json()['items'] == []
    records = client.get(root + '/generation-runs').json()['items']
    assert records[-1]['kind'] == 'test_generation'
    assert records[-1]['status'] == 'failed'


def test_stale_test_bundle_rejected_before_enqueue(prepared):
    _, client, root, revision = prepared
    response = client.post(root + '/test-generation-jobs', json={'proposal_id': revision['id'], 'revision': 1,
        'bundle_digest': 'sha256:' + '0' * 64}, headers={'Idempotency-Key': str(uuid4())})
    assert response.status_code == 409


def controlled(self, system, context, schema):
    ns = context['synthetic_namespace']
    return schema.model_validate({'tests': [{'kind': 'ask', 'scenario': 'positive',
        'query': 'ASK { ?s a <https://example.org/oe-demo/Service> }', 'expected': True,
        'fixtures_ttl': f'<{ns}example> a <https://example.org/oe-demo/CriticalService> .',
        'rationale': 'The synthetic source states critical services are services.',
        'evidence_ids': [context['evidence'][0]['id']], 'question_ids': [context['questions'][0]['id']]}]}), {
            'provider': 'controlled', 'model': 'controlled', 'elapsed_seconds': .1,
            'input_tokens': 100, 'output_tokens': 50, 'cost': None,
            'cost_missing_reason': 'Controlled response; no provider call'}


def model_request(app, client, root, revision):
    response = client.post(root + '/test-generation-jobs', json={
        'proposal_id': revision['id'], 'revision': 1, 'generator_mode': 'model',
        'bundle_digest': revision['bundle_digest']}, headers={'Idempotency-Key': str(uuid4())})
    assert response.status_code == 202, response.text
    return client.get(response.json()['status_url']).json()


def test_model_suite_requires_human_and_creates_successor_preserving_mandatory_checks(prepared, monkeypatch):
    app, client, root, revision = prepared
    configure_studio_model(app.state.studio, monkeypatch, model='controlled')
    monkeypatch.setattr('oe_studio.model.ModelClient.generate', controlled)
    result = model_request(app, client, root, revision)
    assert result['status'] == 'succeeded', result
    suite = result['result']
    assert suite['status'] == 'needs_review'
    assert suite['tests'][0]['oracle_status'] == 'needs_review'
    assert suite['generator']['model_profile_id'] == 'controlled-openai'
    assert suite['generator']['generation_run_id']
    original = client.get(root + '/proposals/' + revision['id'] + '/revisions/1').json()
    assert not original['approval_ids']
    response = client.post(root + '/test-oracle-decisions', json={'test_suite_id': suite['id'],
        'test_suite_digest': suite['digest'], 'decision': 'accept', 'rationale': 'Synthetic software verification expectation'})
    assert response.status_code == 201, response.text
    successor = response.json()
    assert successor['revision'] == 2 and successor['bundle_digest'] != revision['bundle_digest']
    assert successor['validation'] is None and not successor['approval_ids']
    with app.state.studio.db.session() as s:
        old = app.state.studio.revision(s, root.rsplit('/', 1)[-1], revision['id'], 1)
        new = app.state.studio.revision(s, root.rsplit('/', 1)[-1], revision['id'], 2)
        old_tests = json.loads(app.state.studio.artifacts.get_verified(old.data['tests']))
        new_tests = json.loads(app.state.studio.artifacts.get_verified(new.data['tests']))
        assert new_tests[:len(old_tests)] == old_tests
        assert new_tests[-1]['oracle_status'] == 'accepted'


def test_mid_generation_profile_revocation_retains_output_without_suite(prepared, monkeypatch):
    app, client, root, revision = prepared
    project = root.rsplit('/', 1)[-1]
    path = configure_studio_model(app.state.studio, monkeypatch, id='test', model='controlled',
                                  purposes=['test_generation'])
    registry = json.loads(path.read_text())
    def revoke(*args):
        registry['projects'][project] = []
        path.write_text(json.dumps(registry))
        return controlled(*args)
    monkeypatch.setattr('oe_studio.model.ModelClient.generate', revoke)
    result = model_request(app, client, root, revision)
    assert result['status'] == 'failed'
    assert client.get(root + '/test-suites').json()['items'] == []
    assert client.get(root + '/generation-runs').json()['items'][-1]['status'] == 'completed'
