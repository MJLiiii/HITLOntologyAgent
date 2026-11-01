import os
from pathlib import Path
import subprocess
import sys

from scripts.export_openapi import request_types, type_expression


def test_request_types_keep_required_fields_nullable_values_and_refs():
    schema = {'paths': {'/example': {'post': {'requestBody': {'content': {'application/json': {
        'schema': {'$ref': '#/components/schemas/Request'}}}}}}}, 'components': {'schemas': {
        'Request': {'type': 'object', 'required': ['revision'], 'properties': {
            'revision': {'type': 'integer'},
            'note': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
            'condition': {'enum': ['A', 'B']}}},
        'UnusedResponse': {'type': 'object'}}}}
    output = request_types(schema)
    assert '"revision": number;' in output
    assert '"note"?: (string | null);' in output
    assert '"condition"?: "A" | "B";' in output
    assert 'UnusedResponse' not in output
    assert '"POST /example [application/json]": Request;' in output
    assert type_expression({'type': 'string', 'format': 'binary'}) == 'Blob'


def test_generated_contracts_are_current_and_exclude_runtime_secrets():
    root = Path(__file__).resolve().parents[2]
    marker = 'test-secret-must-not-enter-openapi'
    result = subprocess.run([sys.executable, 'scripts/export_openapi.py', '--check'], cwd=root,
                            env={**os.environ, 'PYTHONPATH': str(root / 'services/api/src'),
                                 'OE_MODEL_API_KEY': marker, 'OE_SERVICE_TOKEN': marker},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert marker not in (root / 'docs/openapi.json').read_text()
    assert marker not in result.stdout + result.stderr
