"""Bounded, single-dispatch OpenAI and Claude APIs shared by Studio and TrustGraph."""
import asyncio
from copy import deepcopy
import json
import logging
import time

import httpx
from openai.lib._pydantic import _ensure_strict_json_schema

from .artifacts import digest
from .llm_profiles import secret_value

for _logger in ('openai', 'httpx', 'httpcore'):
    logging.getLogger(_logger).setLevel(logging.CRITICAL)


class CompletionError(ValueError):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


def _redact(value, secret):
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, '[REDACTED]')
    if isinstance(value, dict):
        return {_redact(key, secret): _redact(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, secret) for item in value]
    return value


def _strict_wire_schema(schema):
    """Use the pinned OpenAI schema converter without changing local validation."""
    schema = deepcopy(schema)

    def strip_defaults(node):
        node.pop('default', None)
        for key in ('properties', '$defs', 'definitions'):
            for child in node.get(key, {}).values():
                strip_defaults(child)
        if isinstance(node.get('items'), dict):
            strip_defaults(node['items'])
        for key in ('anyOf', 'allOf', 'oneOf'):
            for child in node.get(key, []):
                strip_defaults(child)

    strip_defaults(schema)
    return _ensure_strict_json_schema(schema, path=(), root=schema)


def _request(profile, system, context, schema):
    provider, mode = profile['provider'], profile['structured_output']
    if provider not in {'openai', 'anthropic'}:
        raise ValueError('Unsupported configured model provider')
    if mode not in {'json_schema', 'json_object', 'prompt_json'} or (provider == 'anthropic' and mode == 'json_object'):
        raise ValueError('Unsupported structured output mode')
    if schema is not None and mode != 'json_schema':
        system += '\nReturn only JSON conforming to this schema:\n' + json.dumps(schema, ensure_ascii=False)
    user = {'role': 'user', 'content': context if isinstance(context, str) else json.dumps(context, ensure_ascii=False)}
    payload = {'model': profile['model'], 'stream': False}
    base = profile['base_url'].rstrip('/')
    if provider == 'openai':
        endpoint = base + '/chat/completions'
        payload.update(messages=[{'role': 'system', 'content': system}, user],
                       max_completion_tokens=profile['max_output_tokens'])
        if schema is not None and mode == 'json_schema':
            payload['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': 'structured_output', 'strict': True, 'schema': _strict_wire_schema(schema)}}
        elif schema is not None and mode == 'json_object':
            payload['response_format'] = {'type': 'json_object'}
    else:
        endpoint = base + '/messages' if base.endswith('/v1') else base + '/v1/messages'
        payload.update(system=system, messages=[user], max_tokens=profile['max_output_tokens'])
        if schema is not None and mode == 'json_schema':
            payload['output_config'] = {'format': {'type': 'json_schema', 'schema': schema}}
    if profile.get('temperature') is not None:
        payload['temperature'] = profile['temperature']
    return endpoint, payload, system


class _BoundedClient(httpx.AsyncClient):
    """Reserve before one dispatch and bound decoded bytes before JSON parsing."""
    def __init__(self, settings, profile, payload, transport, deadline):
        super().__init__(timeout=profile['timeout'], transport=transport, follow_redirects=False, trust_env=False)
        self.settings, self.profile, self.payload = settings, profile, payload
        self.deadline = deadline
        self.http_attempted = False
        self.budget_blocked = False

    async def completion(self, endpoint, headers):
        request = self.build_request('POST', endpoint, json=self.payload, headers=headers)
        if len(request.content) > 1_048_576:
            raise ValueError('Model request exceeded the input bound')
        from .llm_budget import BudgetExceeded, reserve_from_settings
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Model completion deadline expired before reservation')
        try:
            reserve_from_settings(self.settings, self.profile, self.payload, timeout=remaining)
        except BudgetExceeded:
            self.budget_blocked = True
            raise
        if time.monotonic() >= self.deadline:
            raise TimeoutError('Model completion deadline expired before dispatch')
        self.http_attempted = True
        response = await self.send(request, stream=True)
        try:
            response.raise_for_status()
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > self.profile['max_response_bytes']:
                    raise ValueError('Model response exceeded the output bound')
                chunks.append(chunk)
            return json.loads(b''.join(chunks))
        finally:
            await response.aclose()


def _response(raw, provider, metadata):
    usage = raw.get('usage') or {}
    input_key, output_key = ('input_tokens', 'output_tokens') if provider == 'anthropic' else ('prompt_tokens', 'completion_tokens')
    counts = [usage.get(input_key), usage.get(output_key)]
    counts = [count if type(count) is int and count >= 0 else None for count in counts]
    metadata.update(returned_model=raw.get('model'), input_tokens=counts[0], output_tokens=counts[1],
                    input_tokens_source='provider' if counts[0] is not None else 'unavailable',
                    output_tokens_source='provider' if counts[1] is not None else 'unavailable',
                    usage_source='provider' if all(count is not None for count in counts) else
                    'partial' if any(count is not None for count in counts) else 'unavailable')
    if provider == 'openai':
        choice = raw['choices'][0]
        message = choice['message']
        text = message.get('content')
        finish = choice.get('finish_reason')
        invalid = bool(message.get('tool_calls') or message.get('function_call') or message.get('refusal'))
    else:
        blocks = raw['content']
        text = ''.join(block['text'] for block in blocks if block.get('type') == 'text')
        finish = 'stop' if raw.get('stop_reason') == 'end_turn' else raw.get('stop_reason')
        # Thinking is passive provider output; only final text enters the audit record.
        invalid = raw.get('stop_reason') != 'end_turn' or not blocks or any(
            block.get('type') not in {'text', 'thinking', 'redacted_thinking'} for block in blocks)
    metadata.update(raw_output=text, finish_reason=finish)
    if finish != 'stop' or invalid or not isinstance(text, str) or not text.strip():
        raise ValueError('Model response was incomplete, refused, or requested a tool')
    return text


async def complete(settings, system, context, output_schema, *, transport=None):
    """Return text plus credential-free audit metadata; validate output at the caller."""
    profile = deepcopy(getattr(settings, 'resolved_llm_profile', None))
    if not profile:
        raise ValueError('No language model configured')
    started = time.monotonic()
    deadline = started + profile['timeout']
    mode = profile['structured_output']
    metadata = {'provider': profile['provider'], 'model': profile['model'], 'model_profile_id': profile['id'],
                'model_profile_revision': profile['revision'], 'model_profile': profile,
                'session_id': getattr(settings, 'llm_session_id', None),
                'system_prompt': system, 'temperature': profile.get('temperature'),
                'seed': None, 'cost': None, 'cost_missing_reason': 'Provider did not report cost',
                'output_mode': mode if output_schema is not None else 'text',
                'effective_parameters': {key: profile.get(key) for key in (
                    'temperature', 'max_output_tokens', 'timeout', 'max_response_bytes', 'structured_output')},
                'input_tokens': None, 'output_tokens': None, 'raw_output': None, 'http_attempted': False}
    metadata['effective_parameters']['structured_output'] = metadata['output_mode']
    secret, http_client = '', None
    try:
        endpoint, payload, system = _request(profile, system, context, output_schema)
        metadata.update(prompt_digest=digest(payload), system_prompt=system)
        secret = secret_value(settings, profile.get('api_key_env'))
        if not secret:
            raise ValueError('Configured model credential is unavailable')
        headers = {'User-Agent': 'OntologyStudio/0.1.0'}
        if profile['provider'] == 'openai':
            headers['Authorization'] = 'Bearer ' + secret
        else:
            headers.update({'x-api-key': secret, 'anthropic-version': '2023-06-01'})
        async with _BoundedClient(settings, profile, payload, transport, deadline) as http_client:
            raw = await asyncio.wait_for(http_client.completion(endpoint, headers),
                                         timeout=max(0, deadline - time.monotonic()))
            metadata['http_attempted'] = http_client.http_attempted
            text = _response(raw, profile['provider'], metadata)
            if secret in text:
                raise ValueError('Model output contained a configured credential')
            metadata['elapsed_seconds'] = time.monotonic() - started
            return text, _redact(metadata, secret)
    except Exception as exc:
        message = 'Configured model unavailable or returned an invalid response: ' + type(exc).__name__
        metadata.update(status='failed', error=message, validation_errors=[],
                        elapsed_seconds=time.monotonic() - started)
        if http_client is not None:
            metadata.update(http_attempted=http_client.http_attempted,
                            failure_kind='budget' if http_client.budget_blocked else 'provider')
        raise CompletionError(message, _redact(metadata, secret)) from None
