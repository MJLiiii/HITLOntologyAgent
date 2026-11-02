"""Stage a derived pinned TrustGraph worker; never start it or call a provider.

Usage: .venv/bin/python infra/portal/prepare_llm.py --bindings PRIVATE.json
       --pipeline infra/portal/runtime/pipeline.yaml --output .runtime/multi-llm/worker

Bindings contain frozen server-owned profiles and dedicated flow/session names.
Provider credentials stay in process environment or a private compose env file.
The worker image contains source and exact SDK versions from the main uv.lock.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import shutil
import tomllib

import yaml

BASE_IMAGE = 'trustgraph/trustgraph-flow@sha256:29ab8fbb59fcb05318dc9208d946d4a1b2b74e6863099b9f752fc72ffc52bc0e'
SHARED_MODULES = ('__init__.py', 'artifacts.py', 'errors.py', 'settings.py', 'llm_profiles.py',
                  'llm_runtime.py', 'llm_budget.py', 'integrations/__init__.py',
                  'integrations/trustgraph/__init__.py', 'integrations/trustgraph/llm_service.py')


def sdk_requirements(lock):
    """Transitive locked SDK versions, including extras requested by its edges.

    The pinned upstream image uses Python 3.13 while Studio uses Python 3.12.
    Version pins are shared; pip selects wheels for the image's Python ABI.
    """
    packages = {row['name']: row for row in lock['package']}
    selected, expanded = set(), set()
    pending = [('openai', ()), ('httpx', ()), ('pydantic-settings', ()), ('jsonschema', ())]
    while pending:
        name, extras = pending.pop()
        key = name, tuple(sorted(extras))
        if key in expanded:
            continue
        expanded.add(key)
        selected.add(name)
        row = packages[name]
        edges = list(row.get('dependencies', []))
        for extra in extras:
            edges.extend(row.get('optional-dependencies', {}).get(extra, []))
        pending.extend((edge['name'], tuple(edge.get('extra', ()))) for edge in edges)
    return ''.join(f"{name}=={packages[name]['version']}\n" for name in sorted(selected))


def stage_worker(root, output, bindings, pipeline, smoke_directory=None):
    output = output.resolve()
    image = output / 'image'
    image.mkdir(parents=True, exist_ok=True)
    requirements = sdk_requirements(tomllib.loads((root / 'uv.lock').read_text()))
    (image / 'requirements.txt').write_text(requirements)
    source = root / 'services/api/src/oe_studio'
    for relative in SHARED_MODULES:
        destination = image / 'oe_studio' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, destination)
    dockerfile = f'''FROM {BASE_IMAGE}
COPY requirements.txt /opt/oe-worker/requirements.txt
RUN python3 -m pip install --no-cache-dir --no-deps --only-binary=:all: --target=/opt/oe-llm-deps -r /opt/oe-worker/requirements.txt
COPY oe_studio /opt/oe-worker/oe_studio
ENV PYTHONPATH=/opt/oe-worker:/opt/oe-llm-deps
RUN python3 -c "from oe_studio.integrations.trustgraph.llm_service import Processor"
'''
    (image / 'Dockerfile').write_text(dockerfile)
    hashes = {str(path.relative_to(image)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(image.rglob('*')) if path.is_file()}
    identity = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    tag = 'oe-trustgraph-llm:' + identity[:20]
    generated = deepcopy(pipeline)
    dedicated = []
    processor_ids = {processor['params']['id'] for processor in generated['processors']}
    processor_mapping = {}
    for processor in pipeline['processors']:
        if (processor['class'].startswith('trustgraph.model.text_completion.')
                or processor['class'] == 'bounded_ollama.Processor'):
            processor = deepcopy(processor)
            original_id = processor['params']['id']
            identifier = 'studio-' + original_id
            if identifier in processor_ids:
                raise ValueError('Dedicated completion processor ID already exists')
            processor_ids.add(identifier)
            processor_mapping[original_id] = identifier
            processor['params']['id'] = identifier
            processor['class'] = 'oe_studio.integrations.trustgraph.llm_service.Processor'
            for name in ('model', 'temperature', 'ollama'):
                processor['params'].pop(name, None)
            dedicated.append(processor)
    if not dedicated:
        raise ValueError('Pipeline has no completion processors to derive')
    generated['processors'].extend(dedicated)
    (output / 'pipeline.yaml').write_text(yaml.safe_dump(generated, sort_keys=False))
    binding_path = output / 'bindings.json'
    binding_path.write_text(json.dumps(bindings, sort_keys=True, indent=2) + '\n')
    binding_path.chmod(0o600)
    marker_rows = []
    for row in bindings['bindings']:
        markers = {'oe-llm-profile-id': row['profile']['id'],
                   'oe-llm-profile-revision': row['profile']['revision'],
                   'oe-llm-session-id': row['session_id'] or ''}
        marker_rows.append({'workspace': row['workspace'], 'flow': row['flow'], 'flow_parameters': markers,
                            'completion_processor_mapping': processor_mapping,
                            'completion_blueprint_parameters': {key: '{' + key + '}' for key in markers}})
    (output / 'flow-markers.json').write_text(json.dumps({'flows': marker_rows}, indent=2) + '\n')
    env = {'OE_TG_LLM_BINDINGS_FILE': '/smoke/llm-bindings.json',
           'PYTHONPATH': '/opt/oe-worker:/opt/oe-llm-deps:/smoke'}
    for row in bindings['bindings']:
        name = row['profile'].get('api_key_env')
        if name:
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
                raise ValueError('Invalid credential environment reference')
            env[name] = '${' + name + ':?Configure provider credential privately}'
    compose = {'services': {'pipeline': {'image': tag,
        'build': {'context': str(image)}, 'environment': env,
        'volumes': [str(output / 'pipeline.yaml') + ':/smoke/pipeline.yaml:ro',
                    str(binding_path) + ':/smoke/llm-bindings.json:ro']}}}
    if smoke_directory is not None:
        # Mount the directory so SQLite journals and locks use the shared ledger.
        compose['services']['pipeline']['volumes'].append(str(Path(smoke_directory).resolve()) + ':/smoke-budget:rw')
        env.update(OE_LLM_SMOKE_BUDGET_FILE='/smoke-budget/smoke-budget.sqlite',
                   OE_LLM_SMOKE_PRICE_FILE='/smoke-budget/verified-prices.json')
    (output / 'compose.yaml').write_text(yaml.safe_dump(compose, sort_keys=False))
    (output / 'pins.json').write_text(json.dumps({'base_image': BASE_IMAGE, 'derived_image_tag': tag,
        'uv_lock_sha256': hashlib.sha256((root / 'uv.lock').read_bytes()).hexdigest(),
        'image_files_sha256': hashes, 'sdk_requirements': requirements.splitlines()}, indent=2) + '\n')
    return tag


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bindings', type=Path, required=True)
    parser.add_argument('--pipeline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke-directory', type=Path)
    args = parser.parse_args()
    if args.bindings.stat().st_size > 2_097_152 or args.pipeline.stat().st_size > 2_097_152:
        raise ValueError('Oversized worker configuration')
    root = Path(__file__).resolve().parents[2]
    tag = stage_worker(root, args.output, json.loads(args.bindings.read_text()), yaml.safe_load(args.pipeline.read_text()), args.smoke_directory)
    print('Prepared worker image ' + tag + '; no containers started and no provider called.')


if __name__ == '__main__':
    main()
