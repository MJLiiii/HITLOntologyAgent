import json
import pytest
from oe_studio.settings import Settings
from oe_studio.errors import Problem
from oe_studio.llm_profiles import resolve_profile, profile_settings, catalog, model_configured


def configuration(tmp_path, **changes):
    spec = dict(id='local', provider='ollama', model='fixture', base_url='http://localhost:11434',
                purposes=['chat', 'proposal', 'repair', 'experiment'], structured_output='json_schema')
    spec.update(changes)
    path = tmp_path / 'profiles.json'
    path.write_text(json.dumps({'profiles': [spec], 'projects': {'project': ['local']}}))
    return Settings(_env_file=None, data_dir=tmp_path, llm_config_file=path, llm_default_profile='local')


def test_allowlist_and_revision_are_stable_and_settings_are_isolated(tmp_path):
    settings = configuration(tmp_path)
    frozen = resolve_profile(settings, 'project', 'chat')
    assert frozen['revision'].startswith('sha256:')
    assert frozen == resolve_profile(settings, 'project', 'chat', 'local')
    with pytest.raises(Problem):
        resolve_profile(settings, 'other-project', 'chat', 'local')
    with pytest.raises(Problem):
        resolve_profile(settings, 'project', 'extraction', 'local')
    scoped = profile_settings(settings, frozen, 'session')
    assert scoped.resolved_llm_profile == frozen
    assert scoped.llm_session_id == 'session'
    assert not hasattr(settings, 'resolved_llm_profile')
    configuration(tmp_path, model='new-model')
    assert resolve_profile(settings, 'project', 'chat')['revision'] != frozen['revision']
    assert scoped.resolved_llm_profile['model'] == 'fixture'


def test_catalog_is_sanitized_and_missing_key_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv('MISSING_TEST_KEY', raising=False)
    settings = configuration(tmp_path, provider='openai', model='test', base_url='https://api.openai.com/v1', api_key_env='MISSING_TEST_KEY')
    public = catalog(settings, 'project')
    assert public[0]['status'] == 'missing_credentials'
    assert 'api_key_env' not in public[0] and 'base_url' not in public[0]
    with pytest.raises(Problem):
        resolve_profile(settings, 'project', 'chat')
    monkeypatch.setenv('MISSING_TEST_KEY', 'secret-fixture')
    assert 'secret-fixture' not in json.dumps(resolve_profile(settings, 'project', 'chat'))


@pytest.mark.parametrize('changes', [{'base_url': 'https://user:password@example.com/v1'}, {'max_output_tokens': 4097}, {'api_key': 'secret'}, {'purposes': ['unknown']}])
def test_invalid_registry_is_sanitized(tmp_path, changes):
    settings = configuration(tmp_path, **changes)
    with pytest.raises(Problem) as error:
        resolve_profile(settings, 'project', 'chat')
    assert 'password' not in error.value.message and 'secret' not in error.value.message


def test_legacy_and_frozen_demo(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path, model_url='', model_name='')
    assert resolve_profile(settings, 'anything', 'chat') is None
    settings.model_url, settings.model_name = 'http://localhost:11434', 'qwen3:1.7b'
    assert resolve_profile(settings, 'anything', 'chat')['id'] == 'legacy-ollama'
    assert model_configured(settings)
    assert not model_configured(profile_settings(settings, None))
