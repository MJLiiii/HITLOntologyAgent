import copy
from types import SimpleNamespace

import pytest

from oe_studio import demo, experiments as ex
from oe_studio.model import ModelGenerationError


@pytest.fixture
def settings():
    return SimpleNamespace(model_url='http://127.0.0.1:11434', model_name='test-model', model_timeout=10)


@pytest.fixture
def engines(monkeypatch):
    calls = []

    def validate(ttl, **kwargs):
        repaired = '<http://www.w3.org/2000/01/rdf-schema#subClassOf>' in ttl
        cases = [{'id': t['test_id'], 'status': 'passed', 'expected': t['expected'],
                  'actual': t['expected']} for t in kwargs['tests']]
        if not repaired:
            cases[0].update(status='failed', actual=False, secret='DO NOT SEND FULL REPORT')
        cases.append({'id': 'shacl', 'status': 'failed', 'expected': True, 'actual': False})
        calls.append(('validation', ttl))
        return {'status': 'passed' if repaired else 'failed', 'cases': cases,
                'bundle_digest': kwargs['bundle_digest'], 'diagnostics': 'ENGINE SECRET'}

    def assess(ttl, **kwargs):
        calls.append(('assessment', ttl))
        return {'status': 'completed', 'bundle_digest': kwargs['bundle_digest'],
                'vocabulary_coverage': 1., 'vocabulary_utilisation': .75,
                'denominators': {'candidate': {'task_terms': 3, 'ontology_terms': 4, 'overlap': 3}},
                'diagnostics': 'ASSESSMENT SECRET'}

    monkeypatch.setattr(ex, 'validate', validate)
    monkeypatch.setattr(ex, 'assess', assess)
    return calls


class Model:
    def __init__(self):
        self.calls = []

    def generate(self, system, context, schema):
        self.calls.append(copy.deepcopy(context))
        changes = []
        if context['stage'] == 'reasoner_repair':
            changes = [{'operation': 'add', 'triple': {
                'subject': demo.NS + 'CriticalService',
                'predicate': 'http://www.w3.org/2000/01/rdf-schema#subClassOf',
                'object': demo.NS + 'Service'}, 'evidence_ids': [context['evidence'][0]['id']],
                'rationale': 'The source describes a service specialization.'}]
        return schema.model_validate({'summary': 'Inspected the frozen source requirements.',
                                      'changes': changes}), {
            'provider': 'ollama', 'model': 'test-model', 'input_tokens': 20, 'output_tokens': 30,
            'elapsed_seconds': .1, 'cost': None, 'seed': None}


def run(settings, **kwargs):
    return ex.execute_model(demo.ONTOLOGY, bundle_digest='a' * 64, settings=settings, **kwargs)


def test_model_conditions_share_actual_generation_and_equal_repair_budgets(settings, engines):
    model = Model()
    a, b, c, d = run(settings, model_client=model)
    assert [x['stage'] for x in model.calls] == ['initial', 'self_revision', 'self_revision', 'reasoner_repair']
    assert len({r['initial_candidate_digest'] for r in (a, b, c, d)}) == 1
    assert len({r['task_packet_digest'] for r in (a, b, c, d)}) == 1
    assert b['budget'] == c['budget'] == d['budget']
    assert a['repair_history'] == []
    assert c['repair_history'] == d['repair_history']
    assert c['generation_call_ids'] == d['generation_call_ids']
    assert c['candidate_digest'] == d['candidate_digest'] != a['candidate_digest']
    assert d['status'] == 'waiting_human' and d['post_review_snapshot'] is None
    assert d['correction_seconds'] is None and not d['review_decisions']
    assert all(r['mode'] == 'model_pilot' and r['record_digest'] for r in (a, b, c, d))
    assert b['metrics']['model_tokens']['value'] == 150
    assert c['metrics']['model_tokens']['value'] == 100
    assert a['answer_recall'] == .5 and a['vocabulary_coverage'] == 1


def test_all_arms_retain_one_frozen_non_ollama_profile(settings, engines):
    from oe_studio.llm_profiles import Profile, _snapshot, profile_settings
    snapshot = _snapshot(Profile(id='claude', provider='anthropic', model='fixture', purposes=['experiment'], temperature=None, max_output_tokens=1024, structured_output='prompt_json'))
    settings = profile_settings(settings, snapshot)
    records = run(settings, model_client=Model())
    assert len({r['model']['profile_revision'] for r in records}) == 1
    assert all(r['model']['provider'] == 'anthropic' and r['model']['temperature'] is None for r in records)
    assert all(r['budget']['maximum_output_tokens_per_call'] == 1024 for r in records)


def test_only_failed_cq_feedback_reaches_c_and_no_oracles_or_diagnostics_reach_b(settings, engines):
    model = Model()
    run(settings, model_client=model)
    for ctx in model.calls:
        assert not any(key in ctx for key in ('tests', 'shapes', 'assessment', 'held_out'))
        assert 'SECRET' not in str(ctx) and 'sparql_query' not in str(ctx)
        if ctx['stage'] != 'reasoner_repair':
            assert 'feedback' not in ctx
        else:
            assert ctx['feedback'] == [{'id': 'CQ-01', 'status': 'failed', 'expected': True, 'actual': False}]


def test_initial_failure_retains_every_scheduled_observation(settings, engines):
    class Failed(Model):
        def generate(self, *args):
            raise ModelGenerationError('bad output', {'raw_output': 'invalid', 'elapsed_seconds': .5})
    records = run(settings, model_client=Failed(), replicate_ids=[1, 2])
    assert len(records) == 8 and not engines
    for record in records:
        assert record['candidate_ttl'] is None
        assert record['case_counts']['scheduled'] == record['case_counts']['error'] == 3
        assert record['metrics']['reasoning_pass_rate']['denominator'] == 3
        assert record['answer_precision'] is None
        assert record['generation_calls'][0]['raw_output'] == 'invalid'
        assert record['status'] == 'generation_error'


def test_bad_repair_is_retained_and_never_silently_substitutes_scripted_result(settings, engines):
    class BadRepair(Model):
        def generate(self, system, context, schema):
            parsed, metadata = super().generate(system, context, schema)
            if context['stage'] == 'reasoner_repair':
                parsed.changes[0].evidence_ids = ['fabricated']
            return parsed, metadata
    c = run(settings, model_client=BadRepair(), condition='C')[0]
    assert c['status'] == 'generation_error' and c['candidate_ttl'] is None
    assert c['repair_history'][0]['status'] == 'error'
    assert c['generation_calls'][-1]['raw_parsed_output']['changes'][0]['evidence_ids'] == ['fabricated']
    assert c['metrics']['model_tokens']['value'] == 100


def test_packet_copies_inputs_and_rejects_unresolved_or_changed_scope(settings, engines):
    evidence = [{'id': 'trusted-id', 'quote': 'Critical services are services.', 'resolved': True}]
    packet = ex.freeze_model_task(demo.ONTOLOGY, 'a' * 64, evidence=evidence)
    evidence[0]['quote'] = 'mutated'
    assert packet.agent_manifest()['evidence'][0]['quote'] != 'mutated'
    with pytest.raises(ValueError, match='resolved'):
        ex.freeze_model_task(demo.ONTOLOGY, 'a' * 64, evidence=[{'id': 'x', 'quote': 'x', 'resolved': False}])
    with pytest.raises(ValueError, match='scope'):
        ex.freeze_model_task('@prefix x: <https://wrong.test/> . x:A x:B x:C .', 'a' * 64)
    with pytest.raises(ValueError, match='frozen'):
        ex.execute_model(demo.ONTOLOGY, bundle_digest='b' * 64, settings=settings,
                         model_client=Model(), frozen_task=packet)


def review_material(pre, engines):
    post = ex.canonicalize(ex.parse_ttl(demo.ONTOLOGY))
    revision = {'id': 'revision-2', 'proposal_id': 'proposal', 'revision': 2, 'bundle_digest': 'b' * 64,
                'experiment_run_id': pre['id'], 'experiment_pre_candidate_digest': pre['candidate_digest'],
                'manifest': {'canonical_ontology_sha256': ex.sha(post)}}
    review = {'id': 'review-1', 'revision_id': 'revision-2', 'proposal_id': 'proposal', 'revision': 2,
              'bundle_digest': 'b' * 64, 'decision': 'accept', 'rationale': 'Verified against the sources.',
              'actor': {'kind': 'human', 'subject': 'reviewer', 'roles': ['approver']},
              'validation_run_id': 'validation-2', 'required_assessment_run_ids': ['assessment-2']}
    validation = {'id': 'validation-2', 'revision_id': 'revision-2', 'status': 'passed', 'bundle_digest': 'b' * 64,
                  'cases': [{'id': t['test_id'], 'status': 'passed', 'expected': t['expected'],
                             'actual': t['expected']} for t in ex.json.loads(ex.freeze_task(demo.ONTOLOGY, 'a' * 64).tests_json)]}
    assessment = {'id': 'assessment-2', 'revision_id': 'revision-2', 'status': 'completed', 'bundle_digest': 'b' * 64}
    return dict(reviewed_revision=revision, review=review, ontology_ttl=post,
                validation_report=validation, assessment_report=assessment)


def test_human_link_appends_separate_sealed_snapshot_and_does_not_invent_time(settings, engines):
    pre = run(settings, condition='D', model_client=Model())[0]
    before = copy.deepcopy(pre)
    post = ex.append_human_review(pre, **review_material(pre, engines))
    assert pre == before and pre['phase'] == 'pre_review'
    assert post['id'] != pre['id'] and post['parent_run_id'] == pre['id']
    assert post['phase'] == 'post_review' and post['review_status'] == 'accept'
    assert post['post_review_snapshot']['candidate_digest'] != pre['candidate_digest']
    assert post['pre_review_snapshot'] == pre['pre_review_snapshot']
    assert post['correction_seconds'] is None


@pytest.mark.parametrize('tamper', ['actor', 'bundle', 'lineage', 'run_digest', 'report'])
def test_human_link_rejects_untrusted_or_stale_records(settings, engines, tamper):
    pre = run(settings, condition='D', model_client=Model())[0]
    values = review_material(pre, engines)
    if tamper == 'actor':
        values['review']['actor']['kind'] = 'service'
    elif tamper == 'bundle':
        values['review']['bundle_digest'] = 'c' * 64
    elif tamper == 'lineage':
        values['reviewed_revision']['experiment_run_id'] = 'other-run'
    elif tamper == 'report':
        values['assessment_report']['revision_id'] = 'other-revision'
    else:
        pre['candidate_ttl'] += '# tampered'
    with pytest.raises(ValueError):
        ex.append_human_review(pre, **values)
