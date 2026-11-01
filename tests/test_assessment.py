"""Real isolated OntoCheck contracts; no approximate score may authorize a mapping."""
import pytest

NS = 'https://example.org/oe-demo/'
ONTOLOGY = '''@prefix ex: <https://example.org/oe-demo/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:Asset a owl:Class ; rdfs:label "Asset" .
ex:Owner a owl:Class ; rdfs:label "Owner" .
ex:ownedBy a owl:ObjectProperty ; rdfs:domain ex:Asset ; rdfs:range ex:Owner .
'''
QUERY = 'PREFIX ex: <https://example.org/oe-demo/> SELECT ?asset WHERE { ?asset a ex:Asset ; ex:ownedBy ?owner . ?owner a ex:Owner . }'


def assess(ttl=ONTOLOGY, **kwargs):
    from oe_studio.assessment import assess as run
    kwargs.setdefault('questions', [{'id': 'CQ-1', 'question': 'Who owns an asset?',
                                     'sparql_query': QUERY, 'required': True}])
    return run(ttl, bundle_digest='a' * 64, **kwargs)


def test_real_offline_assessment_and_base_deltas():
    report = assess(base_ttl=ONTOLOGY.replace('ex:Owner a owl:Class ; rdfs:label "Owner" .', ''))
    assert report['status'] == 'completed', report
    assert report['vocabulary_coverage'] == 1.0
    assert report['strict_fitness'] == 1.0
    assert report['structural_fitness'] == 1.0
    assert report['denominators']['candidate']['task_terms'] == 3
    assert report['raw']['candidate']['vocabulary']['intersection'] == 3
    assert report['mappings'] == []
    assert report['bundle_digest'] == 'a' * 64
    assert report['engine']['name'] == 'OntoCheck'
    assert report['engine']['network'] == 'disabled'
    assert report['deltas']['vocabulary_coverage'] == pytest.approx(1 / 3)


def test_local_name_collisions_block_required_assessment():
    report = assess(ONTOLOGY + '<https://different.example/Asset> a owl:Class .')
    assert report['status'] == 'unsupported', report
    assert any('collision' in x.lower() for x in report['limitations'])
    assert report['vocabulary_coverage'] is None


@pytest.mark.parametrize('questions', [[], [{'id': 'no-query', 'required': True}],
    [{'id': 'bad', 'required': True, 'sparql_query': 'NOT SPARQL ex:Asset'}],
    [{'id': 'iri', 'required': True, 'sparql_query': 'ASK { ?x a <https://example.org/oe-demo/Asset> }'}],
    [{'id': 'remote', 'required': True, 'sparql_query': 'ASK { SERVICE <http://127.0.0.1:1/> { ?s ?p ?o } }'}]])
def test_unsupported_questions_never_become_success(questions):
    report = assess(questions=questions)
    assert report['status'] == 'unsupported', report
    assert report['strict_fitness'] is None


def test_empty_ontology_normalizes_undefined_denominator():
    report = assess('@prefix ex: <https://example.org/oe-demo/> .')
    assert report['status'] == 'unsupported', report
    assert report['raw']['candidate']['vocabulary']['T_o_count'] == 0
    assert report['vocabulary_utilisation'] is None


def test_malformed_rdf_is_error():
    assert assess('malformed Turtle }')['status'] == 'error'


def test_timeout_never_returns_success(monkeypatch):
    monkeypatch.setenv('OE_ONTOCHECK_TIMEOUT_SECONDS', '0.001')
    report = assess()
    assert report['status'] == 'timeout', report
    assert report['strict_fitness'] is None


def test_missing_runtime_never_returns_fake_scores(monkeypatch, tmp_path):
    monkeypatch.setenv('OE_ONTOCHECK_PYTHON', str(tmp_path / 'missing-python'))
    report = assess()
    assert report['status'] == 'error', report
    assert report['raw'] == {}


def test_remote_imports_are_rejected_without_fetching():
    report = assess(ONTOLOGY + '<https://example.org/oe-demo/> <http://www.w3.org/2002/07/owl#imports> <http://127.0.0.1:1/ontology> .')
    assert report['status'] == 'unsupported', report


@pytest.mark.parametrize('query', [
    QUERY + ' # ex:InventedTerm',
    QUERY.replace('ex:ownedBy', 'ex:ownedBy/ex:ownedBy'),
    QUERY.replace('?owner a ex:Owner .', 'OPTIONAL { ?owner a ex:Owner . }'),
    QUERY.replace('?owner a ex:Owner .', '?owner a ex:Owner . FILTER(?asset = ?owner)'),
    QUERY.replace('ex:Owner', 'other:Owner').replace('SELECT', 'PREFIX other: <https://other.example/> SELECT'),
])
def test_question_semantics_cannot_be_silently_flattened(query):
    report = assess(questions=[{'id': 'unsupported-semantics', 'sparql_query': query}])
    assert report['status'] == 'unsupported', report
    assert report['strict_fitness'] is None


def test_prefix_rebinding_is_not_an_authorized_mapping():
    report = assess(ONTOLOGY.replace(NS, 'https://different.example/'))
    assert report['status'] == 'unsupported', report
    assert report['strict_fitness'] == 0.0
    assert report['raw']['candidate']['conceptual']['detail']['tiers']['exact_via_prefix_mapping'] == 0


def test_missing_schema_path_is_reported_separately_from_vocabulary():
    report = assess(ONTOLOGY.replace(' ; rdfs:range ex:Owner', ''))
    assert report['status'] == 'completed', report
    assert report['vocabulary_coverage'] == 1.0
    assert report['structural_fitness'] == 0.0
    assert report['raw']['candidate']['structural']['affected']


def test_no_edge_workload_keeps_missing_structural_score_and_reason():
    report = assess(questions=[{'id': 'class-only', 'sparql_query':
        'PREFIX ex: <https://example.org/oe-demo/> ASK { ?asset a ex:Asset }'}])
    assert report['status'] == 'completed', report
    assert report['structural_fitness'] is None
    assert report['missing_reasons']['structural_fitness']


def test_identical_inputs_preserve_raw_outputs_and_term_sets():
    first, second = assess(), assess()
    assert first['status'] == second['status'] == 'completed'
    assert first['raw'] == second['raw']
    assert first['questions_sha256'] == second['questions_sha256']
    assert first['raw']['candidate']['term_sets'] == {
        'task': ['Asset', 'Owner', 'ownedBy'], 'ontology': ['Asset', 'Owner', 'ownedBy'],
        'intersection': ['Asset', 'Owner', 'ownedBy'],
    }


def test_offline_worker_blocks_network_and_child_processes():
    import subprocess
    from oe_studio.assessment import ROOT
    worker = ROOT / 'services/api/src/oe_studio/assessment_worker.py'
    program = f'''import runpy, socket, subprocess
worker = runpy.run_path({str(worker)!r})
worker['disable_network_and_children']()
for action in (lambda: socket.create_connection(('127.0.0.1', 1)),
               lambda: subprocess.run(['/bin/true'])):
    try:
        action()
    except PermissionError:
        pass
    else:
        raise AssertionError('Offline worker allowed a forbidden side effect')
'''
    result = subprocess.run([str(ROOT / '.venv-ontocheck/bin/python'), '-I', '-c', program],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_incomplete_success_report_is_an_error(monkeypatch):
    import subprocess
    import oe_studio.assessment as assessment
    monkeypatch.setattr(assessment.subprocess, 'run', lambda *a, **kw:
        subprocess.CompletedProcess(a[0], 0, stdout='{"status":"completed"}', stderr=''))
    report = assess()
    assert report['status'] == 'error', report


def test_keyword_as_local_name_is_a_domain_term():
    report = assess(ONTOLOGY + 'ex:Service a owl:Class .', questions=[{
        'id': 'services', 'sparql_query': 'PREFIX ex: <https://example.org/oe-demo/> ASK { ?s a ex:Service }'}])
    assert report['status'] == 'completed', report


def approved_mapping(**changes):
    return {'requirement_iri': NS + 'Asset', 'ontology_iri': NS + 'Resource',
            'relation_type': 'canonical_correspondence', 'reviewer': 'local:reviewer',
            'review_id': 'mapping-review-1', 'rationale': 'The reviewed resource denotes the required asset.',
            'evidence_ids': ['evidence-1'], **changes}


def test_reviewed_mapping_changes_strict_support_without_rewriting_vocabulary_or_rdf():
    renamed = ONTOLOGY.replace('ex:Asset', 'ex:Resource')
    suggested = assess(renamed)
    reviewed = assess(renamed, mappings=[approved_mapping()])
    assert suggested['status'] == reviewed['status'] == 'completed', reviewed
    assert suggested['strict_fitness'] == 0.6667  # Pinned upstream rounds fitness to four decimals.
    assert suggested['approximate_fitness'] == 1.0
    assert suggested['structural_fitness'] == 0.0
    assert reviewed['strict_fitness'] == reviewed['approximate_fitness'] == 1.0
    assert reviewed['structural_fitness'] == 1.0
    assert reviewed['raw']['candidate']['vocabulary'] == suggested['raw']['candidate']['vocabulary']
    assert reviewed['vocabulary_coverage'] == pytest.approx(2 / 3)
    assert reviewed['raw']['candidate']['ontology_sha256'] == suggested['raw']['candidate']['ontology_sha256']
    assert reviewed['mappings'] == [approved_mapping()]
    concept = reviewed['raw']['candidate']['conceptual']['detail']['concepts'][NS + 'Asset']
    assert (concept['tier'], concept['via'], concept['element']) == ('exact', 'mapping', NS + 'Resource')
    assert reviewed['raw']['candidate']['conceptual']['detail']['tiers']['exact_via_prefix_mapping'] == 0
    assert suggested['raw']['candidate']['conceptual']['detail']['concepts'][NS + 'Asset']['tier'] == 'aligned'
    assert suggested['raw']['candidate']['conceptual']['detail']['ambiguity'] > 0


def test_mapping_is_identical_for_base_and_candidate_even_when_base_target_absent():
    candidate = ONTOLOGY.replace('ex:Asset', 'ex:Resource')
    base = candidate.replace('ex:Resource a owl:Class ; rdfs:label "Asset" .', '')
    report = assess(candidate, base_ttl=base, mappings=[approved_mapping()])
    assert report['status'] == 'completed', report
    assert report['strict_fitness'] == 1.0
    assert report['deltas']['strict_fitness'] == pytest.approx(0.3333)
    assert report['mapping_diagnostics']['base'][0]['target_present'] is False
    assert report['mapping_diagnostics']['candidate'][0]['target_present'] is True
    assert report['engine']['configuration']['mappings'] == {NS + 'Asset': NS + 'Resource'}
    assert report['raw']['candidate']['mappings_sha256'] == report['raw']['base']['mappings_sha256'] == report['mappings_sha256']


def test_mapping_review_metadata_changes_identity_while_preserving_raw_tool_values():
    import hashlib
    from oe_studio.artifacts import canonical_json
    candidate = ONTOLOGY.replace('ex:Asset', 'ex:Resource')
    mapping = approved_mapping(rationale='The reviewed resource denotes the required asset; één begrip.')
    first = assess(candidate, mappings=[mapping])
    second = assess(candidate, mappings=[approved_mapping(review_id='mapping-review-2')])
    assert first['status'] == second['status'] == 'completed', second
    assert first['mappings_sha256'] != second['mappings_sha256']
    assert first['mappings_sha256'] == hashlib.sha256(canonical_json([mapping])).hexdigest()
    assert first['raw']['candidate']['conceptual'] == second['raw']['candidate']['conceptual']
    assert second['mappings'][0]['review_id'] == 'mapping-review-2'


@pytest.mark.parametrize('mappings', [
    [{key: value for key, value in approved_mapping().items() if key != 'reviewer'}],
    [approved_mapping(relation_type='broader')],
    [approved_mapping(requirement_iri='ex:Asset')],
    [approved_mapping(evidence_ids=[])],
    [approved_mapping(), approved_mapping(ontology_iri=NS + 'Owner')],
    [approved_mapping(requirement_iri=NS + 'UnusedRequirement')],
    [approved_mapping(ontology_iri=NS + 'ownedBy')],
])
def test_unreviewed_ambiguous_unused_or_wrong_kind_mappings_are_not_scores(mappings):
    report = assess(mappings=mappings)
    assert report['status'] == 'unsupported', report
    assert report['strict_fitness'] is None
    assert report['raw'] == {}


def test_worker_mapping_identity_is_verified(monkeypatch):
    import json
    import subprocess
    import oe_studio.assessment as assessment
    report = assess()
    assert report['status'] == 'completed', report
    report['mappings_sha256'] = '0' * 64
    monkeypatch.setattr(assessment.subprocess, 'run', lambda *a, **kw:
        subprocess.CompletedProcess(a[0], 0, stdout=json.dumps(report), stderr=''))
    failed = assess()
    assert failed['status'] == 'error', failed
    assert failed['strict_fitness'] is None


def test_missing_pinned_language_resource_never_uses_user_home(monkeypatch, tmp_path):
    import oe_studio.assessment as assessment
    monkeypatch.setattr(assessment, 'RESOURCE_ROOT', tmp_path)
    report = assess()
    assert report['status'] == 'error', report
    assert report['raw'] == {}


def test_reviewed_property_correspondence_restores_schema_path():
    candidate = ONTOLOGY.replace('ex:ownedBy', 'ex:hasSteward')
    mapping = approved_mapping(requirement_iri=NS + 'ownedBy', ontology_iri=NS + 'hasSteward')
    report = assess(candidate, mappings=[mapping])
    assert report['status'] == 'completed', report
    assert report['strict_fitness'] == report['structural_fitness'] == 1.0
    assert report['vocabulary_coverage'] == pytest.approx(2 / 3)
    assert report['mapping_diagnostics']['candidate'][0]['requirement_kind'] == 'property'


def test_sandbox_launch_failure_never_falls_back_to_plain_python(monkeypatch):
    import subprocess
    import oe_studio.assessment as assessment
    commands = []

    def denied(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 71, stdout='', stderr='sandbox_apply: Operation not permitted')

    monkeypatch.setattr(assessment.subprocess, 'run', denied)
    report = assess()
    assert report['status'] == 'error', report
    assert report['raw'] == {}
    assert len(commands) == 1
    assert commands[0][0] == '/usr/bin/sandbox-exec'
