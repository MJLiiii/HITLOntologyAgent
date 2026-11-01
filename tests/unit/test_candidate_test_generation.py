import hashlib

import pytest
from pydantic import ValidationError
from rdflib import Graph, BNode, RDF

from oe_studio import demo
from oe_studio.schemas import TestSpec as Spec
from oe_studio.testspecs import generate_suite, leaf_shape_id


def inputs(**updates):
    return {**dict(candidate_ttl=demo.ONTOLOGY, shapes_ttl=demo.SHAPES,
                   fixtures_ttl=demo.FIXTURES, questions=demo.QUESTIONS,
                   changes={'additions': [], 'deletions': []},
                   evidence=[{'id': 'source-1', 'resolved': True, 'quote': 'Synthetic source packet'}],
                   bundle_digest='sha256:' + 'a' * 64), **updates}


def test_candidate_generation_has_reviewable_scenarios_and_frozen_input_identity():
    suite = generate_suite(**inputs())
    assert suite['generator']['mode'] == 'deterministic_candidate_derived'
    assert {test['scenario'] for test in suite['tests']} == {
        'positive', 'negative', 'boundary', 'contradictory', 'missing_data', 'regression'}
    assert all(t['oracle_status'] == 'needs_review' and t['split'] == 'development' for t in suite['tests'])
    assert all(t['target_ontology_sha256'] == hashlib.sha256(demo.ONTOLOGY.encode()).hexdigest()
               for t in suite['tests'])
    assert {q for t in suite['tests'] for q in t['question_ids']} >= {'CQ-01', 'CQ-02'}
    assert all(t['assumptions'] and t['oracle_source'] for t in suite['tests'])
    assert suite == generate_suite(**inputs())


def test_changed_candidate_terms_and_language_literals_derive_different_cases():
    ttl = demo.ONTOLOGY.replace('CriticalService', 'UrgentService') + '\n' + demo.PREFIX + 'demo:PayrollService rdfs:label "Betalingen"@nl .'
    change = {'subject': demo.NS + 'PayrollService', 'predicate': 'http://www.w3.org/2000/01/rdf-schema#label',
              'object': 'Betalingen', 'object_type': 'literal', 'language': 'nl'}
    suite = generate_suite(**inputs(candidate_ttl=ttl, changes={'additions': [change], 'deletions': []}))
    assert any('UrgentService' in t.get('fixtures_ttl', '') for t in suite['tests'])
    literal = next(t for t in suite['tests'] if t['kind'] == 'select_rows')
    assert literal['expected'] == [{'value': {'kind': 'literal', 'value': 'Betalingen', 'lang': 'nl',
                                            'datatype': str(RDF.langString)}}]
    assert literal['comparison'] == 'contains' and literal['change_ids']
    assert suite['input_manifest']['changes'][0]['id'] in literal['change_ids']
    assert {t['test_id'] for t in suite['tests']} != {t['test_id'] for t in generate_suite(**inputs())['tests']}


def test_missing_data_and_explicit_constraint_contradiction_have_distinct_oracles():
    suite = generate_suite(**inputs())
    missing = next(t for t in suite['tests'] if t['scenario'] == 'missing_data')
    contradiction = next(t for t in suite['tests'] if t['scenario'] == 'contradictory')
    assert missing['expected_conforms'] is contradiction['expected_conforms'] is False
    assert missing['expected_violations'] and contradiction['expected_violations']
    assert 'not OWL negation' in missing['rationale']
    assert 'constraint' in contradiction['rationale']
    assert any(t['scenario'] == 'negative' and t['expected'] is False for t in suite['tests'])


def test_leaf_shape_signature_is_stable_and_preserves_datatypes_language_and_delimiters():
    text = '@prefix sh: <http://www.w3.org/ns/shacl#> . [] sh:path <https://example.org/p> ; sh:name "a:b|c"@nl ; sh:minCount 1 .'
    graphs = [Graph().parse(data=text, format='turtle') for _ in range(2)]
    ids = [leaf_shape_id(g, next(s for s in g.subjects() if isinstance(s, BNode))) for g in graphs]
    assert ids[0] == ids[1] and ids[0].startswith('urn:oe:shacl-leaf:sha256:')
    changed = Graph().parse(data=text.replace('@nl', '@en'), format='turtle')
    assert leaf_shape_id(changed, next(changed.subjects())) != ids[0]


@pytest.mark.parametrize('query', [
    'ASK { SERVICE <https://example.org/remote> { ?s ?p ?o } }',
    'ASK FROM <file:///etc/passwd> { ?s ?p ?o }',
    'INSERT DATA { <https://example.org/s> <https://example.org/p> <https://example.org/o> }',
])
def test_untrusted_requirement_queries_cannot_add_remote_or_executable_operations(query):
    with pytest.raises(ValueError, match='query'):
        generate_suite(**inputs(questions=[{'id': 'untrusted', 'sparql_query': query, 'expected': True}]))


def test_heldout_and_unresolved_evidence_cannot_enter_generation():
    with pytest.raises(ValueError, match='development'):
        generate_suite(**inputs(questions=[{**demo.QUESTIONS[0], 'split': 'held_out'}]))
    with pytest.raises(ValueError, match='resolved'):
        generate_suite(**inputs(evidence=[{'id': 'bad', 'resolved': False}]))


def test_complex_shape_reports_coverage_gap_without_inventing_expected_outcomes():
    shapes = demo.SHAPES.replace('sh:minCount 1', 'sh:pattern "owner.*"')
    suite = generate_suite(**inputs(shapes_ttl=shapes))
    assert any(g['code'] == 'unsupported_shape' for g in suite['coverage_gaps'])
    assert not any(t['kind'] == 'shacl' for t in suite['tests'])


def test_schema_requires_matching_oracles_and_rejects_arbitrary_runner_options():
    for invalid in [{'expected': 'true'}, {'query': None}, {'inference_mode': 'owl'},
                    {'timeout_seconds': 999}, {'rules': 'arbitrary rule'}, {'imports': ['remote']}]:
        with pytest.raises(ValidationError):
            Spec(**{'test_id': 'bad', 'kind': 'ask', 'query': 'ASK {}', 'expected': True,
                    'rationale': 'Test schema contract', **invalid})


def test_case_limit_is_explicit_and_does_not_redefine_frozen_question_expectations():
    extra = '\n'.join(f'<{demo.NS}C{i}> <{RDF.type}> <http://www.w3.org/2002/07/owl#Class> ; '
                      f'<http://www.w3.org/2000/01/rdf-schema#subClassOf> <{demo.NS}Service> .' for i in range(60))
    questions = [{**demo.QUESTIONS[0], 'expected': False}, demo.QUESTIONS[1]]
    suite = generate_suite(**inputs(candidate_ttl=demo.ONTOLOGY + extra, questions=questions))
    assert len(suite['tests']) == 40 and any(g['code'] == 'case_limit' for g in suite['coverage_gaps'])
    regression = next(t for t in suite['tests'] if t['scenario'] == 'regression' and 'CQ-01' in t['oracle_source'])
    assert regression['expected'] is False


@pytest.mark.parametrize('replacement', ['sh:minCount 1.5', 'sh:minCount true',
    'sh:minCount 2 ; sh:datatype <http://www.w3.org/2001/XMLSchema#boolean>'])
def test_unrepresentable_count_or_finite_datatype_boundary_is_a_coverage_gap(replacement):
    shapes = demo.SHAPES.replace('sh:minCount 1 ; sh:nodeKind sh:IRI', replacement)
    suite = generate_suite(**inputs(shapes_ttl=shapes))
    assert any(g['code'] == 'unsupported_shape' for g in suite['coverage_gaps'])
