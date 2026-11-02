"""Shared route registration must preserve each application's own dependencies."""
from fastapi.testclient import TestClient

from oe_studio.main import create_app
from oe_studio.settings import Settings


def test_two_apps_keep_sessions_and_project_writes_in_their_own_store(tmp_path):
    apps = [create_app(Settings(_env_file=None, data_dir=tmp_path / name,
                               database_url='', eager_jobs=True, mode='local',
                               llm_config_file=None))
            for name in ('first', 'second')]
    with TestClient(apps[0]) as first, TestClient(apps[1]) as second:
        for client, app in zip((first, second), apps):
            assert client.get('/api/v1/session', headers={
                'X-OE-Session-Token': app.state.bootstrap_token}).status_code == 200
        first_id = first.get('/api/v1/projects').json()['items'][0]['id']
        second_id = second.get('/api/v1/projects').json()['items'][0]['id']
        assert first_id != second_id
        assert first.get(f'/api/v1/projects/{second_id}').status_code == 404
        assert second.get(f'/api/v1/projects/{first_id}').status_code == 404

        created = first.post('/api/v1/projects', json={'name': 'First app only', 'domain': 'demo'})
        assert created.status_code == 201
        project_id = created.json()['id']
        assert first.get(f'/api/v1/projects/{project_id}').status_code == 200
        assert second.get(f'/api/v1/projects/{project_id}').status_code == 404

        first.cookies.clear()
        assert first.get('/api/v1/session', headers={
            'X-OE-Session-Token': apps[1].state.bootstrap_token}).status_code == 401
        assert first.get('/api/v1/projects').status_code == 401
        assert second.get('/api/v1/projects').status_code == 200
