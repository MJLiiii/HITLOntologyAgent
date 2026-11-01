"""TrustGraph 2.11.1 extension sharing Studio's bounded, single-dispatch SDK.

The private binding file is loaded once at worker start. Configured workspace and
flow names select frozen profiles; bus model/temperature fields cannot select a
provider or override its bounds. Embeddings and reranking use their own services.
"""
from contextvars import ContextVar
import json
import os
from pathlib import Path

from jsonschema import validators
from trustgraph.base import LlmResult, LlmService, ParameterSpec

from ...artifacts import digest
from ...llm_profiles import Profile, profile_settings
from ...llm_runtime import complete
from ...settings import Settings

_request_context = ContextVar('studio_trustgraph_llm_request', default=None)


def _local_schema(value, wrapped_array=False):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ('$ref', '$dynamicRef', '$recursiveRef') and (not isinstance(child, str) or not child.startswith('#')):
                raise ValueError('Only local schema references are admitted')
            if wrapped_array and key in ('$ref', '$dynamicRef', '$recursiveRef') and not child.startswith(('#/$defs/', '#/definitions/')):
                raise ValueError('Array envelopes admit definition references only')
            _local_schema(child, wrapped_array)
    elif isinstance(value, list):
        for child in value:
            _local_schema(child, wrapped_array)


class LiteLLMLlmService(LlmService):
    def __init__(self, **params):
        self.settings = params.pop('settings', None) or Settings()
        path = Path(params.pop('profile_bindings_file', None) or os.environ['OE_TG_LLM_BINDINGS_FILE'])
        try:
            if path.stat().st_size > 2_097_152:
                raise ValueError('oversized worker bindings')
            rows = json.loads(path.read_text())['bindings']
            self.profile_bindings = {}
            for row in rows:
                if set(row) != {'workspace', 'flow', 'profile', 'session_id'}:
                    raise ValueError('invalid worker binding fields')
                key = row['workspace'], row['flow']
                if not all(isinstance(part, str) and 1 <= len(part) <= 120 for part in key) or key in self.profile_bindings:
                    raise ValueError('invalid or duplicate worker flow binding')
                profile = row['profile']
                descriptor = {key: value for key, value in profile.items() if key != 'revision'}
                Profile.model_validate(descriptor)
                # Hash the exact frozen descriptor. Validation can normalize
                # historical JSON numeric forms (0 -> 0.0); that must not rewrite
                # or invalidate the original signed descriptor.
                if set(descriptor) != set(Profile.model_fields) or digest(descriptor) != profile.get('revision'):
                    raise ValueError('Frozen worker profile revision changed')
                if 'extraction' not in profile['purposes']:
                    raise ValueError('worker profile must authorize extraction')
                if row['session_id'] is not None and (not isinstance(row['session_id'], str) or not 1 <= len(row['session_id']) <= 200):
                    raise ValueError('invalid frozen worker session')
                if profile['provider'] == 'opencode_go' and not row['session_id']:
                    raise ValueError('OpenCode Go requires a dedicated flow with a frozen session')
                self.profile_bindings[key] = row
            if not self.profile_bindings:
                raise ValueError('empty worker bindings')
            sessions = [row['session_id'] for row in rows if row['profile']['provider'] == 'opencode_go']
            if len(sessions) != len(set(sessions)):
                raise ValueError('OpenCode Go sessions must have separate dedicated flows')
        except (OSError, ValueError, KeyError, TypeError):
            raise ValueError('Invalid private TrustGraph LLM bindings') from None
        super().__init__(**params)
        for name in ('oe-llm-profile-id', 'oe-llm-profile-revision', 'oe-llm-session-id'):
            self.register_specification(ParameterSpec(name=name))

    async def on_request(self, msg, consumer, flow):
        # Flow.id is the shared processor ID; Flow.name is the deployed flow.
        # ContextVar keeps concurrently handled requests and their sessions apart.
        markers = {name: flow(name) for name in ('oe-llm-profile-id', 'oe-llm-profile-revision', 'oe-llm-session-id')}
        token = _request_context.set((flow.workspace, flow.name, msg.properties()['id'], markers))
        try:
            return await super().on_request(msg, consumer, flow)
        finally:
            _request_context.reset(token)

    async def generate_content(self, system, prompt, model=None, temperature=None, response_format=None, schema=None):
        context = _request_context.get()
        if context is None:
            raise ValueError('Missing TrustGraph request context')
        binding = self.profile_bindings.get(context[:2])
        if binding is None:
            raise ValueError('TrustGraph flow has no authorized extraction profile')
        try:
            markers = {'oe-llm-profile-id': binding['profile']['id'],
                       'oe-llm-profile-revision': binding['profile']['revision'],
                       'oe-llm-session-id': binding['session_id'] or ''}
            if context[3] != markers:
                raise ValueError('Remote flow profile/session markers differ from the frozen worker binding')
            if response_format == 'json' and schema is None and binding['profile']['structured_output'] == 'json_schema':
                raise ValueError('Generic JSON without a schema requires an explicit json_object or prompt_json profile')
            original = schema if schema is not None else ({'type': 'object'} if response_format == 'json' else None)
            if original is not None:
                if not isinstance(original, dict) or len(json.dumps(original).encode()) > 65_536:
                    raise ValueError('Invalid or oversized extraction schema')
                _local_schema(original, original.get('type') == 'array')
            wrapped = original is not None and original.get('type') == 'array'
            output_schema = original
            if wrapped:
                output_schema = {'type': 'object', 'properties': {'items': original},
                                 'required': ['items'], 'additionalProperties': False}
                # Local references remain rooted at the envelope for providers
                # which require an object root. Keep definitions at that root.
                for key in ('$defs', 'definitions'):
                    if key in original:
                        output_schema[key] = original[key]
                system += '\nReturn the requested JSON array inside an object with the single key "items".'
            if output_schema is not None:
                validators.validator_for(output_schema).check_schema(output_schema)
            settings = profile_settings(self.settings, binding['profile'], session_id=binding['session_id'])
            text, metadata = await complete(settings, system, prompt, output_schema)
            if output_schema is not None:
                value = json.loads(text)
                validators.validator_for(output_schema)(output_schema).validate(value)
                if wrapped:
                    value = value['items']
                    validators.validator_for(original)(original).validate(value)
                    text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
            return LlmResult(text=text, in_token=metadata.get('input_tokens'),
                             out_token=metadata.get('output_tokens'), model=binding['profile']['model'])
        except Exception:
            # LlmService sends str(exception) upstream and logs it. Never expose
            # provider exceptions, output content, credentials, or validation paths.
            raise ValueError('Bounded extraction completion failed') from None


Processor = LiteLLMLlmService
