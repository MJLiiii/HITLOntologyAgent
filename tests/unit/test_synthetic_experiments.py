import copy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from oe_studio import experiments as ex
from oe_studio.artifacts import canonical_json
from oe_studio.demo import NS, PREFIX


def packet_inputs(task='billing'):
    title = task.title()
    seed = PREFIX + f'demo:{title} a owl:Class . demo:{title}Special a owl:Class . demo:Other a owl:Class .'
    query = f'PREFIX ex: <{NS}> ASK {{ ex:{title}Example a ex:{title} }}'
    return dict(task_id=task, instruction=f'Model the synthetic {task} specialization stated in the evidence.',
                bundle_digest='sha256:' + 'a' * 64, base_ontology='', seed_ontology=seed,
                questions=[{'id': 'CQ-' + task, 'question': f'Is the synthetic {task} example a {task}?',
                            'sparql_query': query, 'expected': True, 'required': True}],
                tests=[{'test_id': 'CQ-' + task, 'kind': 'ask', 'query': query, 'expected': True,
                        'name': 'Frozen required question'}],
                shapes_ttl='', fixtures_ttl=PREFIX + f'demo:{title}Example a demo:{title}Special .',
                evidence=[{'id': 'evidence-' + task, 'document_id': 'doc-' + task, 'resolved': True,
                           'classification': 'synthetic', 'source_sha256': 'f' * 64,
                           'quote': f'{title}Special is a subclass of {title}.'}], mappings=[])


class Model:
    def __init__(self):
        self.calls = []

    def generate(self, system, context, schema):
        self.calls.append(copy.deepcopy(context))
        changes = []
        if context['stage'] == 'reasoner_repair':
            title = context['task_id'].title()
            changes = [{'operation': 'add', 'triple': {'subject': NS + title + 'Special',
                        'predicate': 'http://www.w3.org/2000/01/rdf-schema#subClassOf', 'object': NS + title},
                        'evidence_ids': [context['evidence'][0]['id']], 'rationale': 'The frozen synthetic source states this specialization.'}]
        return schema.model_validate({'summary': 'Inspect the frozen synthetic task.', 'changes': changes}), {
            'input_tokens': 10, 'output_tokens': 20, 'elapsed_seconds': .01, 'cost': None}


SETTINGS = SimpleNamespace(model_url='http://localhost:11434', model_name='synthetic-test-client', model_timeout=10)


@pytest.fixture
def engines(monkeypatch):
    calls = []

    def validate(ttl, **kwargs):
        calls.append(('validation', copy.deepcopy(kwargs)))
        repaired = 'subClassOf' in ttl
        return {'status': 'passed' if repaired else 'failed', 'cases': [
            {'id': t['test_id'], 'status': 'passed' if repaired else 'failed', 'actual': repaired,
             'expected': t.get('expected')} for t in kwargs['tests']]}

    def assess(ttl, **kwargs):
        calls.append(('assessment', copy.deepcopy(kwargs)))
        return {'status': 'completed', 'denominators': {'candidate': {'questions': 1}}}

    monkeypatch.setattr(ex, 'validate', validate)
    monkeypatch.setattr(ex, 'assess', assess)
    return calls


@pytest.mark.parametrize('task', ['billing', 'inventory'])
def test_two_distinct_registered_tasks_preserve_frozen_inputs_and_ad_conditions(task, engines):
    inputs = packet_inputs(task)
    packet = ex.freeze_synthetic_task(**inputs)
    model = Model()
    rows = ex.execute_synthetic_task(packet, registration_digest=packet.digest, settings=SETTINGS, model_client=model)
    a, b, c, d = rows
    assert {r['task_id'] for r in rows} == {task}
    assert {r['protocol_id'] for r in rows} == {'synthetic-task-v1'}
    assert {r['task_registration_digest'] for r in rows} == {packet.digest}
    assert len({r['task_packet_digest'] for r in rows}) == 1
    assert b['budget'] == c['budget'] == d['budget']
    assert a['candidate_digest'] == b['candidate_digest'] != c['candidate_digest']
    assert c['generation_call_ids'] == d['generation_call_ids'] and c['candidate_digest'] == d['candidate_digest']
    assert d['review_status'] == 'waiting_human' and d['review_decisions'] == []
    assert d['post_review_snapshot'] is None and d['correction_seconds'] is None
    assert len({json.dumps(r['evaluation_inputs'], sort_keys=True) for r in rows}) == 1
    assert all(call[1]['fixtures_ttl'] == inputs['fixtures_ttl'] for call in engines if call[0] == 'validation')
    assert all(call[1]['mappings'] == [] for call in engines if call[0] == 'assessment')
    for context in model.calls:
        assert not {'tests', 'shapes_ttl', 'fixtures_ttl', 'mappings', 'held_out', 'evaluation'} & context.keys()
        assert all('sparql_query' not in q and 'expected' not in q for q in context['questions'])
        if context['stage'] != 'reasoner_repair':
            assert 'feedback' not in context
        else:
            assert context['feedback'] == [{'id': 'CQ-' + task, 'status': 'failed', 'expected': True, 'actual': False}]


def test_packet_copies_inputs_and_tamper_cannot_use_registered_digest(engines):
    inputs = packet_inputs()
    packet = ex.freeze_synthetic_task(**inputs)
    inputs['evidence'][0]['quote'] = 'Changed caller object'
    assert packet.to_dict()['evidence'][0]['quote'] != inputs['evidence'][0]['quote']
    changed = packet.to_dict()
    changed['instruction'] = 'Changed registered instruction'
    tampered = replace(packet, packet_json=canonical_json(changed).decode())
    with pytest.raises(ValueError, match='digest'):
        ex.execute_synthetic_task(tampered, registration_digest=packet.digest, settings=SETTINGS, model_client=Model())
    assert not engines


@pytest.mark.parametrize('field,value', [('split', 'held_out'), ('classification', 'public'),
                                       ('protocol_id', 'real-study'), ('held_out', {'answers': 'secret'})])
def test_self_contained_packet_verification_rejects_forbidden_protocol_and_split(field, value, engines):
    packet = ex.freeze_synthetic_task(**packet_inputs())
    changed = packet.to_dict()
    changed[field] = value
    tampered = replace(packet, packet_json=canonical_json(changed).decode())
    with pytest.raises(ValueError):
        ex.execute_synthetic_task(tampered, registration_digest=tampered.digest, settings=SETTINGS, model_client=Model())
    assert not engines


def test_required_question_oracle_and_additional_test_review_cannot_be_forged():
    inputs = packet_inputs()
    inputs['tests'][0]['expected'] = False
    with pytest.raises(ValueError, match='question'):
        ex.freeze_synthetic_task(**inputs)
    inputs = packet_inputs()
    inputs['tests'].append({'test_id': 'extra', 'kind': 'ask', 'query': 'ASK {}', 'expected': True,
                            'rationale': 'Unreviewed extra oracle'})
    with pytest.raises(ValueError, match='review'):
        ex.freeze_synthetic_task(**inputs)


def test_mixed_cases_have_all_case_pass_rate_and_separate_ask_answer_denominator():
    tests = [{'test_id': 'ask', 'kind': 'ask', 'expected': True},
             {'test_id': 'shape', 'kind': 'shacl', 'expected_conforms': False},
             {'test_id': 'select', 'kind': 'select_rows', 'expected': []}]
    report = {'status': 'passed', 'cases': [{'id': t['test_id'], 'status': 'passed', 'actual': actual}
                                          for t, actual in zip(tests, [True, {'conforms': False}, []])]}
    metrics, counts = ex.measurements(report, {'status': 'not_run'}, tests)
    assert counts['scheduled'] == 3 and counts['answer_scheduled'] == 1 and counts['unevaluable'] == 0
    assert metrics['reasoning_pass_rate']['denominator'] == 3
    assert metrics['answer_accuracy_required']['denominator'] == 1
    assert metrics['answer_precision']['value'] == 1


def test_existing_fixed_model_pilot_does_not_accept_registered_task_packet(engines):
    with pytest.raises(ValueError, match='scope'):
        ex.freeze_model_task(packet_inputs('inventory')['seed_ontology'], 'a' * 64)


def test_only_required_cq_failures_enter_repair_not_extra_reviewed_development_oracles(engines):
    inputs = packet_inputs()
    inputs['tests'].append({'test_id': 'accepted-extra', 'kind': 'ask', 'query': 'ASK {}', 'expected': True,
                            'oracle_status': 'accepted', 'oracle_decision_id': 'test-only-decision',
                            'rationale': 'Explicit synthetic test harness oracle'})
    packet, model = ex.freeze_synthetic_task(**inputs), Model()
    ex.execute_synthetic_task(packet, registration_digest=packet.digest, settings=SETTINGS, model_client=model)
    repairs = [c for c in model.calls if c['stage'] == 'reasoner_repair']
    assert all({v['id'] for v in call['feedback']} == {'CQ-billing'} for call in repairs)


def test_failed_generation_preserves_every_registered_task_arm_and_missing_scores(engines):
    class FailedModel(Model):
        def generate(self, *args):
            raise RuntimeError('Synthetic provider failure')
    packet = ex.freeze_synthetic_task(**packet_inputs())
    rows = ex.execute_synthetic_task(packet, registration_digest=packet.digest, settings=SETTINGS,
                                     model_client=FailedModel(), replicate_ids=[1, 2])
    assert len(rows) == 8 and not engines
    assert all(r['status'] == 'generation_error' and r['candidate_ttl'] is None for r in rows)
    assert all(r['case_counts']['scheduled'] == r['case_counts']['error'] == 1 for r in rows)
    assert all(r['answer_precision'] is None for r in rows)


@pytest.mark.parametrize('field,extra', [('seed_ontology', '<https://foreign.example/A> a <http://www.w3.org/2002/07/owl#Class> .'),
                                      ('seed_ontology', '<' + NS + 'A> <http://www.w3.org/2002/07/owl#imports> <https://remote.example/ontology> .'),
                                      ('shapes_ttl', '<' + NS + 'Shape> <http://www.w3.org/ns/shacl#sparql> "arbitrary query" .')])
def test_out_of_scope_or_executable_rdf_is_rejected_before_models(field, extra):
    inputs = packet_inputs()
    inputs[field] += extra
    with pytest.raises(ValueError):
        ex.freeze_synthetic_task(**inputs)


def test_query_prefix_names_inside_literals_and_outer_bytes_are_preserved():
    inputs = packet_inputs()
    query = f'  PREFIX demo: <{NS}> ASK {{ demo:BillingExample <http://www.w3.org/2000/01/rdf-schema#label> "demo:example" }}\n'
    inputs['questions'][0]['sparql_query'] = query
    inputs['tests'][0]['query'] = query
    packet = ex.freeze_synthetic_task(**inputs)
    assert packet.to_dict()['questions'][0]['sparql_query'] == query
    assert packet.to_dict()['tests'][0]['query'] == query
    assert packet.to_dict()['seed_ontology'] == inputs['seed_ontology']


def test_reviewed_mapping_is_identical_for_every_assessment_and_absent_from_model(engines):
    inputs = packet_inputs()
    mapping = {'requirement_iri': NS + 'Billing', 'ontology_iri': NS + 'BillingSpecial',
               'relation_type': 'canonical_correspondence', 'rationale': 'Synthetic mapping contract fixture.',
               'evidence_ids': ['evidence-billing'], 'reviewer': 'test-only-human', 'review_id': 'test-only-review'}
    inputs['mappings'] = [mapping]
    packet, model = ex.freeze_synthetic_task(**inputs), Model()
    ex.execute_synthetic_task(packet, registration_digest=packet.digest, settings=SETTINGS, model_client=model)
    assert all(call[1]['mappings'] == [mapping] for call in engines if call[0] == 'assessment')
    assert all('mappings' not in call for call in model.calls)


def test_registered_d_human_snapshot_keeps_original_workload_and_registration(engines):
    packet = ex.freeze_synthetic_task(**packet_inputs())
    pre = ex.execute_synthetic_task(packet, registration_digest=packet.digest, settings=SETTINGS,
                                    condition='D', model_client=Model())[0]
    before = copy.deepcopy(pre)
    revision = {'id': 'rev-2', 'proposal_id': 'proposal', 'revision': 2, 'bundle_digest': 'c' * 64,
                'experiment_run_id': pre['id'], 'experiment_pre_candidate_digest': pre['candidate_digest'],
                'manifest': {'canonical_ontology_sha256': pre['candidate_digest']}}
    review = {'id': 'test-only-review', 'revision_id': 'rev-2', 'proposal_id': 'proposal', 'revision': 2,
              'bundle_digest': 'c' * 64, 'decision': 'accept', 'validation_run_id': 'validation',
              'required_assessment_run_ids': ['assessment'],
              'actor': {'kind': 'human', 'subject': 'test-only-reviewer', 'roles': ['approver']}}
    validation = {'id': 'validation', 'revision_id': 'rev-2', 'bundle_digest': 'c' * 64, 'status': 'passed'}
    assessment = {**validation, 'id': 'assessment', 'status': 'completed'}
    post = ex.append_human_review(pre, reviewed_revision=revision, review=review,
        ontology_ttl=pre['candidate_ttl'], validation_report=validation, assessment_report=assessment)
    assert pre == before and post['parent_record_digest'] == pre['record_digest']
    assert post['task_registration_digest'] == packet.digest
    assert post['evaluation_inputs'] == pre['evaluation_inputs']
    assert post['correction_seconds'] is None and post['phase'] == 'post_review'
