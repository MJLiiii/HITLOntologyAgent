"""Wire serialization must preserve immutable evidence, not just UI summaries."""
from tests.integration.test_real_engine_workflow import real_client as engine_client, candidate, job
from tests.integration.test_workflow import client as workflow_client
from oe_studio.artifacts import canonical_json

real_client = engine_client
client = workflow_client


def test_real_engine_http_reports_preserve_entire_persisted_payload(real_client):
    p, root, proposal = candidate(real_client)
    studio = real_client.app.state.studio
    for kind, success in [('validation', 'passed'), ('assessment', 'completed')]:
        result = job(real_client, root, kind, proposal)
        assert result['status'] == success, result
        with studio.db.session() as session:
            stored = studio.body(studio.get(session, p['id'], result['id'], kind))
        fetched = real_client.get(root + f'/{kind}-runs/' + result['id'])
        assert fetched.status_code == 200, fetched.text
        assert canonical_json(result) == canonical_json(stored) == canonical_json(fetched.json())
        if kind == 'validation':
            assert result['raw_artifacts'] and result['input_manifest'] and result['engine']['isolation']
        else:
            assert result['raw']['candidate'] and result['denominators']
            assert 'deltas' in result and 'missing_reasons' in result
    with studio.db.session() as session:
        record = studio.revision(session, p['id'], proposal['proposal_id'], 1)
        expected = studio.revision_body(session, studio.project(session, p['id']), record)
    revision = real_client.get(root + f"/proposals/{proposal['proposal_id']}/revisions/1").json()
    assert canonical_json(revision) == canonical_json(expected)


def test_actual_document_evidence_and_version_responses_do_not_inject_defaults(client):
    studio = client.app.state.studio
    p = client.get('/api/v1/projects').json()['items'][0]
    root = f"/api/v1/projects/{p['id']}"
    with studio.db.session() as session:
        expected_project = studio.project_body(studio.project(session, p['id']))
        documents = [studio.document_body(session, item) for item in studio.items(session, p['id'], 'document')]
        versions = [studio.version_body(session, item) for item in studio.items(session, p['id'], 'version')]
        evidence = studio.corpus_evidence(session, p['id'], p['corpus_snapshot_id'])
    assert canonical_json(p) == canonical_json(expected_project)
    for suffix, records in [('documents', documents), ('versions', versions), ('corpus-evidence', evidence)]:
        actual = client.get(root + '/' + suffix).json()['items']
        assert canonical_json(actual) == canonical_json(records)
    artifact = client.get(root + '/artifacts/' + documents[0]['artifact']['id'])
    assert artifact.content == studio.artifacts.get_verified(documents[0]['artifact'])


def test_historical_artifact_and_manifest_fields_remain_absent_on_api_reads(client):
    """Build an old-format synthetic store; never migrate an immutable manifest."""
    from copy import deepcopy
    from sqlalchemy import select
    from oe_studio.db import Item
    from oe_studio.artifacts import digest
    from tests.integration.test_workflow import candidate as new_candidate
    p, revision = new_candidate(client)
    studio = client.app.state.studio
    historical_manifest_fields = {'mappings', 'scope_digest', 'assessment_mappings_digest',
                                  'mapping_decision_id', 'mapping_source_snapshot_id', 'mapping_evidence'}

    def old_artifact_references(value):
        if isinstance(value, dict):
            return {key: old_artifact_references(child) for key, child in value.items()
                    if not (key == 'id' and {'sha256', 'byte_length', 'media_type'} <= value.keys())}
        if isinstance(value, list):
            return [old_artifact_references(child) for child in value]
        return value

    # This is fixture construction in pytest's temporary DB and artifact store.
    # Production .data is never opened or altered by this regression.
    with studio.db.session(write=True) as session:
        for item in session.scalars(select(Item)):
            data = old_artifact_references({key: value for key, value in item.data.items() if key != '_payload'})
            if item.kind == 'revision':
                data.pop('mappings')
                for field in historical_manifest_fields:
                    data['manifest'].pop(field)
                data['bundle_digest'] = digest(data['manifest'])
            ref = studio.artifacts.put(canonical_json(data), 'application/json')
            item.data = {**data, '_payload': old_artifact_references(ref)}
        session.flush()
        expected = {item.id: deepcopy(item.data) for item in session.scalars(select(Item))}
        stored = studio.revision(session, p['id'], revision['id'], 1)
        old_manifest = deepcopy(stored.data['manifest'])
        old_bundle_digest = stored.data['bundle_digest']

    root = f"/api/v1/projects/{p['id']}"
    for suffix, artifact_field in [('documents', 'artifact'), ('versions', 'ontology'), ('corpus-evidence', 'chunk')]:
        response = client.get(root + '/' + suffix)
        assert response.status_code == 200, response.text
        for item in response.json()['items']:
            assert 'id' not in item[artifact_field]
            assert canonical_json(item[artifact_field]) == canonical_json(expected[item['id']][artifact_field])
    for url in (root + '/proposals', root + f"/proposals/{revision['id']}/revisions/1"):
        response = client.get(url)
        assert response.status_code == 200, response.text
        item = response.json()['items'][0] if 'items' in response.json() else response.json()
        assert 'mappings' not in item
        assert not historical_manifest_fields.intersection(item['manifest'])
        assert canonical_json(item['manifest']) == canonical_json(old_manifest)
        assert item['bundle_digest'] == old_bundle_digest
        assert not item['review_eligibility']['eligible']
        assert any('scope changed' in reason.lower() for reason in item['review_eligibility']['reasons'])
    with studio.db.session() as session:
        assert {item.id: item.data for item in session.scalars(select(Item))} == expected
