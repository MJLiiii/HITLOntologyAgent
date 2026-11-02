"""Independent review regressions for provenance and frozen workflow context."""
from tests.llm_fixtures import configure_studio_model
from uuid import uuid4

from tests.integration.test_workflow import client as workflow_client, job, project

client = workflow_client


def test_withdrawn_mapping_only_citation_blocks_review_for_an_older_proposal_corpus(client):
    p = project(client)
    root = f"/api/v1/projects/{p['id']}"
    old_corpus = p['corpus_snapshot_id']
    document = client.post(root + '/documents', files={'file': ('mapping.txt', b'Service denotes a service in both vocabularies.', 'text/plain')},
                           data={'title': 'Mapping-only source', 'classification': 'synthetic'}).json()
    response = client.post(root + '/ingestions', json={'document_id': document['id']},
                            headers={'Idempotency-Key': str(uuid4())})
    ingestion = client.get('/api/v1/jobs/' + response.json()['job_id']).json()['result']
    corpus = client.post(root + '/corpus-snapshots', json={'ingestion_run_ids': [ingestion['ingestion_run_id']]}).json()
    studio = client.app.state.studio
    with studio.db.session() as session:
        mapping_evidence = studio.corpus_evidence(session, p['id'], corpus['id'])[0]['id']
    mapping = client.post(root + '/mapping-sets', json={'mappings': [{
        'requirement_iri': 'https://example.org/oe-demo/Service',
        'ontology_iri': 'https://example.org/oe-demo/Service',
        'relation_type': 'canonical_correspondence', 'rationale': 'Reviewed terminology correspondence',
        'evidence_ids': [mapping_evidence]}]}).json()
    decision = client.post(root + '/mapping-decisions', json={'mapping_set_id': mapping['id'], 'digest': mapping['digest'],
                           'decision': 'accept', 'rationale': 'Reviewed the separate mapping evidence'})
    assert decision.status_code == 201
    proposal = job(client, p['id'], 'proposal', {'base_version_id': None, 'corpus_snapshot_id': old_corpus,
                                               'instruction': 'Create synthetic ontology from the original corpus'})
    revision_url = root + f"/proposals/{proposal['proposal_id']}/revisions/1"
    revision = client.get(revision_url).json()
    assert mapping_evidence not in revision['evidence_ids']
    bundle = {'proposal_id': proposal['proposal_id'], 'revision': 1, 'bundle_digest': revision['bundle_digest']}
    validation, assessment = job(client, p['id'], 'validation', bundle), job(client, p['id'], 'assessment', bundle)
    assert client.post(root + '/scope-decisions', json={'scope_digest': p['scope_digest'], 'decision': 'accept',
                                                       'rationale': 'Synthetic regression fixture only'}).status_code == 201
    assert client.get(revision_url).json()['review_eligibility']['eligible']
    withdrawn = client.post(root + f"/documents/{document['id']}/withdrawal", json={'rationale': 'Withdraw only the mapping citation'})
    assert withdrawn.status_code == 201
    eligibility = client.get(revision_url).json()['review_eligibility']
    assert not eligibility['eligible'], 'A withdrawn mapping citation must block review even outside proposal evidence'
    response = client.post(root + '/review-submissions', headers={'If-Match': '1'}, json={
        'proposal_id': proposal['proposal_id'], 'revision': 1, 'validation_run_id': validation['id'],
        'required_assessment_run_ids': [assessment['id']]})
    assert response.status_code == 409


def test_model_proposal_rejects_scope_changed_during_generation(client, monkeypatch):
    from oe_studio.schemas import ScopeUpload
    p = project(client)
    studio = client.app.state.studio
    configure_studio_model(studio, monkeypatch)
    def generate(_self, system, context, schema):
        questions = [{**q, 'expected': q.get('expected', True), 'required': True,
                      'question': q['question'] + ' Under the changed scope.'} for q in p['competency_questions']]
        studio.upload_scope(p['id'], ScopeUpload(title='Changed scope during model generation',
            purpose='Require the newly frozen modelling expectations', competency_questions=questions),
            {'kind': 'human', 'subject': 'local-human', 'roles': ['approver']})
        return schema.model_validate({'summary': 'Declare the original source-backed service class', 'changes': [{
            'operation': 'add', 'triple': {'subject': 'https://example.org/oe-demo/Service',
            'predicate': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', 'object': 'http://www.w3.org/2002/07/owl#Class'},
            'evidence_ids': [context['evidence'][0]['id']], 'rationale': 'A service is described by the original evidence'}]}), {}
    monkeypatch.setattr('oe_studio.model.ModelClient.generate', generate)
    response = client.post(f"/api/v1/projects/{p['id']}/proposal-jobs", json={'instruction': 'Use the original scope',
        'base_version_id': None, 'corpus_snapshot_id': p['corpus_snapshot_id']}, headers={'Idempotency-Key': str(uuid4())})
    result = client.get('/api/v1/jobs/' + response.json()['job_id']).json()
    assert project(client)['scope_digest'] != p['scope_digest'], 'The test must actually commit the concurrent scope change'
    assert result['status'] == 'failed', 'An output generated against the old scope must not receive the new scope bundle'
    assert 'scope' in result['error'].lower() or 'context' in result['error'].lower()
    assert client.get(f"/api/v1/projects/{p['id']}/proposals").json()['items'] == []


def test_review_timer_cannot_double_count_one_human_across_revisions(client):
    p = project(client)
    root = f"/api/v1/projects/{p['id']}"
    result = job(client, p['id'], 'proposal', {'instruction': 'Create synthetic seed ontology'})
    first = client.get(root + f"/proposals/{result['proposal_id']}/revisions/1").json()
    second = client.post(root + f"/proposals/{result['proposal_id']}/revisions", headers={'If-Match': '1'}, json={
        'parent_revision': 1, 'structured_changes': {}, 'rationale': 'Create a second reviewable snapshot'}).json()
    endpoint = root + '/review-sessions'
    assert client.post(endpoint, json={'revision_id': first['revision_id'], 'event': 'start'}).status_code == 201
    overlap = client.post(endpoint, json={'revision_id': second['revision_id'], 'event': 'start'})
    assert overlap.status_code == 409, 'One reviewer cannot accrue two overlapping active intervals'


def test_experiment_review_time_stops_at_the_linked_human_decision(client, monkeypatch):
    from oe_studio import experiments as ex
    studio = client.app.state.studio
    configure_studio_model(studio, monkeypatch)
    monkeypatch.setattr('oe_studio.model.ModelClient.generate', lambda self, system, context, schema: (
        schema.model_validate({'summary': 'No justified source changes are needed', 'changes': []}), {'elapsed_seconds': .1}))
    monkeypatch.setattr(ex, 'validate', lambda ttl, **kw: {'status': 'passed', 'cases': [
        {'id': t['test_id'], 'status': 'passed', 'expected': t['expected'], 'actual': t['expected']} for t in kw['tests']]})
    monkeypatch.setattr(ex, 'assess', lambda ttl, **kw: {'status': 'completed'})
    p = project(client)
    root = f"/api/v1/projects/{p['id']}"
    run = job(client, p['id'], 'experiment', {'protocol_id': 'model-pilot-v1', 'condition': 'D'})['runs'][0]
    r = client.post(root + f"/experiments/{run['id']}/proposal").json()
    bundle = {'proposal_id': r['id'], 'revision': 1, 'bundle_digest': r['bundle_digest']}
    validation, assessment = job(client, p['id'], 'validation', bundle), job(client, p['id'], 'assessment', bundle)
    client.post(root + '/scope-decisions', json={'scope_digest': p['scope_digest'], 'decision': 'accept',
                                                'rationale': 'Synthetic timing regression only'})
    submission = {'proposal_id': r['id'], 'revision': 1, 'validation_run_id': validation['id'],
                  'required_assessment_run_ids': [assessment['id']]}
    assert client.post(root + '/review-submissions', headers={'If-Match': '1'}, json=submission).status_code == 201
    timer = root + '/review-sessions'
    for action, stamp in [('start', '2020-01-01T00:00:00+00:00'), ('end', '2020-01-01T00:00:10+00:00')]:
        monkeypatch.setattr('oe_studio.workflow.now', lambda stamp=stamp: stamp)
        assert client.post(timer, json={'revision_id': r['revision_id'], 'event': action}).status_code == 201
    review = client.post(root + '/reviews', json={**submission, 'bundle_digest': r['bundle_digest'], 'decision': 'accept',
        'rationale': 'Observed synthetic decision before any later inspection', 'review_policy_id': p['review_policy_id']}).json()
    # Independent later inspection is permitted, but does not belong to time-to-this-decision.
    for action, stamp in [('start', '2099-01-01T00:00:00+00:00'), ('end', '2099-01-01T00:00:20+00:00')]:
        monkeypatch.setattr('oe_studio.workflow.now', lambda stamp=stamp: stamp)
        assert client.post(timer, json={'revision_id': r['revision_id'], 'event': action}).status_code == 201
    linked = client.post(root + f"/experiments/{run['id']}/review-results", json={'review_id': review['id']})
    assert linked.status_code == 201, linked.text
    assert linked.json()['correction_seconds'] == 10, 'Later inspection must not inflate time to an earlier acceptance'
