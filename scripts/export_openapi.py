"""Export deterministic request, response and operation contracts from FastAPI."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def type_expression(schema):
    if '$ref' in schema:
        prefix = '#/components/schemas/'
        reference = schema['$ref']
        if not reference.startswith(prefix) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*', reference[len(prefix):]):
            raise ValueError(f'Unsupported schema reference {reference!r}')
        return reference[len(prefix):].replace('-', '_')
    if 'const' in schema:
        return json.dumps(schema['const'])
    if 'enum' in schema:
        return ' | '.join(json.dumps(value) for value in schema['enum']) or 'never'
    for keyword, separator in (('anyOf', ' | '), ('oneOf', ' | '), ('allOf', ' & ')):
        if keyword in schema:
            return '(' + separator.join(type_expression(value) for value in schema[keyword]) + ')'
    kind = schema.get('type')
    if isinstance(kind, list):
        return '(' + ' | '.join(type_expression({**schema, 'type': value}) for value in kind) + ')'
    if kind == 'null':
        return 'null'
    if kind == 'boolean':
        return 'boolean'
    if kind in ('number', 'integer'):
        return 'number'
    if kind == 'string':
        return 'Blob' if schema.get('format') == 'binary' else 'string'
    if kind == 'array':
        return 'Array<' + type_expression(schema.get('items', {})) + '>'
    if kind == 'object' or 'properties' in schema:
        fields = []
        for name, value in sorted(schema.get('properties', {}).items()):
            optional = '' if name in schema.get('required', []) else '?'
            fields.append(f'{json.dumps(name)}{optional}: {type_expression(value)};')
        additional = schema.get('additionalProperties')
        if additional is True or isinstance(additional, dict):
            fields.append('[key: string]: ' + type_expression(additional if isinstance(additional, dict) else {}) + (' | undefined' if type_expression(additional if isinstance(additional, dict) else {}) == 'JsonValue' or any(name not in schema.get('required', []) for name in schema.get('properties', {})) else '') + ';')
        return '{ ' + ' '.join(fields) + ' }' if fields else ('Record<string, never>' if additional is False else 'Record<string, JsonValue>')
    if kind is not None:
        raise ValueError(f'Unsupported JSON schema type {kind!r}')
    return 'JsonValue'


def contracts(schema):
    definitions = schema.get('components', {}).get('schemas', {})
    names = [name.replace('-', '_') for name in definitions]
    if len(names) != len(set(names)):
        raise ValueError('Schema names collide after TypeScript normalization')
    lines = ['/** Generated from the actual FastAPI OpenAPI schema. Do not edit.',
             ' * Runtime validation constraints remain enforced by FastAPI. */', '']
    if 'JsonValue' not in definitions:
        lines.append('export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };')
    for name, definition in sorted(definitions.items()):
        lines.append(f"export type {name.replace('-', '_')} = {type_expression(definition)};")
    requests, operations, jobs = {}, [], {}
    for path, methods in sorted(schema['paths'].items()):
        for method, operation in sorted(methods.items()):
            if method not in {'get', 'post', 'put', 'patch', 'delete', 'options', 'head'}:
                continue
            key = f'{method.upper()} {path}'
            fields = []
            for location, field in [('path', 'path'), ('query', 'query'), ('header', 'headers')]:
                params = [value for value in operation.get('parameters', []) if value['in'] == location]
                obj = {'type': 'object', 'properties': {value['name']: value['schema'] for value in params},
                       'required': [value['name'] for value in params if value.get('required')], 'additionalProperties': False}
                fields.append(f'{field}: {type_expression(obj)};')
            content = operation.get('requestBody', {}).get('content', {})
            bodies = []
            for media_type, body in sorted(content.items()):
                requests[f'{key} [{media_type}]'] = type_expression(body['schema'])
                bodies.append('FormData' if media_type == 'multipart/form-data' else type_expression(body['schema']))
            fields.append('body: ' + (' | '.join(bodies) if bodies else 'never') + ';')
            fields.append('bodyRequired: ' + ('true' if operation.get('requestBody', {}).get('required') else 'false') + ';')
            responses = {}
            for status, response in sorted(operation['responses'].items()):
                variants = [type_expression(value.get('schema', {})) for value in response.get('content', {}).values()]
                responses[status] = ' | '.join(dict.fromkeys(variants)) or 'void'
            success = ' | '.join(dict.fromkeys(value for status, value in responses.items() if status.startswith('2')))
            if not success:
                raise ValueError(f'No successful response declared for {key}')
            if 'x-job-kind' in operation:
                if success != 'JobRefResponse':
                    raise ValueError(f'Job operation {key} does not return JobRefResponse')
                discriminator = definitions['JobResponse']['discriminator']
                ref = discriminator['mapping'].get(operation['x-job-kind'])
                if not ref:
                    raise ValueError(f'Unknown job kind for {key}')
                result = definitions[ref.rsplit('/', 1)[-1]]['properties']['result']
                variants = [value for value in result.get('anyOf', [result]) if value.get('type') != 'null']
                jobs[key] = ' | '.join(type_expression(value) for value in variants)
            elif success == 'JobRefResponse':
                raise ValueError(f'Missing job kind for {key}')
            fields.append(f'response: {success};')
            fields.append('responses: { ' + ' '.join(f'{json.dumps(status)}: {value};' for status, value in responses.items()) + ' };')
            operations.append(f'  {json.dumps(key)}: {{ ' + ' '.join(fields) + ' };')
    lines.extend(['', 'export interface ApiRequestBodies {'])
    lines.extend(f'  {json.dumps(key)}: {value};' for key, value in requests.items())
    lines.extend(['}', '', 'export interface ApiOperations {', *operations, '}', '', 'export interface ApiJobResults {'])
    lines.extend(f'  {json.dumps(key)}: {value};' for key, value in jobs.items())
    lines.extend(['}', ''])
    return '\n'.join(lines)


# Public view names are aliases only; every field originates in OpenAPI.
ALIASES = {
    'Project': 'ProjectResponse', 'Session': 'SessionResponse', 'Version': 'VersionResponse',
    'SourceDocument': 'DocumentResponse', 'Evidence': 'EvidenceResponse', 'Proposal': 'RevisionResponse',
    'Revision': 'RevisionResponse', 'ValidationReport': 'ValidationReportResponse',
    'AssessmentReport': 'AssessmentReportResponse', 'Answer': 'AnswerResponse', 'JobRef': 'JobRefResponse',
    'Experiment': 'ExperimentResponse', 'TestSpec': 'TestSpecResponse', 'TestSuite': 'TestSuiteResponse',
    'ReviewTimingEvent': 'ReviewTimingResponse', 'AuditEvent': 'AuditResponse', 'Publication': 'PublicationResponse',
    'ReviewDecision': 'ReviewResponse', 'ScopeVersion': 'ScopeResponse', 'AssessmentMapping': 'ApprovedMapping',
    'MappingEntry': 'MappingDraft', 'MappingSet': 'MappingSetResponse', 'MappingConfig': 'MappingConfigResponse',
    'SyntheticTask': 'SyntheticTaskResponse', 'TrustGraphPreparation': 'TrustGraphPreparationResponse',
    'TrustGraphIngestion': 'TrustGraphIngestionResponse', 'TrustGraphIngestions': 'TrustGraphIngestionsResponse',
    'TrustGraphRegisteredChunks': 'TrustGraphRegisteredChunksResponse', 'TrustGraphFrozenSelection': 'CorpusResponse',
    'ProposalJobResult': 'ProposalJobResult', 'SeedImportResult': 'ProposalJobResult',
    'RepairJobResult': 'ProposalJobResult', 'IngestionResult': 'IngestionResult',
}


def aliases(schema):
    definitions = schema['components']['schemas']
    lines = ['/** Generated OpenAPI response aliases. Do not edit. */', "import type * as Wire from './openapi'", '']
    for name, source in sorted(ALIASES.items()):
        if source not in definitions:
            raise ValueError(f'Missing public alias source {source}')
        lines.append(f'export type {name} = Wire.{source}')
    triple = 'Triple_Output' if 'Triple-Output' in definitions else 'Triple'
    lines += [f'export type Triple = Wire.{triple}',
              "export type Page<T> = Omit<Wire.Page_ProjectResponse_, 'items'> & { items: T[] }",
              "export type Job<T = Wire.JobResponse['result']> = Omit<Wire.JobResponse, 'result'> & { result: T | null }", '']
    return '\n'.join(lines)


def application_schema():
    # Importing main constructs its app. Keep its seed/key/database strictly temporary.
    with tempfile.TemporaryDirectory(prefix='oe-openapi-') as folder:
        overrides = {'OE_DATA_DIR': folder, 'OE_DATABASE_URL': '', 'OE_EAGER_JOBS': 'true',
                     'OE_MODE': 'local', 'OE_SERVICE_TOKEN': ''}
        previous = {key: os.environ.get(key) for key in overrides}
        os.environ.update(overrides)
        try:
            from oe_studio.main import app
            return app.openapi()
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if checked-in artifacts differ; do not rewrite')
    args = parser.parse_args()
    schema = application_schema()
    outputs = {ROOT / 'docs/openapi.json': json.dumps(schema, indent=2, sort_keys=True) + '\n',
               ROOT / 'apps/studio-plugin/src/api/openapi.ts': contracts(schema),
               ROOT / 'apps/studio-plugin/src/api/generated.ts': aliases(schema)}
    for path, content in outputs.items():
        if args.check:
            if not path.is_file() or path.read_text() != content:
                raise SystemExit(f'Generated contract is stale: {path.relative_to(ROOT)}; run make api-contracts')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    print('OpenAPI request/response schemas, operation map and aliases ' + ('verified.' if args.check else 'exported.'))


if __name__ == '__main__':
    main()
