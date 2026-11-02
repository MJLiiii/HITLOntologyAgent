"""Offline synthetic mutation comparison; controlled model responses, never paid calls.

This development benchmark is separate from registered experiments and held-out
research evaluation. Fixed reference expectations are authored independently of
both generators. Real pinned Jena evaluates all reference/generated cases.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/api/src'))

from oe_studio.agents.test_generation import TestGenerationAgent, TestGenerationAgentInput  # noqa: E402
from oe_studio.artifacts import digest  # noqa: E402
from oe_studio.model import ModelClient, ModelGenerationError  # noqa: E402
from oe_studio.schemas import TestSpec  # noqa: E402
from oe_studio.testspecs import generate_suite, sha  # noqa: E402
from oe_studio.validation import validate  # noqa: E402

NS = 'https://example.org/oe-demo/'
PREFIX = f'@prefix : <{NS}> .\n@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
DECLARATIONS = ':CriticalService a rdfs:Class .\n:Service a rdfs:Class .\n:Owner a rdfs:Class .\n:ownedBy a rdf:Property .\n:operatedBy a rdf:Property .\n'
AXIOMS = {
    'subclass': ':CriticalService rdfs:subClassOf :Service .\n',
    'subproperty': ':operatedBy rdfs:subPropertyOf :ownedBy .\n',
    'domain': ':ownedBy rdfs:domain :Service .\n',
    'range': ':ownedBy rdfs:range :Owner .\n',
}
CANDIDATE = PREFIX + DECLARATIONS + ''.join(AXIOMS.values())
FIXTURES = PREFIX + ':fixed-class-instance a :CriticalService .\n:fixed-subject :operatedBy :fixed-object .\n'
# Independent reference expectations describe source requirements, not generated outputs.
REFERENCE = {
    'subclass': f'ASK {{ <{NS}fixed-class-instance> a <{NS}Service> }}',
    'subproperty': f'ASK {{ <{NS}fixed-subject> <{NS}ownedBy> <{NS}fixed-object> }}',
    'domain': f'ASK {{ <{NS}fixed-subject> a <{NS}Service> }}',
    'range': f'ASK {{ <{NS}fixed-object> a <{NS}Owner> }}',
}
EXPECTED_MUTANT_FAILURES = {
    'subclass': ['subclass'], 'subproperty': ['domain', 'range', 'subproperty'],
    'domain': ['domain'], 'range': ['range'],
}


class ControlledClient:
    """Fixed contract fixture; performance is not evidence of live-model quality."""
    def __init__(self):
        self.transport_requests = 0

    def generate(self, system, context, schema):
        base = context['synthetic_namespace']
        fixtures = PREFIX + f'<{base}class-instance> a :CriticalService .\n<{base}subject> :operatedBy <{base}object> .\n'
        tests = []
        controlled_queries = {
            'subclass': f'ASK {{ <{base}class-instance> a <{NS}Service> }}',
            'subproperty': f'ASK {{ <{base}subject> <{NS}ownedBy> <{base}object> }}',
            'domain': f'ASK {{ <{base}subject> a <{NS}Service> }}',
            'range': f'ASK {{ <{base}object> a <{NS}Owner> }}',
        }
        for name, query in controlled_queries.items():
            tests.append({'kind': 'ask', 'query': query, 'expected': True, 'fixtures_ttl': fixtures,
                          'rationale': 'Controlled response proposes the frozen synthetic source requirement: ' + name,
                          'evidence_ids': ['source:synthetic-rdfs'], 'question_ids': ['Q-subclass'] if name == 'subclass' else [],
                          'scenario': 'positive'})
        profile = {'id': 'controlled-fixture', 'revision': digest({'fixture': 'test-agent-api-v2'}),
                   'provider': 'openai', 'api_key_env': 'OE_BENCHMARK_API_KEY', 'model': 'controlled-fixture', 'base_url': 'https://provider.invalid/v1',
                   'timeout': 2, 'max_output_tokens': 4096, 'temperature': 0,
                   'structured_output': 'json_schema', 'max_response_bytes': 65536, 'purposes': ['test_generation']}
        settings = SimpleNamespace(resolved_llm_profile=profile, llm_session_id=None)
        content = json.dumps({'tests': tests})

        def serve(request):
            self.transport_requests += 1
            wire = json.loads(request.content)
            if 'tools' in wire:
                raise AssertionError('Controlled agent transport must not expose tools')
            if request.method != 'POST' or request.url.path != '/v1/chat/completions':
                raise AssertionError('Controlled fixture requires the completion API endpoint')
            return httpx.Response(200, json={
                'id': 'controlled-response', 'object': 'chat.completion', 'created': 0,
                'model': 'controlled-fixture', 'choices': [
                    {'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 100, 'total_tokens': 200}})

        observations = dict(usage_source='synthetic_fixture', input_tokens_source='synthetic_fixture',
                            output_tokens_source='synthetic_fixture', usage_is_measured=False,
                            cost=None, cost_missing_reason='Controlled in-memory transport; no actual provider charge',
                            transport='httpx.MockTransport', http_attempt_scope='In-memory mock request only', network_calls=0)
        try:
            with TemporaryDirectory(prefix='oe-benchmark-') as directory:
                credential_file = Path(directory) / 'fixture.env'
                credential_file.write_text('OE_BENCHMARK_API_KEY=synthetic-benchmark-key\n')
                settings.model_config = {'env_file': credential_file}
                output, record = ModelClient(settings, transport=httpx.MockTransport(serve)).generate(system, context, schema)
        except ModelGenerationError as error:
            error.record.update(observations)
            raise
        record.update(observations)
        return output, record


def reference_tests():
    return [TestSpec(test_id=name, kind='ask', query=query, expected=True, fixtures_ttl=FIXTURES,
                     rationale='Fixed independent synthetic source requirement: ' + name).model_dump(exclude_none=True)
            for name, query in REFERENCE.items()]


def run_comparison(validator=validate):
    """Injectable engine boundary; the default invokes real pinned isolated Jena."""
    bundle = digest({'candidate': CANDIDATE, 'fixtures': FIXTURES, 'requirements': REFERENCE})
    context = dict(candidate_ttl=CANDIDATE, shapes_ttl='', fixtures_ttl=FIXTURES,
                   questions=[{'id': 'Q-subclass', 'sparql_query': REFERENCE['subclass'], 'expected': True}],
                   changes={}, evidence=[{'id': 'source:synthetic-rdfs', 'resolved': True,
                                          'text': 'Synthetic requirements: CriticalService is a Service; operatedBy implies ownedBy; ownedBy has domain Service and range Owner.'}],
                   bundle_digest=bundle)
    started = time.perf_counter()
    deterministic = generate_suite(**context)
    deterministic_elapsed = time.perf_counter() - started
    client = ControlledClient()
    started = time.perf_counter()
    model = None
    model_failure = None
    try:
        model = TestGenerationAgent(client).run(TestGenerationAgentInput(**context))
        model_record = model.generation_record
    except ModelGenerationError as error:
        model_record = error.record
        model_failure = str(error)
    model_elapsed = time.perf_counter() - started
    generation_observations = {
        'fixed_reference': {'generation_attempts': 0, 'invalid_output_count': 0,
                            'generation_elapsed_seconds': None, 'network_calls': 0,
                            'usage': None, 'cost': None, 'cost_missing_reason': 'Preauthored reference; no generation'},
        'deterministic': {'generation_attempts': 1, 'invalid_output_count': 0,
                          'generation_elapsed_seconds': deterministic_elapsed, 'network_calls': 0,
                          'usage': None, 'cost': None, 'cost_missing_reason': 'Local deterministic generation; no provider charge'},
        'controlled_model': {'generation_attempts': 1, 'generation_failure_count': int(model_failure is not None),
                             'invalid_output_count': int(model_failure is not None and bool(
                                 model_record.get('raw_output') or model_record.get('output') or model_record.get('validation_errors'))),
                             'generation_error': model_failure,
                             'generation_elapsed_seconds': model_elapsed, 'network_calls': 0,
                             'mock_transport_requests': client.transport_requests,
                             'usage': {'input_tokens': model_record.get('input_tokens'),
                                       'output_tokens': model_record.get('output_tokens'),
                                       'source': 'synthetic_fixture', 'is_measured': False},
                             'cost': None, 'cost_missing_reason': 'Controlled in-memory transport; no actual provider charge'},
    }
    suites = {'fixed_reference': reference_tests(), 'deterministic': deterministic['tests']}
    if model is not None:
        suites['controlled_model'] = [test.model_dump(exclude_none=True) for test in model.tests]

    valid_variants = {
        'baseline': CANDIDATE,
        'valid_unrelated_extension': CANDIDATE + ':Unrelated a rdfs:Class .\n',
        'valid_redundant_axiom': CANDIDATE + ':operatedBy rdfs:domain :Service .\n',
    }
    variants = {**valid_variants, **{name: CANDIDATE.replace(axiom, '') for name, axiom in AXIOMS.items()}}
    results = {}
    for suite_name, tests in suites.items():
        rows = {}
        for variant, candidate in variants.items():
            # Each mutation is a distinct evaluation target; preserve original suite digest.
            # This test-only transplantation never writes Studio bundles or approvals.
            evaluation_tests = [{**test, 'target_ontology_sha256': sha(candidate)} for test in tests]
            report = validator(candidate, bundle_digest=digest({'bundle': bundle, 'variant': variant, 'suite': suite_name}),
                               fixtures_ttl=FIXTURES, tests=evaluation_tests)
            cases = report.get('cases', [])
            rows[variant] = {'status': report['status'],
                             'failed_cases': sorted(case['id'] for case in cases if case['status'] == 'failed'),
                             'error_cases': sorted(case['id'] for case in cases if case['status'] not in {'failed', 'passed'}),
                             'report': report}
        baseline_valid = rows['baseline']['status'] == 'passed'
        assessed = [name for name in AXIOMS if rows[name]['status'] in {'passed', 'failed'} and not rows[name]['error_cases']]
        killed = [name for name in assessed if rows[name]['failed_cases']]
        assessed_valid = [name for name in valid_variants if rows[name]['status'] in {'passed', 'failed'} and not rows[name]['error_cases']]
        false_positives = [name for name in assessed_valid if rows[name]['failed_cases']]
        metrics_complete = len(assessed) == len(AXIOMS) and len(assessed_valid) == len(valid_variants)
        results[suite_name] = {**generation_observations[suite_name], 'valid_variant_denominator': len(valid_variants),
                              'invalid_variant_denominator': len(AXIOMS),
                              'assessed_valid_variants': assessed_valid,
                              'assessed_invalid_variants': assessed,
                              'true_positive_count': len(killed) if metrics_complete else None,
                              'false_negative_count': len(AXIOMS) - len(killed) if metrics_complete else None,
                              'false_positive_count': len(false_positives) if metrics_complete else None,
                              'true_negative_count': len(valid_variants) - len(false_positives) if metrics_complete else None,
                              'false_positive_variants': false_positives,
                              'false_positive_rate': len(false_positives) / len(valid_variants) if metrics_complete else None,
                              'test_count': len(tests), 'suite_digest': digest(tests), 'baseline_passed': baseline_valid,
                              'assessed_mutants': assessed, 'killed_mutants': killed,
                              'mutation_score': len(killed) / len(AXIOMS) if baseline_valid and len(assessed) == len(AXIOMS) else None,
                              'variants': rows}
    if model_failure is not None:
        results['controlled_model'] = {**generation_observations['controlled_model'], 'generation_status': 'failed',
            'valid_variant_denominator': len(valid_variants), 'invalid_variant_denominator': len(AXIOMS),
            'assessed_valid_variants': [], 'assessed_invalid_variants': [], 'assessed_mutants': [],
            'killed_mutants': [], 'false_positive_variants': [], 'test_count': None, 'suite_digest': None,
            'baseline_passed': None, 'mutation_score': None, 'true_positive_count': None,
            'false_negative_count': None, 'false_positive_count': None, 'true_negative_count': None,
            'false_positive_rate': None, 'variants': {}}
    reference = results['fixed_reference']
    reference_valid = all(reference['variants'][name]['status'] == 'passed' for name in valid_variants) and all(
        reference['variants'][name]['status'] == 'failed'
        and reference['variants'][name]['failed_cases'] == expected and not reference['variants'][name]['error_cases']
        for name, expected in EXPECTED_MUTANT_FAILURES.items())
    if not reference_valid:
        for result in results.values():
            for metric in ('mutation_score', 'true_positive_count', 'false_negative_count', 'false_positive_count', 'true_negative_count', 'false_positive_rate'):
                result[metric] = None
    comparison_complete = reference_valid and all(
        len(row['assessed_valid_variants']) == len(valid_variants)
        and len(row['assessed_invalid_variants']) == len(AXIOMS) for row in results.values())
    return {'version': 'test-agent-development-mutation-v1', 'status': 'completed' if comparison_complete else 'error',
            'scope': 'Synthetic development benchmark; not a registered study or held-out evaluation',
            'model_mode': 'controlled_response_fixture',
            'live_model_calls': 0, 'human_oracle_decisions': 0,
            'network_calls': 0,
            'external_network_calls': 0,
            'generation_observation_scope': 'One deterministic generation and one controlled API response; counts do not estimate a general failure rate. Adversarial invalid-output unit tests are separate.',
            'limitations': ['Controlled model responses measure integration and expressive coverage, not model quality.',
                            'Four fixed RDFS mutants do not establish general semantic correctness or source fidelity.',
                            'Generated suites retain needs_review and are never approved by this benchmark.'],
            'engine': reference['variants']['baseline']['report'].get('engine'),
            'input_manifest': {'candidate_sha256': sha(CANDIDATE), 'fixtures_sha256': sha(FIXTURES),
                               'bundle_digest': bundle, 'benchmark_implementation_sha256': sha(Path(__file__).read_text()),
                               'candidate_ttl': CANDIDATE, 'fixtures_ttl': FIXTURES},
            'suites': suites, 'controlled_generation_record': model_record,
            'reference_expectations': REFERENCE, 'expected_mutant_failures': EXPECTED_MUTANT_FAILURES,
            'reference_verified': reference_valid, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_comparison()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': report['status'], 'reference_verified': report['reference_verified'],
                      'mutation_scores': {key: row['mutation_score'] for key, row in report['results'].items()},
                      'output': str(args.output)}))
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
