"""Only the two supported APIs may dispatch, including historical job snapshots."""
import asyncio
import json

import httpx
import pytest

from oe_studio.errors import Problem
from oe_studio.llm_profiles import authorize_inherited, resolve_profile
from oe_studio.llm_runtime import CompletionError, complete
from oe_studio.settings import Settings
from tests.unit.test_llm_runtime import SCHEMA, configured, response


REMOVED_PROVIDERS = ['ollama', 'openai_compatible', 'litellm_proxy', 'opencode_go']


@pytest.mark.parametrize('provider', REMOVED_PROVIDERS)
def test_removed_provider_registry_is_rejected_before_selection(provider, tmp_path, monkeypatch):
    monkeypatch.setenv('RUNTIME_TEST_API_KEY', 'synthetic-key')
    profile = configured(provider).resolved_llm_profile.copy()
    profile.pop('revision')
    path = tmp_path / 'profiles.json'
    path.write_text(json.dumps({'profiles': [profile], 'projects': {'project': ['fixture']}}))
    settings = Settings(_env_file=None, llm_config_file=path, llm_default_profile='fixture')
    with pytest.raises(Problem, match='configuration'):
        resolve_profile(settings, 'project', 'chat')


@pytest.mark.parametrize('provider', REMOVED_PROVIDERS)
def test_removed_provider_snapshot_cannot_dispatch(provider, monkeypatch):
    monkeypatch.setenv('RUNTIME_TEST_API_KEY', 'synthetic-key')
    settings = configured(provider)
    settings.llm_session_id = 'old-session'
    requests = []
    with pytest.raises(CompletionError) as caught:
        asyncio.run(complete(settings, 'safe', {}, SCHEMA,
            transport=httpx.MockTransport(lambda request: requests.append(request) or response(provider))))
    assert requests == []
    assert caught.value.record['http_attempted'] is False


def test_removed_snapshot_cannot_inherit_an_existing_profile_id(tmp_path, monkeypatch):
    monkeypatch.setenv('RUNTIME_TEST_API_KEY', 'synthetic-key')
    descriptor = configured('openai').resolved_llm_profile.copy()
    descriptor.pop('revision')
    path = tmp_path / 'profiles.json'
    path.write_text(json.dumps({'profiles': [descriptor], 'projects': {'project': ['fixture']}}))
    settings = Settings(_env_file=None, llm_config_file=path, llm_default_profile='fixture')
    with pytest.raises(Problem):
        authorize_inherited(settings, 'project', 'chat', configured('ollama').resolved_llm_profile)


def test_claude_uses_native_schema_without_tools(monkeypatch):
    monkeypatch.setenv('RUNTIME_TEST_API_KEY', 'synthetic-key')
    requests = []
    asyncio.run(complete(configured('anthropic'), 'safe system', 'source data', SCHEMA,
        transport=httpx.MockTransport(lambda request: requests.append(request) or response('anthropic'))))
    wire = json.loads(requests[0].content)
    assert wire['output_config'] == {'format': {'type': 'json_schema', 'schema': SCHEMA}}
    assert wire['system'] == 'safe system'
    assert wire['messages'] == [{'role': 'user', 'content': 'source data'}]
    assert requests[0].headers['anthropic-version'] == '2023-06-01'
    assert 'tools' not in wire and 'tool_choice' not in wire
