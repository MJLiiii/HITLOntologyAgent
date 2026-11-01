"""Frozen development-only oracles executed by Jena and the real OntoCheck runner."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parents[1] / 'research/development-assessment/jena-rdfs-compat-v1'


def inputs():
    manifest = json.loads((FIXTURE / 'manifest.json').read_text())
    assert manifest['split'] == 'development'
    for filename, expected in manifest['files'].items():
        assert hashlib.sha256((FIXTURE / filename).read_bytes()).hexdigest() == expected
    return (FIXTURE / 'ontology.ttl').read_text(), json.loads((FIXTURE / 'suite.json').read_text())


def test_real_upstream_benchmark_agrees_with_jena_on_frozen_rdfs_oracles():
    from oe_studio.ontocheck_benchmark import run_rdfs_benchmark
    report = run_rdfs_benchmark(*inputs())
    assert report['status'] == 'completed', report
    assert report['equivalent'] is True and report['oracles_passed'] is True
    assert report['score'] == 1.0
    assert len(report['comparisons']) == len(report['raw']['ontocheck']['results']) == 10
    assert all(case['status'] == 'success' for case in report['raw']['ontocheck']['results'])
    assert report['raw']['jena']['status'] == 'passed'
    assert report['closure_rows_sha256']
    assert report['raw']['ontocheck']['results'][0]['evaluator'] == 'constrained-plan-v1'
    assert report['engine']['reasoner'] == 'frozen-jena-rdfs-simple-v1'


def test_builtin_graph_path_is_measured_as_a_counterexample_not_called_rdfs():
    from oe_studio.ontocheck_benchmark import run_rdfs_benchmark
    report = run_rdfs_benchmark(*inputs())
    assert report['status'] == 'completed', report
    baseline = {item['case_id']: item for item in report['raw']['graph_path_counterexample']['results']}
    bridged = {item['case_id']: item for item in report['raw']['ontocheck']['results']}
    assert baseline['inherited-instance-type']['actual']['checks']['inherited-instance-type'] == 'not_entailed'
    assert bridged['inherited-instance-type']['actual']['checks']['inherited-instance-type'] == 'entailed'
    assert report['raw']['graph_path_counterexample']['score'] < report['score']


def test_wrong_known_answer_stays_a_failed_oracle_even_when_engines_agree():
    from oe_studio.ontocheck_benchmark import run_rdfs_benchmark
    ontology, suite = inputs()
    suite['cases'][1]['expected']['values']['inherited-instance-type'] = 'not_entailed'
    report = run_rdfs_benchmark(ontology, suite)
    assert report['status'] == 'completed', report
    assert report['equivalent'] is True
    assert report['oracles_passed'] is False
    assert report['raw']['jena']['status'] == 'failed'
    assert report['score'] == 0.9


@pytest.mark.parametrize('split', ['held_out', 'test', 'unspecified'])
def test_non_development_oracles_cannot_enter_engine_feedback(monkeypatch, split):
    import oe_studio.ontocheck_benchmark as benchmark
    ontology, suite = inputs()
    suite['cases'][0]['split'] = split
    suite['cases'][0]['prompt'] = 'PRIVATE-CANARY-DO-NOT-RETURN'

    def forbidden(*args, **kwargs):
        raise AssertionError('Non-development workload reached the engine')

    monkeypatch.setattr(benchmark, 'validate', forbidden)
    report = benchmark.run_rdfs_benchmark(ontology, suite)
    assert report['status'] == 'unsupported', report
    assert report['raw'] == {}
    assert 'PRIVATE-CANARY' not in json.dumps(report)
    assert 'suite_sha256' not in report


@pytest.mark.parametrize('change', ['profile', 'deduction', 'empty', 'duplicate', 'query_language'])
def test_unsupported_suite_semantics_are_not_silently_rewritten(change):
    from oe_studio.ontocheck_benchmark import run_rdfs_benchmark
    ontology, suite = inputs()
    if change == 'profile':
        suite['inference']['profile'] = 'graph_path'
    elif change == 'deduction':
        suite['cases'][0]['task_type'] = 'deduction'
    elif change == 'empty':
        suite['cases'] = []
    elif change == 'duplicate':
        suite['cases'].append(copy.deepcopy(suite['cases'][0]))
    else:
        suite['cases'][0]['query']['language'] = 'sparql_summary'
    report = run_rdfs_benchmark(ontology, suite)
    assert report['status'] == 'unsupported', report
    assert report['score'] is None


def test_malformed_and_out_of_profile_graphs_keep_engine_status():
    from oe_studio.ontocheck_benchmark import run_rdfs_benchmark
    ontology, suite = inputs()
    malformed = run_rdfs_benchmark('broken Turtle }', suite)
    assert malformed['status'] == 'error', malformed
    assert malformed['score'] is None and 'ontocheck' not in malformed['raw']
    unsupported = run_rdfs_benchmark(ontology + '\n<https://example.org/oe-compat/o> '
        '<http://www.w3.org/2002/07/owl#imports> <http://127.0.0.1:1/external> .', suite)
    assert unsupported['status'] == 'unsupported', unsupported
    assert unsupported['score'] is None


def test_remote_query_cannot_reach_the_upstream_evaluator():
    from oe_studio.ontocheck_benchmark import run_rdfs_benchmark
    ontology, suite = inputs()
    suite['cases'][0]['query']['checks'][0]['query'] = 'ASK { SERVICE <http://127.0.0.1:1/> { ?s ?p ?o } }'
    report = run_rdfs_benchmark(ontology, suite)
    assert report['status'] == 'unsupported', report
    assert 'ontocheck' not in report['raw']


def test_missing_upstream_runtime_cannot_become_a_homegrown_benchmark(monkeypatch, tmp_path):
    from oe_studio.ontocheck_benchmark import run_rdfs_benchmark
    monkeypatch.setenv('OE_ONTOCHECK_PYTHON', str(tmp_path / 'missing-python'))
    report = run_rdfs_benchmark(*inputs())
    assert report['status'] == 'error', report
    assert report['score'] is None


def test_closure_and_registry_cannot_leak_from_a_previous_run():
    from oe_studio.ontocheck_benchmark import run_rdfs_benchmark
    ontology, suite = inputs()
    first = run_rdfs_benchmark(ontology, suite)
    changed = run_rdfs_benchmark(ontology.replace('ex:Inventory ex:ownedBy ex:Warehouse .', ''), suite)
    assert first['status'] == changed['status'] == 'completed', changed
    assert first['score'] == 1.0 and changed['score'] == 0.8
    assert first['closure_rows_sha256'] != changed['closure_rows_sha256']
    assert changed['equivalent'] is True and changed['oracles_passed'] is False


@pytest.mark.parametrize('corruption', ['upstream_error', 'closure_hash'])
def test_upstream_error_zero_or_wrong_identity_is_never_a_valid_score(monkeypatch, corruption):
    import subprocess
    import oe_studio.ontocheck_benchmark as benchmark
    report = benchmark.run_rdfs_benchmark(*inputs())
    assert report['status'] == 'completed', report
    result = {'status': 'completed', **{key: report[key] for key in
              ('ontology_sha256', 'suite_sha256', 'closure_rows_sha256')},
              'upstream_environment': report['engine']['upstream_environment'],
              'raw': {key: report['raw'][key] for key in ('ontocheck', 'graph_path_counterexample')}}
    if corruption == 'upstream_error':
        case = result['raw']['ontocheck']['results'][0]
        case.update(status='error', score=0.0, answer_score=0.0)
    else:
        result['closure_rows_sha256'] = '0' * 64
    monkeypatch.setattr(benchmark, 'validate', lambda *args, **kwargs: report['raw']['jena'])

    def fake_run(command, **kwargs):
        kwargs['stdout'].write(json.dumps(result).encode())
        return subprocess.CompletedProcess(command, 0, stderr=b'')

    monkeypatch.setattr(benchmark.subprocess, 'run', fake_run)
    failed = benchmark.run_rdfs_benchmark(*inputs())
    assert failed['status'] == 'error', failed
    assert failed['score'] is None
    if corruption == 'upstream_error':
        assert failed['raw']['ontocheck']['results'][0]['score'] == 0.0
