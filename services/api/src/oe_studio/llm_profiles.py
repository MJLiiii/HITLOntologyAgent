"""Server-owned, project-authorized model configuration. Snapshots never contain keys."""
from copy import deepcopy
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .artifacts import digest
from .errors import Problem

Operation = Literal['chat', 'proposal', 'repair', 'experiment', 'extraction']
ProfileId = str


class Profile(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, validate_default=True)
    id: str = Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$')
    provider: Literal['openai', 'anthropic', 'ollama', 'openai_compatible', 'litellm_proxy', 'opencode_go']
    model: str = Field(min_length=1, max_length=200, pattern=r'^[^\s]+$')
    base_url: str | None = None
    api_key_env: str | None = Field(default=None, pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    purposes: list[Operation] = Field(min_length=1, max_length=5)
    timeout: float = Field(default=45, gt=0, le=120)
    max_output_tokens: int = Field(default=4096, gt=0, le=4096)
    temperature: float | None = Field(default=0, ge=0, le=2)
    structured_output: Literal['json_schema', 'json_object', 'prompt_json'] = 'json_schema'
    max_response_bytes: int = Field(default=1048576, gt=0, le=1048576)

    @field_validator('base_url')
    @classmethod
    def safe_endpoint(cls, value):
        if value is None:
            return value
        url = urlsplit(value)
        if (not url.hostname or url.username or url.password or url.query or url.fragment
                or url.scheme not in {'http', 'https'}):
            raise ValueError('Model endpoint must be an HTTP(S) service without embedded credentials')
        return value.rstrip('/')

    @model_validator(mode='after')
    def defaults(self):
        if len(self.purposes) != len(set(self.purposes)):
            raise ValueError('Duplicate profile operations')
        defaults = {'openai': ('https://api.openai.com/v1', 'OPENAI_API_KEY'),
                    'anthropic': ('https://api.anthropic.com', 'ANTHROPIC_API_KEY'),
                    'opencode_go': ('https://opencode.ai/inference/go/openai/v1', 'OPENCODE_API_KEY')}
        if self.provider in defaults:
            endpoint, key = defaults[self.provider]
            self.base_url = self.base_url or endpoint
            self.api_key_env = self.api_key_env or key
        elif not self.base_url:
            raise ValueError('This provider requires an endpoint')
        return self


class Registry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    profiles: list[Profile] = Field(min_length=1, max_length=100)
    projects: dict[str, list[str]]

    @model_validator(mode='after')
    def unique_profiles(self):
        ids = [profile.id for profile in self.profiles]
        if len(ids) != len(set(ids)) or any(p not in ids for allowed in self.projects.values() for p in allowed):
            raise ValueError('Invalid profile references')
        return self


def _registry(settings):
    path = getattr(settings, 'llm_config_file', None)
    if not path:
        return None
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(1048577)
        if len(raw) > 1048576:
            raise ValueError('oversized')
        result = Registry.model_validate_json(raw)
        default = getattr(settings, 'llm_default_profile', None)
        if not default or default not in {p.id for p in result.profiles}:
            raise ValueError('invalid default')
        return result
    except (OSError, ValueError, TypeError):
        raise Problem(422, 'llm_configuration_invalid', 'Model profile configuration is invalid; check the server configuration') from None


def secret_value(settings, env_name):
    if not env_name:
        return ''
    if env_name in os.environ:
        return os.environ[env_name]
    # The same local dotenv source as Settings; values are never returned in metadata.
    files = getattr(settings, 'model_config', {}).get('env_file', '.env')
    if not files:
        return ''
    if isinstance(files, (str, Path)):
        files = [files]
    value = ''
    for file in files:
        value = dotenv_values(file).get(env_name, value) or ''
    return value


def _snapshot(profile):
    descriptor = profile.model_dump()
    descriptor['purposes'] = sorted(descriptor['purposes'])
    return {**descriptor, 'revision': digest(descriptor)}


def _available(settings, snapshot):
    return not snapshot.get('api_key_env') or bool(secret_value(settings, snapshot['api_key_env']))


def legacy_profile(settings):
    if not getattr(settings, 'model_url', '') or not getattr(settings, 'model_name', ''):
        return None
    return _snapshot(Profile(id='legacy-ollama', provider='ollama', model=settings.model_name,
                             base_url=settings.model_url, timeout=settings.model_timeout,
                             purposes=['chat', 'proposal', 'repair', 'experiment', 'extraction']))


def resolve_profile(settings, project_id, operation, profile_id=None):
    registry = _registry(settings)
    if registry is None:
        profile = legacy_profile(settings)
        if profile_id and (not profile or profile_id != profile['id']):
            raise Problem(422, 'unknown_model_profile', 'Unknown model profile')
        return profile
    selected = profile_id or settings.llm_default_profile
    profile = next((p for p in registry.profiles if p.id == selected), None)
    if profile is None:
        raise Problem(422, 'unknown_model_profile', 'Unknown model profile')
    if selected not in registry.projects.get(project_id, []) or operation not in profile.purposes:
        raise Problem(403, 'model_profile_forbidden', 'This model profile is not permitted for this project and operation')
    snapshot = _snapshot(profile)
    if not _available(settings, snapshot):
        raise Problem(422, 'model_credentials_missing', 'The selected model profile requires a server-side credential')
    return snapshot


def authorize_inherited(settings, project_id, operation, snapshot):
    if snapshot is None:
        return None
    # Check current permissions, but retain the exact configuration used by the origin.
    registry = _registry(settings)
    if registry:
        current = next((p for p in registry.profiles if p.id == snapshot['id']), None)
        permitted = current is not None and operation in current.purposes and snapshot['id'] in registry.projects.get(project_id, [])
    else:
        permitted = snapshot['id'] == 'legacy-ollama'
    if not permitted or operation not in snapshot['purposes'] or not _available(settings, snapshot):
        raise Problem(403, 'model_profile_forbidden', 'The originating model profile is not permitted or configured for repair')
    return deepcopy(snapshot)


def profile_settings(settings, snapshot, session_id=None):
    update = {'resolved_llm_profile': deepcopy(snapshot), 'llm_session_id': session_id}
    if snapshot:
        update.update(model_url=snapshot['base_url'], model_name=snapshot['model'], model_timeout=snapshot['timeout'])
    else:
        update.update(model_url='', model_name='')
    if hasattr(settings, 'model_copy'):
        return settings.model_copy(update=update)
    from types import SimpleNamespace
    return SimpleNamespace(**{**vars(settings), **update})


def model_configured(settings):
    if hasattr(settings, 'resolved_llm_profile'):
        return settings.resolved_llm_profile is not None
    return bool(getattr(settings, 'llm_config_file', None) or (settings.model_url and settings.model_name))


def configuration_status(settings):
    try:
        registry = _registry(settings)
        if registry:
            default = next(p for p in registry.profiles if p.id == settings.llm_default_profile)
            return 'configured_unverified' if _available(settings, _snapshot(default)) else 'missing_credentials'
        return 'configured_unverified' if legacy_profile(settings) else 'not_configured'
    except (Problem, ValueError):
        return 'configuration_error'


def catalog(settings, project_id):
    registry = _registry(settings)
    if registry:
        profiles = [_snapshot(p) for p in registry.profiles if p.id in registry.projects.get(project_id, [])]
        default = settings.llm_default_profile
    else:
        profile = legacy_profile(settings)
        profiles, default = ([profile] if profile else []), 'legacy-ollama'
    return [{**{k: p[k] for k in ('id', 'revision', 'provider', 'model', 'purposes', 'structured_output', 'max_output_tokens')},
             'status': 'configured_unverified' if _available(settings, p) else 'missing_credentials',
             'is_default': p['id'] == default} for p in sorted(profiles, key=lambda p: p['id'])]
