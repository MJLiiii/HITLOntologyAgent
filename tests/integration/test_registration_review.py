"""Independent registration/staging provenance regressions; synthetic fixtures only."""
from uuid import uuid4

from tests.integration.test_workflow import client as workflow_client, job, project
from tests.integration.test_task_registration import registration

client = workflow_client


def model_double(monkeypatch, studio):
    studio.settings.model_url, studio.settings.model_name = 'http://localhost:11434', 'registration-review-double'
    monkeypatch.setattr('oe_studio.model.ModelClient.generate', lambda self, system, context, schema: (
        schema.model_validate({'summary': 'Preserve the supplied synthetic candidate', 'changes': []}),
        {'provider': 'controlled-test-double', 'elapsed_seconds': 0.01}))
    monkeypatch.setattr('oe_studio.experiments.validate', lambda ttl, **kw: {
        'id': str(uuid4()), 'status': 'passed', 'bundle_digest': kw['bundle_digest'], 'cases': []})
    monkeypatch.setattr('oe_studio.experiments.assess', lambda ttl, **kw: {
        'id': str(uuid4()), 'status': 'completed', 'bundle_digest': kw['bundle_digest']})


def test_registered_d_staging_keeps_mapping_only_evidence_separate_from_proposal_corpus(client, monkeypatch):
    p = project(client)
    root, studio = f"/api/v1/projects/{p['id']}", client.app.state.studio
    original_corpus = p['corpus_snapshot_id']
    doc = client.post(root + '/documents', files={'file': ('mapping-only.txt', b'Service has the same meaning in the reviewed vocabularies.', 'text/plain')},
                      data={'title': 'Synthetic mapping-only source', 'classification': 'synthetic'}).json()
    handle = client.post(root + '/ingestions', json={'document_id': doc['id']}, headers={'Idempotency-Key': str(uuid4())}).json()
    ingestion = client.get(handle['status_url']).json()['result']
    mapping_corpus = client.post(root + '/corpus-snapshots', json={'ingestion_run_ids': [ingestion['ingestion_run_id']]}).json()
    with studio.db.session() as session:
        mapping_evidence_id = studio.corpus_evidence(session, p['id'], mapping_corpus['id'])[0]['id']
        original_ids = {row['id'] for row in studio.corpus_evidence(session, p['id'], original_corpus)}
    mapping = client.post(root + '/mapping-sets', json={'mappings': [{
        'requirement_iri': 'https://example.org/oe-demo/Service', 'ontology_iri': 'https://example.org/oe-demo/Service',
        'relation_type': 'canonical_correspondence', 'rationale': 'Synthetic correspondence with separate source scope',
        'evidence_ids': [mapping_evidence_id]}]}).json()
    accepted = client.post(root + '/mapping-decisions', json={'mapping_set_id': mapping['id'], 'digest': mapping['digest'],
        'decision': 'accept', 'rationale': 'Simulated mapping review for this engineering regression'})
    assert accepted.status_code == 201, accepted.text
    proposal = job(client, p['id'], 'proposal', {'base_version_id': None, 'corpus_snapshot_id': original_corpus,
        'instruction': 'Create a synthetic candidate using the original proposal corpus'})
    revision = client.get(root + f"/proposals/{proposal['proposal_id']}/revisions/1").json()
    assert set(revision['evidence_ids']) == original_ids and mapping_evidence_id not in original_ids
    assert client.post(root + '/scope-decisions', json={'scope_digest': p['scope_digest'], 'decision': 'accept',
        'rationale': 'Synthetic registration review fixture only'}).status_code == 201
    registered = client.post(root + '/synthetic-tasks', json={'proposal_id': revision['id'], 'revision': 1,
        'bundle_digest': revision['bundle_digest'], 'task_id': 'mapping-scope-regression',
        'instruction': 'Keep proposal evidence and reviewed correspondence evidence in their frozen scopes'})
    assert registered.status_code == 201, registered.text
    record = registered.json()
    model_double(monkeypatch, studio)
    response = client.post(root + '/synthetic-task-jobs', json={'registration_id': record['id'],
        'registration_digest': record['registration_digest'], 'condition': 'D', 'replicate_ids': [1]},
        headers={'Idempotency-Key': str(uuid4())})
    outcome = client.get(response.json()['status_url']).json()
    assert outcome['status'] == 'succeeded', outcome
    run = outcome['result']['runs'][0]
    staged = client.post(root + f"/experiments/{run['id']}/proposal")
    assert staged.status_code == 201, staged.text
    value = staged.json()
    assert value['corpus_snapshot_id'] == original_corpus
    assert {row['id'] for row in value['manifest']['mapping_evidence']} == {mapping_evidence_id}
    assert set(value['evidence_ids']) == original_ids, 'Mapping-only citations must not become proposal-corpus evidence during D staging'
    assert value['manifest']['mapping_source_snapshot_id'] == mapping_corpus['id']


def test_registration_job_cannot_select_heldout_or_another_projects_task(client, monkeypatch):
    p, _, _, record = registration(client)
    root = f"/api/v1/projects/{p['id']}"
    payload = {'registration_id': record['id'], 'registration_digest': record['registration_digest'], 'condition': 'A'}
    calls = []
    monkeypatch.setattr('oe_studio.research_workflow.execute_synthetic_task', lambda *a, **kw: calls.append(kw))
    heldout = client.post(root + '/synthetic-task-jobs', json={**payload, 'split': 'held_out'},
        headers={'Idempotency-Key': str(uuid4())})
    assert heldout.status_code == 422
    other = client.post('/api/v1/projects', json={'name': 'Other synthetic task project', 'domain': 'demo'}).json()
    queued = client.post(f"/api/v1/projects/{other['id']}/synthetic-task-jobs", json=payload,
        headers={'Idempotency-Key': str(uuid4())})
    assert queued.status_code == 202
    outcome = client.get(queued.json()['status_url']).json()
    assert outcome['status'] == 'failed' and not calls


def test_registered_source_withdrawal_stops_generation_before_model_call(client, monkeypatch):
    p, _, _, record = registration(client)
    root, studio = f"/api/v1/projects/{p['id']}", client.app.state.studio
    with studio.db.session() as session:
        source = studio.evidence(session, p['id'], record['project_context']['evidence_ids'][0])
    withdrawn = client.post(root + f"/documents/{source['document_id']}/withdrawal", json={
        'rationale': 'Synthetic source withdrawal before registered generation'})
    assert withdrawn.status_code == 201
    calls = []
    monkeypatch.setattr('oe_studio.research_workflow.execute_synthetic_task', lambda *a, **kw: calls.append(kw))
    queued = client.post(root + '/synthetic-task-jobs', json={'registration_id': record['id'],
        'registration_digest': record['registration_digest'], 'condition': 'D'}, headers={'Idempotency-Key': str(uuid4())})
    outcome = client.get(queued.json()['status_url']).json()
    assert outcome['status'] == 'failed' and 'withdrawn' in outcome['error'] and not calls
