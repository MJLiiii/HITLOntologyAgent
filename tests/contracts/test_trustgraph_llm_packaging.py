"""Worker staging contains frozen source/SDK pins and never copies secrets into the image."""
import importlib.util
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[2]


def module():
    spec = importlib.util.spec_from_file_location('prepare_tg_litellm', ROOT / 'infra/portal/prepare_litellm.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_worker_sdk_requirements_derive_versions_and_http2_extra_from_main_lock():
    prepare = module()
    lock = tomllib.loads((ROOT / 'uv.lock').read_text())
    versions = {row['name']: row['version'] for row in lock['package']}
    requirements = prepare.sdk_requirements(lock)
    for name in ('litellm', 'openai', 'httpx', 'h2', 'jsonschema', 'pydantic-settings'):
        assert f'{name}=={versions[name]}' in requirements.splitlines()
    assert all('==' in line for line in requirements.splitlines())
    assert 'fastapi' not in requirements


def test_worker_staging_changes_only_completion_and_keeps_private_config_outside_image(tmp_path):
    prepare = module()
    bindings = {'bindings': [{'workspace': 'private-workspace', 'flow': 'dedicated-run',
                              'profile': {'id': 'test', 'revision': 'sha256:' + 'a' * 64}, 'session_id': 'frozen-session'}]}
    pipeline = {'processors': [
        {'class': 'trustgraph.model.text_completion.ollama.Processor', 'params': {'id': 'text-completion', 'model': 'qwen'}},
        {'class': 'trustgraph.embeddings.ollama.Processor', 'params': {'id': 'embeddings', 'model': 'all-minilm'}},
        {'class': 'trustgraph.reranker.flashrank.Processor', 'params': {'id': 'reranker'}}]}
    import yaml
    prepare.stage_worker(ROOT, tmp_path, bindings, pipeline)
    generated = yaml.safe_load((tmp_path / 'pipeline.yaml').read_text())
    assert generated['processors'][:len(pipeline['processors'])] == pipeline['processors']
    dedicated = generated['processors'][len(pipeline['processors']):]
    assert len(dedicated) == 1
    assert dedicated[0]['class'] == 'oe_studio.integrations.trustgraph.llm_service.Processor'
    assert dedicated[0]['params']['id'] == 'studio-text-completion'
    markers = json.loads((tmp_path / 'flow-markers.json').read_text())
    assert markers['flows'][0]['completion_processor_mapping'] == {'text-completion': 'studio-text-completion'}
    assert json.loads((tmp_path / 'bindings.json').read_text()) == bindings
    assert (tmp_path / 'bindings.json').stat().st_mode & 0o777 == 0o600
    assert not (tmp_path / 'image/bindings.json').exists()
    dockerfile = (tmp_path / 'image/Dockerfile').read_text()
    assert prepare.BASE_IMAGE in dockerfile
    assert '--no-deps' in dockerfile and 'requirements.txt' in dockerfile
    compose = yaml.safe_load((tmp_path / 'compose.yaml').read_text())
    assert compose['services']['pipeline']['image'].startswith('oe-trustgraph-litellm:')
    assert 'command' not in compose['services']['pipeline']
