"""Real isolated Jena and synthetic temporary workflow state; no study approvals."""
import json
from uuid import uuid4
import pytest

from fastapi.testclient import TestClient

from oe_studio import demo
from oe_studio.main import create_app
from oe_studio.settings import Settings
from oe_studio.testspecs import generate_suite
from oe_studio.validation import validate


def generated(**updates):
    params = dict(candidate_ttl=demo.ONTOLOGY, shapes_ttl=demo.SHAPES, fixtures_ttl=demo.FIXTURES,
                  questions=demo.QUESTIONS, changes={'additions': [], 'deletions': []},
                  evidence=[{'id': 'synthetic-test-evidence', 'resolved': True}], bundle_digest='a' * 64)
    params.update(updates)
    return generate_suite(**params)


@pytest.mark.parametrize('named_shape', [False, True])
def test_all_generated_scenarios_execute_in_real_jena_with_exact_violation_signatures(named_shape):
    shapes = demo.SHAPES.replace('sh:minCount 1', 'sh:minCount 1 ; sh:maxCount 1 ; sh:name "Eigenaar:é|x"@nl')
    if named_shape:
        shapes = shapes.replace('sh:property [ ', 'sh:property demo:OwnerProperty . demo:OwnerProperty ').replace(' ] .', ' .')
    suite = generated(shapes_ttl=shapes)
    report = validate(demo.ONTOLOGY, bundle_digest='a' * 64, shapes_ttl=shapes,
                      fixtures_ttl=demo.FIXTURES, tests=suite['tests'])
    assert report['status'] == 'passed', report
    assert {case['id'] for case in report['cases']} == {test['test_id'] for test in suite['tests']}
    for test in suite['tests']:
        if test['kind'] == 'shacl':
            case = next(c for c in report['cases'] if c['id'] == test['test_id'])
            assert case['actual']['violations'] == test['expected_violations']
    assert report['engine']['isolation']['network'] == 'kernel-denied'
    assert report['raw_artifacts']['shacl-report.ttl']


def test_generated_oracle_detects_removed_inference_and_weakened_required_shape():
    suite = generated()
    inference = next(t for t in suite['tests'] if t['kind'] == 'ask'
                     and 'axiom-0/subject' in t.get('query', '') and t['expected'] is True)
    broken = demo.ONTOLOGY.replace('rdfs:subClassOf demo:Service ;', '')
    report = validate(broken, bundle_digest='b' * 64, shapes_ttl=demo.SHAPES,
                      fixtures_ttl=demo.FIXTURES, tests=[inference])
    assert report['status'] == 'failed' and report['cases'][0]['actual'] is False, report
    missing = next(t for t in suite['tests'] if t['scenario'] == 'missing_data')
    report = validate(demo.ONTOLOGY, bundle_digest='c' * 64,
                      shapes_ttl=demo.SHAPES.replace('sh:minCount 1', 'sh:minCount 0'),
                      fixtures_ttl=demo.FIXTURES, tests=[missing])
    assert report['status'] == 'failed' and report['cases'][0]['actual']['conforms'] is True, report


@pytest.mark.parametrize('datatype', ['string', 'integer', 'decimal', 'boolean'])
def test_generated_typed_literal_boundaries_have_distinct_values_and_exact_failures(datatype):
    ttl = demo.PREFIX + 'demo:Item a owl:Class . demo:code a owl:DatatypeProperty .'
    shapes = ('@prefix sh: <http://www.w3.org/ns/shacl#> . ' + demo.PREFIX
              + f'demo:ItemShape a sh:NodeShape ; sh:targetClass demo:Item ; sh:property [ sh:path demo:code ; '
                f'sh:minCount 1 ; sh:maxCount 1 ; sh:nodeKind sh:Literal ; sh:datatype <http://www.w3.org/2001/XMLSchema#{datatype}> ] .')
    questions = [{'id': 'typed-cq', 'sparql_query': f'ASK {{ <{demo.NS}Item> a <http://www.w3.org/2002/07/owl#Class> }}', 'expected': True}]
    suite = generated(candidate_ttl=ttl, shapes_ttl=shapes, fixtures_ttl='', questions=questions)
    report = validate(ttl, bundle_digest='e' * 64, shapes_ttl=shapes, tests=suite['tests'])
    assert report['status'] == 'passed', report


def test_generated_development_suite_requires_oracle_decision_then_validates_successor(tmp_path):
    app = create_app(Settings(_env_file=None, llm_config_file=None, data_dir=tmp_path, eager_jobs=True))
    with TestClient(app) as client:
        client.get('/api/v1/session', headers={'X-OE-Session-Token': app.state.bootstrap_token})
        project = client.get('/api/v1/projects').json()['items'][0]
        root = '/api/v1/projects/' + project['id']

        def job(kind, payload):
            queued = client.post(root + '/' + kind + '-jobs', json=payload,
                                 headers={'Idempotency-Key': str(uuid4())})
            assert queued.status_code == 202, queued.text
            response = client.get('/api/v1/jobs/' + queued.json()['job_id']).json()
            assert response['status'] == 'succeeded', response
            return response['result']

        proposal = job('proposal', {'base_version_id': None, 'corpus_snapshot_id': project['corpus_snapshot_id'],
                                    'instruction': 'Create the neutral synthetic candidate'})
        suite = job('test-generation', {'proposal_id': proposal['proposal_id'], 'revision': 1})
        assert suite['status'] == 'needs_review'
        assert suite['generator']['mode'] == 'deterministic_candidate_derived'
        with app.state.studio.db.session() as session:
            old = app.state.studio.revision(session, project['id'], proposal['proposal_id'], 1)
            original_tests = json.loads(app.state.studio.artifacts.get_verified(old.data['tests']))
            original_bundle = old.data['bundle_digest']
        assert {t['test_id'] for t in original_tests} == {'CQ-01', 'CQ-02'}
        accepted = client.post(root + '/test-oracle-decisions', json={
            'test_suite_id': suite['id'], 'test_suite_digest': suite['digest'], 'decision': 'accept',
            'rationale': 'Synthetic contract test decision in temporary state only; verify frozen RDFS and SHACL expectations'})
        assert accepted.status_code == 201, accepted.text
        successor = accepted.json()
        assert successor['revision'] == 2 and successor['bundle_digest'] != original_bundle
        report = job('validation', {'proposal_id': proposal['proposal_id'], 'revision': 2,
                                    'bundle_digest': successor['bundle_digest']})
        assert report['status'] == 'passed', report
        assert {c['id'] for c in report['cases']} == {'CQ-01', 'CQ-02', *(t['test_id'] for t in suite['tests'])}
        with app.state.studio.db.session() as session:
            old = app.state.studio.revision(session, project['id'], proposal['proposal_id'], 1)
            assert old.data['bundle_digest'] == original_bundle
            assert json.loads(app.state.studio.artifacts.get_verified(old.data['tests'])) == original_tests
        assert client.get(root).json()['approved_version_id'] is None
