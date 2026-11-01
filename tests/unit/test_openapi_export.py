import os
from pathlib import Path
import subprocess
import sys

from scripts.export_openapi import contracts, type_expression


def test_request_types_keep_required_fields_nullable_values_and_refs():
    schema = {'paths': {'/example': {'post': {'requestBody': {'content': {'application/json': {
        'schema': {'$ref': '#/components/schemas/Request'}}}}, 'responses': {'200': {'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Response'}}}}}}}}, 'components': {'schemas': {
        'Request': {'type': 'object', 'required': ['revision'], 'properties': {
            'revision': {'type': 'integer'},
            'note': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
            'condition': {'enum': ['A', 'B']}}},
        'Response': {'type': 'object', 'properties': {'diagnostics': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['diagnostics'], 'additionalProperties': False}}}}
    output = contracts(schema)
    assert '"revision": number;' in output
    assert '"note"?: (string | null);' in output
    assert '"condition"?: "A" | "B";' in output
    assert 'export type Response' in output
    assert 'response: Response;' in output
    assert 'diagnostics' in output
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
