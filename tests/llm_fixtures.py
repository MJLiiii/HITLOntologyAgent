"""Controlled API profiles for disposable stores and mocked model transports."""
import json

from sqlalchemy import select

from oe_studio.db import Project
from oe_studio.llm_profiles import Profile, _snapshot, profile_settings


API_KEY_ENV = 'OE_TEST_MODEL_API_KEY'
API_KEY = 'synthetic-controlled-model-key'


def controlled_profile(**overrides):
    return Profile(**{
        'id': 'controlled-openai', 'provider': 'openai', 'model': 'fixture-model',
        'base_url': 'http://controlled-provider.invalid/v1', 'api_key_env': API_KEY_ENV,
        'purposes': ['chat', 'proposal', 'repair', 'experiment', 'test_generation'],
        'timeout': 10, **overrides,
    })


def configured_model_settings(settings, monkeypatch=None, **overrides):
    if monkeypatch is not None:
        monkeypatch.setenv(API_KEY_ENV, API_KEY)
    return profile_settings(settings, _snapshot(controlled_profile(**overrides)))


def configure_studio_model(studio, monkeypatch, *, secret=API_KEY, **overrides):
    """Authorize only this temporary store's current projects; never wildcard IDs."""
    profile = controlled_profile(**overrides)
    monkeypatch.setenv(profile.api_key_env, secret)
    with studio.db.session() as session:
        project_ids = list(session.scalars(select(Project.id)))
    path = studio.settings.data_dir / 'controlled-models.json'
    path.write_text(json.dumps({
        'profiles': [profile.model_dump()],
        'projects': {project_id: [profile.id] for project_id in project_ids},
    }))
    studio.settings.llm_config_file = path
    studio.settings.llm_default_profile = profile.id
    return path


def openai_response(content, *, model='fixture-model', input_tokens=None, output_tokens=None):
    return {
        'model': model,
        'choices': [{'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': input_tokens, 'completion_tokens': output_tokens},
    }
