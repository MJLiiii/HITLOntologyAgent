"""The wire contract must be generated from actual API response models."""
from scripts.export_openapi import application_schema


def test_every_json_endpoint_declares_a_success_response_contract():
    schema = application_schema()
    missing = []
    for path, methods in schema['paths'].items():
        for method, operation in methods.items():
            if method not in {'get', 'post'}:
                continue
            for status, response in operation['responses'].items():
                if status.startswith('2'):
                    for media, content in response.get('content', {}).items():
                        if media == 'application/json' and not content.get('schema'):
                            missing.append(f'{method.upper()} {path} {status}')
    assert not missing, 'Missing response schemas: ' + ', '.join(missing)


def test_diagnostic_extensions_and_missing_measurements_round_trip_exactly():
    from oe_studio.responses import AssessmentReportResponse, ValidationReportResponse
    from oe_studio.artifacts import canonical_json
    assessment = {'id': 'assessment', 'status': 'unsupported', 'vocabulary_coverage': None,
                  'raw': {'candidate': {'score': 1, 'missing': None, 'rows': [False, 0, 0.5]}},
                  'provider_future_diagnostic': {'nullable': None, 'text': ' exact \n'}}
    validation = {'id': 'validation', 'status': 'error', 'cases': [],
                  'raw_artifacts': {'shacl-report.ttl': '@prefix ex: <https://example.org/> .\n'},
                  'provider_future_diagnostic': {'exit_code': 9, 'stderr': ' bounded\n'}}
    for model, payload in [(AssessmentReportResponse, assessment), (ValidationReportResponse, validation)]:
        assert canonical_json(model.model_validate(payload).model_dump(exclude_unset=True)) == canonical_json(payload)


def test_stable_records_reject_undeclared_response_fields():
    import pytest
    from pydantic import ValidationError
    from oe_studio.responses import JobRefResponse
    with pytest.raises(ValidationError, match='Extra inputs'):
        JobRefResponse.model_validate({'job_id': 'job', 'status_url': '/api/v1/jobs/job', 'silent_loss': 'forbidden'})


def test_wire_schemas_include_diagnostics_artifacts_and_nullable_results():
    schema = application_schema()
    definitions = schema['components']['schemas']
    for model, fields in {
        'RevisionResponse': {'manifest', 'ontology', 'questions', 'tests', 'mappings', 'validation', 'assessment'},
        'ValidationReportResponse': {'raw_artifacts', 'input_manifest', 'stages', 'shacl'},
        'AssessmentReportResponse': {'raw', 'deltas', 'denominators', 'missing_reasons', 'mappings'},
        'ExperimentResponse': {'sealed_record', 'record_digest', 'metrics', 'generation_calls', 'project_context'},
        'EvidenceResponse': {'chunk', 'source_hash', 'span_start', 'span_end', 'provenance'},
    }.items():
        assert fields <= definitions[model]['properties'].keys()
    assert definitions['ProjectResponse']['additionalProperties'] is False
    assert definitions['AssessmentReportResponse']['additionalProperties'] == {'$ref': '#/components/schemas/JsonValue'}
    # Raw artifact bytes and the CSV export do not pretend to be generic JSON.
    paths = schema['paths']
    assert 'application/octet-stream' in paths['/api/v1/projects/{p}/artifacts/{artifact_id}']['get']['responses']['200']['content']
    assert set(paths['/api/v1/projects/{p}/experiments/export']['get']['responses']['200']['content']) == {'application/json', 'text/csv'}


def test_job_result_preserves_boolean_json_diagnostics_and_stage_contract():
    import pytest
    from pydantic import ValidationError
    from oe_studio.artifacts import canonical_json
    from oe_studio.responses import JobResponse
    report = {'id': 'report', 'status': 'passed', 'cases': [{'id': 'cq', 'status': 'passed', 'actual': True, 'expected': True}],
              'raw_artifacts': {'rows': [{'nullable': None, 'boolean': False, 'integer': 0, 'float': 0.0}]}}
    envelope = {'id': 'job', 'status': 'succeeded', 'stage': 'validation', 'result': report,
                'error': None, 'progress': 1, 'created_at': 'now'}
    serialized = JobResponse.model_validate(envelope).model_dump(mode='json', exclude_unset=True)
    assert canonical_json(serialized) == canonical_json(envelope)
    with pytest.raises(ValidationError):
        JobResponse.model_validate({**envelope, 'stage': 'proposal'})


def test_job_operation_metadata_matches_registered_worker_kind():
    """No handwritten TS result registry may drift from an enqueue handler."""
    import ast
    from pathlib import Path
    tree = ast.parse((Path(__file__).parents[2] / 'services/api/src/oe_studio/main.py').read_text())
    found = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        enqueues = [call for call in ast.walk(node) if isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute) and call.func.attr == 'create_job']
        # create_app contains all handlers; only direct route decorators count.
        decorators = [decorator for decorator in node.decorator_list if isinstance(decorator, ast.Call)]
        if not enqueues or not decorators:
            continue
        assert len(enqueues) == 1
        kind = ast.literal_eval(enqueues[0].args[1])
        metadata = next(keyword.value for decorator in decorators for keyword in decorator.keywords
                        if keyword.arg == 'openapi_extra')
        assert ast.literal_eval(metadata)['x-job-kind'] == kind
        found += 1
    assert found == 13
