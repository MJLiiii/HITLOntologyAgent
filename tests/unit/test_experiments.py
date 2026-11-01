from dataclasses import FrozenInstanceError

import pytest

from oe_studio import demo
from oe_studio import experiments as ex


@pytest.fixture
def engines(monkeypatch):
    calls = []

    def validate(ttl, **kwargs):
        repaired = '<http://www.w3.org/2000/01/rdf-schema#subClassOf>' in ttl
        cases = [{'id': t['test_id'], 'status': 'passed', 'expected': t['expected'],
                  'actual': t['expected']} for t in kwargs['tests']]
        if not repaired:
            cases[0].update(status='failed', actual=False)
        calls.append(('validation', ttl, kwargs))
        return {'status': 'passed' if repaired else 'failed', 'cases': cases}

    def assess(ttl, **kwargs):
        calls.append(('assessment', ttl, kwargs))
        return {'status': 'completed', 'vocabulary_coverage': 1., 'vocabulary_utilisation': .75,
                'denominators': {'candidate': {'task_terms': 3, 'ontology_terms': 4, 'overlap': 3}}}

    monkeypatch.setattr(ex, 'validate', validate)
    monkeypatch.setattr(ex, 'assess', assess)
    return calls


def test_conditions_share_frozen_inputs_and_budgets(engines):
    records = ex.execute_demo(demo.ONTOLOGY, bundle_digest='a' * 64)
    assert [r['condition'] for r in records] == list('ABCD')
    assert len({r['task_packet_digest'] for r in records}) == 1
    assert len({r['initial_candidate_digest'] for r in records}) == 1
    assert records[1]['budget'] == records[2]['budget'] == records[3]['budget']
    assert records[2]['candidate_digest'] == records[3]['candidate_digest']
    assert records[0]['candidate_digest'] != records[2]['candidate_digest']


def test_task_packet_is_immutable_and_agent_manifest_excludes_oracles():
    packet = ex.freeze_task(demo.ONTOLOGY, 'a' * 64)
    with pytest.raises(FrozenInstanceError):
        packet.initial_candidate = 'changed'
    manifest = packet.agent_manifest()
    assert 'held_out' not in manifest and 'tests' not in manifest
    manifest['sources'][0]['text'] = 'mutated external copy'
    assert packet.agent_manifest()['sources'][0]['text'] != 'mutated external copy'


def test_condition_feedback_is_limited_to_failed_entailment_cases(engines):
    a, b, c, d = ex.execute_demo(demo.ONTOLOGY, bundle_digest='a' * 64)
    assert a['repair_history'] == []
    assert b['repair_history'][0]['feedback'] == []
    assert c['repair_history'] == d['repair_history']
    assert [case['id'] for case in c['repair_history'][0]['feedback']] == ['CQ-01']
    assert all('assessment' not in step and 'vocabulary_coverage' not in str(step)
               for r in (a, b, c, d) for step in r['repair_history'])
    assert {call[2]['questions'][0]['sparql_query'] for call in engines if call[0] == 'assessment'}


def test_error_counts_in_scheduled_denominator(monkeypatch, engines):
    monkeypatch.setattr(ex, 'validate', lambda *a, **kw: {'status': 'timeout', 'cases': []})
    result = ex.execute_demo(demo.ONTOLOGY, bundle_digest='a' * 64, condition='A')[0]
    metric = result['metrics']['reasoning_pass_rate']
    assert metric['value'] == 0 and metric['denominator'] == 3
    assert result['case_counts']['timeout'] == 3
    assert result['status'] == 'timeout'
    assert result['answer_precision'] is None


def test_undefined_precision_is_missing_and_distinct_from_vocabulary(engines):
    result = ex.execute_demo(demo.ONTOLOGY, bundle_digest='a' * 64, condition='A')[0]
    assert result['metrics']['answer_recall']['value'] == .5
    assert result['vocabulary_coverage'] == 1
    assert ex.ratio(0, 0)['value'] is None
    assert ex.ratio(0, 0)['missing_reason'] == 'zero_denominator'


def test_known_true_false_positive_negative_table_has_explicit_denominators():
    tests = [{'test_id': str(i), 'expected': expected} for i, expected in enumerate([True, False, True, False])]
    actual = [True, True, False, False]
    report = {'status': 'failed', 'cases': [{'id': str(i), 'actual': value,
              'status': 'passed' if value == tests[i]['expected'] else 'failed'} for i, value in enumerate(actual)]}
    metrics, counts = ex.measurements(report, {'status': 'not_run'}, tests)
    assert (counts['tp'], counts['fp'], counts['fn'], counts['tn']) == (1, 1, 1, 1)
    assert counts['scheduled'] == 4 and counts['unevaluable'] == 0
    for name in ('answer_precision', 'answer_recall', 'answer_f1', 'answer_accuracy_required', 'reasoning_pass_rate'):
        assert metrics[name]['value'] == .5
    assert metrics['answer_accuracy_required']['denominator'] == 4
    assert metrics['vocabulary_coverage']['value'] is None


def test_d_pre_post_snapshots_separate_without_invented_review(engines):
    d = ex.execute_demo(demo.ONTOLOGY, bundle_digest='a' * 64, condition='D')[0]
    assert d['status'] == d['review_status'] == 'waiting_human'
    assert d['pre_review_snapshot']['candidate_digest'] == d['candidate_digest']
    assert d['post_review_snapshot'] is None
    assert d['correction_seconds'] is None and d['review_decisions'] == []
    assert d['mode'] == 'deterministic_demo'


def test_failed_engine_keeps_every_requested_replicate(monkeypatch, engines):
    def unavailable(*args, **kwargs):
        raise OSError('missing runner')
    monkeypatch.setattr(ex, 'assess', unavailable)
    records = ex.execute_demo(demo.ONTOLOGY, bundle_digest='a' * 64, replicate_ids=[1, 2])
    assert len(records) == 8
    assert all(r['assessment']['status'] == 'error' for r in records)
    assert all(r['vocabulary_utilisation'] is None for r in records)


@pytest.mark.parametrize('condition,replicates', [('Z', [1]), ('all', []), ('A', [1, 1]), ('A', [0])])
def test_invalid_run_request_rejected(condition, replicates):
    with pytest.raises(ValueError):
        ex.execute_demo(demo.ONTOLOGY, bundle_digest='a' * 64,
                        condition=condition, replicate_ids=replicates)
