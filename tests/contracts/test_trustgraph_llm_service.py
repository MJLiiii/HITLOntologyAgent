"""Exercise the real TrustGraph request handler and native APIs through fake HTTP."""
import asyncio
import importlib
import json
from types import SimpleNamespace

import httpx
import pytest

from oe_studio.settings import Settings
from oe_studio.llm_profiles import Profile, _snapshot


PROFILE = _snapshot(Profile(**{'id': 'extract-fast', 'provider': 'openai', 'model': 'gpt-test',
           'base_url': 'https://provider.invalid/v1', 'api_key_env': 'TG_TEST_API_KEY', 'purposes': ['extraction'],
           'timeout': 2, 'max_output_tokens': 100, 'temperature': 0,
           'structured_output': 'json_schema', 'max_response_bytes': 8192}))


class Producer:
    def __init__(self):
        self.messages = []

    async def send(self, response, properties):
        self.messages.append((response, properties))


class Flow:
    workspace, name, id = 'private-workspace', 'frozen-run', 'shared-processor-id'

    def __init__(self, profile=PROFILE):
        self.profile = profile
        self.producer = {'response': Producer()}

    def __call__(self, key):
        markers = {'oe-llm-profile-id': self.profile['id'], 'oe-llm-profile-revision': self.profile['revision'],
                   'oe-llm-session-id': 'run-session-123'}
        return markers.get(key, self.producer.get(key))  # Bus model fields cannot override registry.


class Message:
    def __init__(self, schema):
        self.request = SimpleNamespace(system='extract', prompt='Synthetic Atlas belongs to Platform.',
                                       schema=schema, response_format='json', streaming=False)

    def value(self):
        return self.request

    def properties(self):
        return {'id': 'upstream-correlation-id'}


def processor(tmp_path, monkeypatch, response_text, profile=PROFILE, usage=True):
    module = importlib.import_module('oe_studio.integrations.trustgraph.llm_service')
    from oe_studio import llm_runtime
    path = tmp_path / 'private-bindings.json'
    path.write_text(json.dumps({'bindings': [{'workspace': Flow.workspace, 'flow': Flow.name,
                                            'profile': profile, 'session_id': 'run-session-123'}]}))
    monkeypatch.setenv('TG_TEST_API_KEY', 'private-test-key')
    requests = []

    def handler(request):
        requests.append(request)
        body = {'id': 'completion', 'object': 'chat.completion', 'created': 1,
            'model': 'gpt-test', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': response_text},
                                            'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 7, 'completion_tokens': 3, 'total_tokens': 10}}
        if profile['provider'] == 'anthropic':
            body = {'id': 'message', 'type': 'message', 'role': 'assistant', 'model': 'claude-test',
                    'content': [{'type': 'text', 'text': response_text}],
                    'stop_reason': 'end_turn', 'stop_sequence': None,
                    'usage': {'input_tokens': 7, 'output_tokens': 3}}
        if not usage:
            body.pop('usage')
        return httpx.Response(200, json=body)
    original = llm_runtime.complete

    async def complete(settings, *args, **kwargs):
        assert settings.llm_session_id == 'run-session-123'
        return await original(settings, *args, transport=httpx.MockTransport(handler), **kwargs)
    monkeypatch.setattr(module, 'complete', complete)
    service = module.ProfileLlmService(profile_bindings_file=path, settings=Settings(_env_file=None))
    return service, requests


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_real_worker_handler_wraps_array_validates_and_preserves_correlation(tmp_path, monkeypatch, provider):
    schema = {'type': 'array', 'items': {'type': 'string'}}
    profile = _snapshot(Profile(**{**{k: v for k, v in PROFILE.items() if k != 'revision'},
                                  'provider': provider, 'model': 'gpt-test' if provider == 'openai' else 'claude-test'}))
    service, requests = processor(tmp_path, monkeypatch, '{"items":["Atlas"]}', profile)
    flow = Flow(profile)
    asyncio.run(service.on_request(Message(schema), None, flow))
    response, properties = flow.producer['response'].messages[0]
    assert response.error is None
    assert json.loads(response.response) == ['Atlas']
    assert properties == {'id': 'upstream-correlation-id'}
    assert response.in_token == 7 and response.out_token == 3
    assert len(requests) == 1
    payload = json.loads(requests[0].content)
    if provider == 'openai':
        assert requests[0].url.path == '/v1/chat/completions'
        assert payload['max_completion_tokens'] == 100
        assert payload['response_format']['json_schema']['schema']['properties']['items'] == schema
        assert requests[0].headers['authorization'] == 'Bearer private-test-key'
    else:
        assert requests[0].url.path == '/v1/messages'
        assert payload['max_tokens'] == 100
        assert payload['output_config']['format']['schema']['properties']['items'] == schema
        assert requests[0].headers['x-api-key'] == 'private-test-key'
        assert 'authorization' not in requests[0].headers
    assert 'tools' not in payload


@pytest.mark.parametrize('response_text', ['{"items":[1]}', '{"items":["Atlas"],"extra":true}', '["Atlas"]'])
def test_worker_rejects_malformed_or_original_schema_invalid_output(tmp_path, monkeypatch, response_text):
    service, requests = processor(tmp_path, monkeypatch, response_text)
    flow = Flow()
    asyncio.run(service.on_request(Message({'type': 'array', 'items': {'type': 'string'}}), None, flow))
    response, properties = flow.producer['response'].messages[0]
    assert response.error is not None and response.response is None
    assert 'private-test-key' not in response.error.message
    assert len(requests) == 1


def test_worker_uses_flow_name_and_denies_unconfigured_flow_before_dispatch(tmp_path, monkeypatch):
    service, requests = processor(tmp_path, monkeypatch, '{"items":[]}')
    flow = Flow()
    flow.name = flow.id
    asyncio.run(service.on_request(Message({'type': 'array', 'items': {'type': 'string'}}), None, flow))
    response, _ = flow.producer['response'].messages[0]
    assert response.error is not None
    assert requests == []


def test_worker_context_is_cleared_after_request(tmp_path, monkeypatch):
    service, _ = processor(tmp_path, monkeypatch, '{"items":[]}')
    async def run():
        await service.on_request(Message({'type': 'array', 'items': {}}), None, Flow())
        with pytest.raises(ValueError, match='request context'):
            await service.generate_content('system', 'prompt')
    asyncio.run(run())


def test_worker_rejects_remote_schema_references_before_completion(tmp_path, monkeypatch):
    service, requests = processor(tmp_path, monkeypatch, '{"items":[]}')
    flow = Flow()
    asyncio.run(service.on_request(Message({'type': 'array', 'items': {'$ref': 'https://untrusted.invalid/schema'}}), None, flow))
    response, _ = flow.producer['response'].messages[0]
    assert response.error is not None
    assert requests == []


def test_worker_rejects_changed_frozen_profile_revision(tmp_path):
    module = importlib.import_module('oe_studio.integrations.trustgraph.llm_service')
    path = tmp_path / 'private-bindings.json'
    path.write_text(json.dumps({'bindings': [{'workspace': Flow.workspace, 'flow': Flow.name,
                                            'profile': {**PROFILE, 'model': 'changed-model'}, 'session_id': 'run'}]}))
    with pytest.raises(ValueError, match='bindings'):
        module.ProfileLlmService(profile_bindings_file=path, settings=Settings(_env_file=None))


@pytest.mark.parametrize('provider', ['opencode_go', 'ollama', 'openai_compatible'])
def test_worker_rejects_removed_provider_even_with_matching_frozen_revision(tmp_path, provider):
    from oe_studio.artifacts import digest
    module = importlib.import_module('oe_studio.integrations.trustgraph.llm_service')
    descriptor = {**{key: value for key, value in PROFILE.items() if key != 'revision'}, 'provider': provider}
    profile = {**descriptor, 'revision': digest(descriptor)}
    path = tmp_path / 'bindings.json'
    path.write_text(json.dumps({'bindings': [{'workspace': Flow.workspace, 'flow': Flow.name,
                                            'profile': profile, 'session_id': 'run-session-123'}]}))
    with pytest.raises(ValueError, match='bindings'):
        module.ProfileLlmService(profile_bindings_file=path, settings=Settings(_env_file=None))


def test_worker_rejects_remote_flow_profile_marker_mismatch_before_completion(tmp_path, monkeypatch):
    service, requests = processor(tmp_path, monkeypatch, '{"items":[]}')
    class WrongFlow(Flow):
        def __call__(self, key):
            if key == 'oe-llm-profile-revision':
                return 'changed-revision'
            return super().__call__(key)
    flow = WrongFlow()
    asyncio.run(service.on_request(Message({'type': 'array', 'items': {}}), None, flow))
    response, _ = flow.producer['response'].messages[0]
    assert response.error is not None
    assert requests == []


def test_array_envelope_rejects_root_dependent_references_before_completion(tmp_path, monkeypatch):
    service, requests = processor(tmp_path, monkeypatch, '{"items":[]}')
    flow = Flow()
    asyncio.run(service.on_request(Message({'type': 'array', 'items': {'$ref': '#'}}), None, flow))
    response, _ = flow.producer['response'].messages[0]
    assert response.error is not None
    assert requests == []


def test_worker_accepts_hash_of_original_complete_snapshot_without_float_renormalization(tmp_path):
    module = importlib.import_module('oe_studio.integrations.trustgraph.llm_service')
    profile = _snapshot(Profile(id='defaults', provider='openai', model='test', purposes=['extraction']))
    # Existing snapshots can contain a numeric default serialized as 0, while
    # revalidating the JSON normalizes it to 0.0. The signed descriptor is original.
    profile['temperature'] = 0
    from oe_studio.artifacts import digest
    profile['revision'] = digest({key: value for key, value in profile.items() if key != 'revision'})
    path = tmp_path / 'bindings.json'
    path.write_text(json.dumps({'bindings': [{'workspace': Flow.workspace, 'flow': Flow.name,
                                            'profile': profile, 'session_id': None}]}))
    service = module.ProfileLlmService(profile_bindings_file=path, settings=Settings(_env_file=None))
    assert service.profile_bindings[(Flow.workspace, Flow.name)]['profile'] == profile


def test_schema_required_profile_rejects_generic_json_without_schema_before_http(tmp_path, monkeypatch):
    service, requests = processor(tmp_path, monkeypatch, '{"name":"Atlas"}')
    flow = Flow()
    asyncio.run(service.on_request(Message(None), None, flow))
    response, _ = flow.producer['response'].messages[0]
    assert response.error is not None
    assert requests == []


@pytest.mark.parametrize('mode', ['prompt_json', 'json_object'])
def test_generic_json_object_retains_properties_in_explicit_supported_modes(tmp_path, monkeypatch, mode):
    profile = _snapshot(Profile(**{**{k: v for k, v in PROFILE.items() if k != 'revision'}, 'structured_output': mode}))
    service, requests = processor(tmp_path, monkeypatch, '{"name":"Atlas"}', profile)
    flow = Flow(profile)
    asyncio.run(service.on_request(Message(None), None, flow))
    response, _ = flow.producer['response'].messages[0]
    assert response.error is None and json.loads(response.response) == {'name': 'Atlas'}
    payload = json.loads(requests[0].content)
    assert payload.get('response_format') == ({'type': 'json_object'} if mode == 'json_object' else None)


def test_real_worker_and_rabbitmq_serialization_preserve_unknown_usage_as_null(tmp_path, monkeypatch):
    from trustgraph.base.async_rabbitmq_backend import AsyncRabbitMQProducer
    from trustgraph.base.serialization import dict_to_dataclass
    from trustgraph.schema import TextCompletionResponse
    service, requests = processor(tmp_path, monkeypatch, '{"items":["Atlas"]}', usage=False)
    class Exchange:
        async def publish(self, message, routing_key):
            self.message = message
    exchange = Exchange()
    flow = Flow()
    flow.producer['response'] = AsyncRabbitMQProducer(None, exchange, False)
    asyncio.run(service.on_request(Message({'type': 'array', 'items': {'type': 'string'}}), None, flow))
    wire = json.loads(exchange.message.body)
    decoded = dict_to_dataclass(wire, TextCompletionResponse)
    assert decoded.error is None and json.loads(decoded.response) == ['Atlas']
    assert wire['in_token'] is None and wire['out_token'] is None
    assert decoded.in_token is None and decoded.out_token is None
    assert exchange.message.headers == {'id': 'upstream-correlation-id'}
    assert len(requests) == 1
