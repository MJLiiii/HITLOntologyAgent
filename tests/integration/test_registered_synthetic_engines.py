"""Two authored tasks, scripted model double, real confined engines; no study."""
from types import SimpleNamespace

import pytest

from oe_studio import experiments as ex
from oe_studio.demo import NS, PREFIX


@pytest.mark.parametrize('task', ['billing', 'inventory'])
def test_two_registered_tasks_execute_their_own_frozen_workloads_with_real_engines(task):
    title = task.title()
    seed = PREFIX + f'''demo:{title} a owl:Class . demo:{title}Special a owl:Class .
demo:hasOwner a owl:ObjectProperty . demo:Team a owl:Class . demo:Owner a demo:Team .'''
    fixture = PREFIX + f'demo:{title}Example a demo:{title}Special ; demo:hasOwner demo:Owner ; rdfs:label "Example"@en .'
    shapes = PREFIX + f'''@prefix sh: <http://www.w3.org/ns/shacl#> .
demo:{title}Shape a sh:NodeShape ; sh:targetClass demo:{title} ;
 sh:property [ sh:path demo:hasOwner ; sh:minCount 1 ; sh:nodeKind sh:IRI ] .'''
    query = f'PREFIX ex: <{NS}> ASK {{ ex:{title}Example a ex:{title} }}'
    tests = [{'test_id': 'CQ-' + task, 'kind': 'ask', 'query': query, 'expected': True},
             {'test_id': 'missing-' + task, 'kind': 'shacl', 'expected_conforms': False,
              'fixtures_ttl': fixture + f'\ndemo:Missing{title} a demo:{title} .',
              'oracle_status': 'accepted', 'oracle_decision_id': 'test-only-oracle',
              'rationale': 'Synthetic test-only required-owner violation'},
             {'test_id': 'label-' + task, 'kind': 'select_rows',
              'query': f'SELECT ?label WHERE {{ <{NS}{title}Example> <http://www.w3.org/2000/01/rdf-schema#label> ?label }}',
              'expected': [{'label': {'kind': 'literal', 'value': 'Example', 'lang': 'en',
                                      'datatype': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#langString'}}],
              'oracle_status': 'accepted', 'oracle_decision_id': 'test-only-oracle',
              'rationale': 'Synthetic test-only lexical preservation'}]
    packet = ex.freeze_synthetic_task(task_id=task, instruction=f'Model the synthetic {task} specialization.',
        bundle_digest='a' * 64, base_ontology='', seed_ontology=seed, shapes_ttl=shapes, fixtures_ttl=fixture,
        questions=[{'id': 'CQ-' + task, 'question': f'Is the {task} example classified by its specialization?',
                    'sparql_query': query, 'expected': True, 'required': True}], tests=tests,
        evidence=[{'id': 'source-' + task, 'document_id': 'doc-' + task, 'classification': 'synthetic',
                   'source_sha256': 'b' * 64, 'resolved': True,
                   'quote': f'{title}Special is a kind of {title}. Every example has an owner.'}])

    class ScriptedModelDouble:
        def generate(self, system, context, schema):
            changes = []
            if context['stage'] == 'reasoner_repair':
                changes = [{'operation': 'add', 'triple': {'subject': NS + title + 'Special',
                            'predicate': 'http://www.w3.org/2000/01/rdf-schema#subClassOf', 'object': NS + title},
                            'evidence_ids': ['source-' + task], 'rationale': 'The synthetic fixture explicitly states this hierarchy.'}]
            return schema.model_validate({'summary': 'Scripted test double for the generation boundary.', 'changes': changes}), {
                'input_tokens': None, 'output_tokens': None, 'cost': None}

    settings = SimpleNamespace(model_url='http://localhost:11434', model_name='unused-scripted-test-double', model_timeout=10)
    a, b, c, d = ex.execute_synthetic_task(packet, registration_digest=packet.digest, settings=settings,
                                           model_client=ScriptedModelDouble(), maximum_repairs=1)
    assert a['validation']['status'] == b['validation']['status'] == 'failed'
    assert c['validation']['status'] == d['validation']['status'] == 'passed', c['validation']
    assert all(r['assessment']['status'] == 'completed' for r in (a, b, c, d))
    assert all(r['case_counts']['scheduled'] == 3 and r['case_counts']['answer_scheduled'] == 1 for r in (a, b, c, d))
    assert c['answer_recall'] == 1 and a['answer_recall'] == 0
    assert c['generation_call_ids'] == d['generation_call_ids']
    assert {r['evaluation_inputs']['fixtures_ttl'] for r in (a, b, c, d)} == {fixture}
    assert d['status'] == 'waiting_human' and d['review_decisions'] == []
