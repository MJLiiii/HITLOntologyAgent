"""Benchmark accounting is independent of generator/engine failures."""
import sys

import httpx
import pytest

from scripts import benchmark_test_agents as benchmark
from scripts.benchmark_test_agents import AXIOMS, EXPECTED_MUTANT_FAILURES, REFERENCE, run_comparison


def controlled_engine(candidate, *, tests, **kwargs):
    missing = [name for name, axiom in AXIOMS.items() if axiom not in candidate]
    # Frozen reference outcomes validate independent source expectations. For
    # generated suites this fixture models a detected semantic regression.
    failure_names = set(EXPECTED_MUTANT_FAILURES[missing[0]]) if missing else set()
    is_reference = {test['test_id'] for test in tests} == set(REFERENCE)
    return {'status': 'failed' if missing else 'passed', 'cases': [
        {'id': test['test_id'], 'status': 'failed' if (test['test_id'] in failure_names if is_reference else bool(missing)) else 'passed'}
        for test in tests]}


def test_benchmark_denominators_and_controlled_mode():
    report = run_comparison(controlled_engine)
    assert report['reference_verified'] is True
    assert report['live_model_calls'] == report['human_oracle_decisions'] == 0
    for result in report['results'].values():
        assert result['valid_variant_denominator'] == 3
        assert result['invalid_variant_denominator'] == 4
        assert result['true_positive_count'] == 4
        assert result['false_positive_count'] == 0
        assert result['false_positive_rate'] == 0
        assert result['mutation_score'] == 1


def test_cli_rejects_local_runtime_option(monkeypatch, tmp_path, capsys):
    output = tmp_path / 'report.json'
    monkeypatch.setattr(sys, 'argv', ['benchmark_test_agents.py', '--output', str(output), '--local-ollama'])
    with pytest.raises(SystemExit) as error:
        benchmark.main()
    assert error.value.code == 2
    assert 'unrecognized arguments: --local-ollama' in capsys.readouterr().err
    assert not output.exists()


def test_engine_errors_never_count_as_killed_or_valid():
    report = run_comparison(lambda *args, **kwargs: {'status': 'error', 'cases': []})
    assert report['status'] == 'error'
    assert not report['reference_verified']
    for result in report['results'].values():
        assert result['mutation_score'] is None
        assert result['false_positive_rate'] is None
        assert result['killed_mutants'] == []
        assert result['assessed_invalid_variants'] == []
        assert result['assessed_valid_variants'] == []


def test_generated_false_positives_are_counted_on_valid_variants():
    def engine(candidate, *, tests, **kwargs):
        report = controlled_engine(candidate, tests=tests, **kwargs)
        if {test['test_id'] for test in tests} != set(REFERENCE) and ':Unrelated' in candidate:
            report['status'] = 'failed'
            report['cases'][0]['status'] = 'failed'
        return report
    report = run_comparison(engine)
    assert report['reference_verified'] is True
    for name in ['deterministic', 'controlled_model']:
        result = report['results'][name]
        assert result['false_positive_count'] == 1
        assert result['false_positive_variants'] == ['valid_unrelated_extension']
        assert result['false_positive_rate'] == 1 / 3


def test_generated_engine_error_is_an_incomplete_comparison():
    def engine(candidate, *, tests, **kwargs):
        if {test['test_id'] for test in tests} != set(REFERENCE):
            return {'status': 'unsupported', 'cases': []}
        return controlled_engine(candidate, tests=tests, **kwargs)
    report = run_comparison(engine)
    assert report['reference_verified'] is True
    assert report['status'] == 'error'
    assert report['results']['controlled_model']['mutation_score'] is None


def test_generation_observations_label_mock_usage_and_null_cost():
    report = run_comparison(controlled_engine)
    assert report['network_calls'] == 0
    for name in ['deterministic', 'controlled_model']:
        row = report['results'][name]
        assert row['generation_attempts'] == 1
        assert row['invalid_output_count'] == 0
        assert row['generation_elapsed_seconds'] >= 0
        assert row['network_calls'] == 0
        assert row['cost'] is None
        assert row['cost_missing_reason']
    row = report['results']['controlled_model']
    assert row['mock_transport_requests'] == 1
    assert row['usage']['source'] == 'synthetic_fixture'
    assert row['usage']['is_measured'] is False
    record = report['controlled_generation_record']
    assert record['usage_source'] == record['input_tokens_source'] == record['output_tokens_source'] == 'synthetic_fixture'
    assert record['model_profile']['provider'] == 'openai_compatible'
    assert record['model_profile']['purposes'] == ['test_generation']
    assert record['effective_parameters']['max_output_tokens'] == 4096
    assert all(test['oracle_status'] == 'needs_review' for test in report['suites']['controlled_model'])
    assert record['cost'] is None and 'no actual provider charge' in record['cost_missing_reason']


def test_invalid_api_output_is_retained_without_fallback_or_quality_score(monkeypatch):
    original_request = httpx.MockTransport.handle_async_request

    async def invalid_response(self, request):
        await original_request(self, request)
        return httpx.Response(200, json={
            'id': 'controlled-invalid', 'object': 'chat.completion', 'created': 0,
            'model': 'controlled-fixture', 'choices': [
                {'index': 0, 'message': {'role': 'assistant', 'content': 'invalid-json'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 7, 'completion_tokens': 5, 'total_tokens': 12}})

    monkeypatch.setattr(httpx.MockTransport, 'handle_async_request', invalid_response)
    engine_calls = []

    def engine(*args, **kwargs):
        engine_calls.append(kwargs['bundle_digest'])
        return controlled_engine(*args, **kwargs)

    report = run_comparison(engine)
    assert len(engine_calls) == 14  # Reference and deterministic suites only.
    assert report['reference_verified'] is True
    assert report['status'] == 'error'
    controlled = report['results']['controlled_model']
    assert controlled['generation_attempts'] == controlled['generation_failure_count'] == controlled['invalid_output_count'] == 1
    assert controlled['mock_transport_requests'] == 1
    assert controlled['mutation_score'] is None and controlled['false_positive_rate'] is None
    assert controlled['test_count'] is None and controlled['variants'] == {}
    assert report['controlled_generation_record']['raw_output'] == 'invalid-json'
    assert report['controlled_generation_record']['status'] == 'failed'
    assert report['controlled_generation_record']['validation_errors']
    assert controlled['usage']['input_tokens'] == 7
    assert controlled['usage']['source'] == 'synthetic_fixture'
    assert controlled['usage']['is_measured'] is False
    assert controlled['network_calls'] == 0
    assert report['network_calls'] == report['external_network_calls'] == report['live_model_calls'] == 0


def test_api_transport_failure_is_not_counted_as_invalid_output(monkeypatch):
    original_request = httpx.MockTransport.handle_async_request

    async def failed_response(self, request):
        await original_request(self, request)
        return httpx.Response(503, json={'error': {'message': 'Controlled unavailable endpoint'}})

    monkeypatch.setattr(httpx.MockTransport, 'handle_async_request', failed_response)
    report = run_comparison(controlled_engine)
    controlled = report['results']['controlled_model']
    assert report['status'] == 'error' and report['reference_verified'] is True
    assert controlled['generation_failure_count'] == controlled['mock_transport_requests'] == 1
    assert controlled['invalid_output_count'] == 0
    assert controlled['usage']['input_tokens'] is None and controlled['usage']['output_tokens'] is None
    assert controlled['mutation_score'] is None and controlled['variants'] == {}
    assert controlled['cost'] is None and controlled['network_calls'] == 0
