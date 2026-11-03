from tests.llm_fixtures import API_KEY, API_KEY_ENV, controlled_profile
import json
from uuid import uuid4
from oe_studio.db import Job
from oe_studio.llm_profiles import resolve_profile
from tests.integration.test_workflow import client as workflow_client, project

client = workflow_client


def configure(client, tmp_path, monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, API_KEY)
    p = project(client)['id']
    specs = [controlled_profile(id=name, model=name, purposes=['chat', 'proposal', 'repair', 'experiment']).model_dump() for name in ('alpha', 'beta')]
    path = tmp_path / 'models.json'
    path.write_text(json.dumps({'profiles': specs, 'projects': {p: ['alpha']}}))
    settings = client.app.state.settings
    settings.llm_config_file, settings.llm_default_profile = path, 'alpha'
    return p, path


def test_catalog_pagination_authorization_and_invalid_uuid(client, tmp_path, monkeypatch):
    p, _ = configure(client, tmp_path, monkeypatch)
    root = f'/api/v1/projects/{p}'
    response = client.get(root + '/model-profiles?limit=1')
    assert response.status_code == 200, response.text
    assert [p['id'] for p in response.json()['items']] == ['alpha']
    assert 'base_url' not in response.text
    for profile, status in [('beta', 403), ('missing', 422)]:
        result = client.post(root + '/question-jobs', json={'question': 'What is a service?', 'model_profile_id': profile}, headers={'Idempotency-Key': str(uuid4())})
        assert result.status_code == status, result.text
    result = client.post(root + '/question-jobs', json={'question': 'What is a service?', 'conversation_id': 'not-a-uuid'}, headers={'Idempotency-Key': str(uuid4())})
    assert result.status_code == 422


def test_enqueued_profile_and_session_survive_config_change_and_idempotency(client, tmp_path, monkeypatch):
    p, path = configure(client, tmp_path, monkeypatch)
    studio = client.app.state.studio
    studio.settings.eager_jobs = False
    # Fixture's background worker is disabled because it started in eager mode.
    conversation = str(uuid4())
    key = str(uuid4())
    body = {'question': 'What is a service?', 'conversation_id': conversation}
    url = f'/api/v1/projects/{p}/question-jobs'
    result = client.post(url, json=body, headers={'Idempotency-Key': key})
    assert result.status_code == 202, result.text
    job_id = result.json()['job_id']
    with studio.db.session() as session:
        payload = session.get(Job, job_id).payload
        assert payload['_resolved_llm_profile']['model'] == 'alpha'
        frozen_session = payload['_llm_session_id']
    data = json.loads(path.read_text())
    data['profiles'][0]['model'] = 'redirected-model'
    path.write_text(json.dumps(data))
    again = client.post(url, json=body, headers={'Idempotency-Key': key})
    assert again.json()['job_id'] == job_id
    seen = []
    def generate(self, system, context, schema):
        seen.append((self.settings.resolved_llm_profile, self.settings.llm_session_id))
        raise ValueError('Synthetic stop before network')
    monkeypatch.setattr('oe_studio.model.ModelClient.generate', generate)
    studio.execute_job(job_id)
    assert seen[0][0]['model'] == 'alpha'
    assert seen[0][1] == frozen_session
    assert client.get('/api/v1/jobs/' + job_id).json()['status'] == 'failed'
    assert project(client)['approved_version_id'] is None


def test_demo_experiment_rejects_model_selection(client, tmp_path, monkeypatch):
    p, _ = configure(client, tmp_path, monkeypatch)
    response = client.post(f'/api/v1/projects/{p}/experiment-jobs', json={'protocol_id': 'demo-v1', 'model_profile_id': 'alpha'}, headers={'Idempotency-Key': str(uuid4())})
    assert response.status_code == 422, response.text


def test_repair_inherits_original_revision_and_allows_explicit_permitted_override(client, tmp_path, monkeypatch):
    p, path = configure(client, tmp_path, monkeypatch)
    studio = client.app.state.studio
    studio.settings.eager_jobs = False
    original = resolve_profile(studio.settings, p, 'proposal')
    with studio.db.session(write=True) as session:
        generation = studio.add(session, p, 'generation', {'model_profile': original}, 'completed')
        proposal = studio.add(session, p, 'proposal', {'generation_run_id': generation.id, 'origin': 'model'})
        proposal_id = proposal.id
    data = json.loads(path.read_text())
    data['profiles'][0]['model'] = 'changed-alpha'
    data['projects'][p].append('beta')
    path.write_text(json.dumps(data))
    studio.settings.llm_default_profile = 'beta'
    body = {'proposal_id': proposal_id, 'revision': 1, 'bundle_digest': 'fixture'}
    for extra, expected in [({}, original), ({'model_profile_id': 'beta'}, resolve_profile(studio.settings, p, 'repair', 'beta'))]:
        result = client.post(f'/api/v1/projects/{p}/repair-jobs', json={**body, **extra}, headers={'Idempotency-Key': str(uuid4())})
        assert result.status_code == 202, result.text
        with studio.db.session() as session:
            assert session.get(Job, result.json()['job_id']).payload['_resolved_llm_profile'] == expected
    data['projects'][p].remove('alpha')
    path.write_text(json.dumps(data))
    result = client.post(f'/api/v1/projects/{p}/repair-jobs', json=body, headers={'Idempotency-Key': str(uuid4())})
    assert result.status_code == 403, result.text


def test_health_is_configuration_only(client, tmp_path, monkeypatch):
    configure(client, tmp_path, monkeypatch)
    monkeypatch.setattr('oe_studio.health.engine_readiness', lambda *a: {'jena': 'available', 'ontocheck': 'available'})
    monkeypatch.setattr('httpx.Client.get', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('Health must not query a model')))
    from oe_studio.health import dependencies
    assert dependencies(client.app.state.studio)['model'] == 'configured_unverified'


def test_gui_catalog_selections_freeze_each_model_and_reject_missing_credentials(client, tmp_path, monkeypatch):
    """Selecting a second model must not silently enqueue the provider's default."""
    from oe_studio.llm_profiles import Profile

    p = project(client)['id']
    root = f'/api/v1/projects/{p}'
    monkeypatch.setenv('GUI_OPENAI_TEST_KEY', 'synthetic-openai-key')
    monkeypatch.setenv('GUI_CLAUDE_TEST_KEY', 'synthetic-claude-key')
    monkeypatch.delenv('GUI_MISSING_TEST_KEY', raising=False)
    models = [('terra', 'openai', 'gpt-6.1-terra'), ('sol', 'openai', 'gpt-6.1-sol'),
              ('sonnet', 'anthropic', 'claude-sonnet-5-5'), ('opus', 'anthropic', 'claude-opus-5-5')]
    profiles = [Profile(id=name, provider=provider, model=model, purposes=['chat'], temperature=None,
                        api_key_env='GUI_OPENAI_TEST_KEY' if provider == 'openai' else 'GUI_CLAUDE_TEST_KEY').model_dump()
                for name, provider, model in models]
    profiles.append({**profiles[-1], 'id': 'unavailable', 'api_key_env': 'GUI_MISSING_TEST_KEY'})
    profiles.append({**profiles[0], 'id': 'other-project'})
    path = tmp_path / 'gui-models.json'
    path.write_text(json.dumps({'profiles': profiles, 'projects': {p: [m[0] for m in models] + ['unavailable']}}))
    studio = client.app.state.studio
    studio.settings.llm_config_file = path
    studio.settings.llm_default_profile = 'terra'
    studio.settings.eager_jobs = False

    listed, cursor = [], None
    while True:
        response = client.get(root + '/model-profiles', params={'limit': 2, **({'cursor': cursor} if cursor else {})})
        assert response.status_code == 200
        page = response.json()
        listed.extend(page['items'])
        cursor = page['next_cursor']
        if not cursor:
            break
    assert {item['id'] for item in listed} == {'terra', 'sol', 'sonnet', 'opus', 'unavailable'}
    assert {item['id'] for item in listed if item['is_default']} == {'terra'}
    assert next(item['status'] for item in listed if item['id'] == 'unavailable') == 'missing_credentials'
    assert all('base_url' not in item and 'api_key_env' not in item for item in listed)

    for name, provider, model in models:
        conversation = str(uuid4())
        response = client.post(root + '/question-jobs', json={
            'question': 'Who owns Atlas?', 'conversation_id': conversation, 'model_profile_id': name,
        }, headers={'Idempotency-Key': str(uuid4())})
        assert response.status_code == 202, response.text
        with studio.db.session() as session:
            payload = session.get(Job, response.json()['job_id']).payload
            frozen = payload['_resolved_llm_profile']
            assert (frozen['id'], frozen['provider'], frozen['model']) == (name, provider, model)
            assert frozen['revision'] == next(item['revision'] for item in listed if item['id'] == name)
            assert payload['conversation_id'] == conversation
            assert 'synthetic-openai-key' not in json.dumps(payload)
            assert 'synthetic-claude-key' not in json.dumps(payload)
    for name, status in [('unavailable', 422), ('other-project', 403)]:
        response = client.post(root + '/question-jobs', json={'question': 'Synthetic?', 'model_profile_id': name},
                               headers={'Idempotency-Key': str(uuid4())})
        assert response.status_code == status
    assert project(client)['approved_version_id'] is None
