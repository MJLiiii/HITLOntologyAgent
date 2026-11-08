"""Integration contracts: a real Jena process must earn a successful result."""
import json
import subprocess

import pytest


ONTOLOGY = '''@prefix ex: <https://example.org/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:Person a owl:Class . ex:Employee a owl:Class ; rdfs:subClassOf ex:Person .
ex:name a owl:DatatypeProperty .
'''
FIXTURE = '<https://example.org/alice> a <https://example.org/Employee> .'
ASK = 'ASK { <https://example.org/alice> a <https://example.org/Person> }'
SHAPES = '''@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <https://example.org/> .
ex:PersonShape a sh:NodeShape; sh:targetClass ex:Person; sh:property ex:NameShape .
ex:NameShape sh:path ex:name; sh:minCount 1 .'''


def validate(*args, **kwargs):
    from oe_studio.validation import validate as run
    return run(*args, bundle_digest='a' * 64, **kwargs)


def test_subclass_inference_answers_cq():
    report = validate(ONTOLOGY, fixtures_ttl=FIXTURE,
                      tests=[{'id': 'CQ-01', 'kind': 'ask', 'query': ASK, 'expected': True}])
    assert report['status'] == 'passed', report
    assert report['cases'][0]['actual'] is True
    assert report['engine']['name'] == 'Apache Jena'
    assert report['bundle_digest'] == 'a' * 64
    assert report['metrics']['inferred_triples'] > 0


def test_wrong_inference_fails_case():
    report = validate(ONTOLOGY, fixtures_ttl=FIXTURE,
                      tests=[{'id': 'wrong', 'kind': 'ask', 'query': ASK, 'expected': False}])
    assert report['status'] == 'failed'
    assert report['cases'][0]['status'] == 'failed'


def test_expected_shacl_violation_passes_case():
    report = validate(ONTOLOGY, shapes_ttl=SHAPES, tests=[{
        'id': 'missing-name', 'kind': 'shacl', 'fixtures_ttl': FIXTURE,
        'expected_conforms': False,
        'expected_violations': [{'focusNode': 'https://example.org/alice',
                                'path': 'https://example.org/name',
                                'sourceShape': 'https://example.org/NameShape',
                                'severity': 'http://www.w3.org/ns/shacl#Violation'}],
    }])
    assert report['status'] == 'passed', report
    assert report['cases'][0]['actual']['conforms'] is False


def test_required_data_shape_fails_but_valid_data_passes():
    assert validate(ONTOLOGY, shapes_ttl=SHAPES, fixtures_ttl=FIXTURE)['status'] == 'failed'
    valid = FIXTURE + '\n<https://example.org/alice> <https://example.org/name> "Alice" .'
    assert validate(ONTOLOGY, shapes_ttl=SHAPES, fixtures_ttl=valid)['status'] == 'passed'


def test_select_preserves_typed_and_language_tagged_bindings():
    report = validate(ONTOLOGY, fixtures_ttl=FIXTURE + '\n<https://example.org/alice> <https://example.org/name> "Alice"@en .',
                      tests=[{'id': 'names', 'kind': 'select_rows',
                              'query': 'SELECT ?name WHERE { <https://example.org/alice> <https://example.org/name> ?name }',
                              'expected': [{'name': {'kind': 'literal', 'value': 'Alice', 'lang': 'en',
                                                    'datatype': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#langString'}}]}])
    assert report['status'] == 'passed', report


@pytest.mark.parametrize('query', [
    'ASK { SERVICE <http://127.0.0.1:1/> { ?s ?p ?o } }',
    'DELETE WHERE { ?s ?p ?o }',
    'ASK FROM <file:///etc/passwd> { ?s ?p ?o }',
    'ASK { FILTER(<https://evil.example/function>(1)) }',
    'SELECT (IRI("file:///etc/passwd") AS ?x) WHERE {}',
])
def test_unsafe_queries_are_rejected(query):
    report = validate(ONTOLOGY, tests=[{'id': 'unsafe', 'kind': 'ask', 'query': query, 'expected': True}])
    assert report['status'] == 'unsupported', report


@pytest.mark.parametrize('extra', [
    '<https://example.org/o> <http://www.w3.org/2002/07/owl#imports> <http://127.0.0.1:1/remote> .',
    '<https://example.org/A> <http://www.w3.org/2002/07/owl#equivalentClass> <https://example.org/B> .',
    '<https://example.org/p> a <http://www.w3.org/2002/07/owl#TransitiveProperty> .',
    '<https://example.org/A> <http://www.w3.org/2000/01/rdf-schema#subClassOf> [ a <http://www.w3.org/2002/07/owl#Restriction> ] .',
])
def test_unsupported_construct_blocks_validation(extra):
    assert validate(ONTOLOGY + extra)['status'] == 'unsupported'


def test_malformed_rdf_is_error():
    assert validate('this is not Turtle')['status'] == 'error'


def test_shacl_sparql_is_rejected_before_execution():
    shapes = SHAPES + '\n<https://example.org/PersonShape> <http://www.w3.org/ns/shacl#sparql> [ <http://www.w3.org/ns/shacl#select> "SELECT ?this WHERE { SERVICE <http://127.0.0.1:1/> {?this ?p ?o} }" ] .'
    assert validate(ONTOLOGY, shapes_ttl=shapes)['status'] == 'unsupported'


def test_timeout_never_passes(monkeypatch):
    import oe_studio.validation as validation
    monkeypatch.setattr(validation, 'TIMEOUT_SECONDS', 0.001)
    assert validate(ONTOLOGY)['status'] == 'timeout'


def test_missing_runner_never_passes(monkeypatch, tmp_path):
    import oe_studio.validation as validation
    monkeypatch.setattr(validation, 'RUNNER_JAR', tmp_path / 'missing.jar')
    assert validate(ONTOLOGY)['status'] == 'error'


def test_missing_report_is_error(monkeypatch):
    import oe_studio.validation as validation
    # The process boundary is the only double: a crashed/misconfigured engine can exit 0 without output.
    monkeypatch.setattr(validation, 'run_engine', lambda *a, **kw: subprocess.CompletedProcess(a[0], 0))
    assert validate(ONTOLOGY)['status'] == 'error'


def test_manifest_hash_mismatch_is_error(tmp_path):
    from oe_studio.validation import JAVA_EXECUTABLE, RUNNER_JAR
    ontology = tmp_path / 'ontology.ttl'
    ontology.write_text(ONTOLOGY)
    manifest = {'schema_version': 1, 'bundle_digest': 'a' * 64,
                'expected_runner_version': '0.1.0', 'inference_mode': 'rdfs',
                'validation_graph': 'asserted_plus_inferred',
                'artifacts': {'ontology': {'path': 'ontology.ttl', 'sha256': '0' * 64}}}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    result = subprocess.run([str(JAVA_EXECUTABLE), '-jar', str(RUNNER_JAR), '--manifest', str(tmp_path / 'manifest.json')],
                            cwd=tmp_path, capture_output=True, timeout=20)
    assert result.returncode == 3
    assert json.loads((tmp_path / 'report.json').read_text())['status'] == 'error'


def test_prefixed_bundle_digest_is_preserved_exactly():
    from oe_studio.validation import validate as run
    digest = 'sha256:' + 'b' * 64
    report = run(ONTOLOGY, bundle_digest=digest)
    assert report['status'] == 'passed', report
    assert report['bundle_digest'] == digest
    assert report['input_manifest']['bundle_digest'] == digest
