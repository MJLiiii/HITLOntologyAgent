"""Profile-to-flow authorization and historical recovery stay server-owned."""
import json

import pytest

from oe_studio.errors import Problem
from oe_studio import trustgraph_workflow as tg
from tests.integration.test_trustgraph_workflow import client, provider, run  # noqa: F401


def mapped_config(path, profile_id='fast', revision='a' * 64):
    data = json.loads(path.read_text())
    original = data['projects'][0]
    selected = {**original, 'binding': {**original['binding'], 'flow': 'fast-run-1'},
                'extraction_profile_id': profile_id, 'extraction_profile_revision': revision,
                'llm_session_id': 'frozen-run-1'}
    markers = {'oe-llm-profile-id': profile_id, 'oe-llm-profile-revision': revision,
               'oe-llm-session-id': selected['llm_session_id']}
    selected['expected_configuration'] = {
        'flow': {'fast-run-1': {'blueprint-name': 'profile-blueprint', 'parameters': markers}},
        'flow-blueprint': {'profile-blueprint': {'flow': {'studio-text-completion:{id}': {}}}},
        'processor:studio-text-completion': {'fast-run-1': {'parameters': markers}}}
    data['projects'].append(selected)
    path.write_text(json.dumps(data))
    return selected


def test_profile_selects_exact_preconfigured_flow_and_freezes_without_token(provider):  # noqa: F811
    studio, project, document, path = provider
    mapped_config(path)
    profile = {'id': 'fast', 'revision': 'a' * 64}
    frozen = tg.freeze_profile_binding(studio.settings, project['id'], profile)
    assert frozen['binding']['flow'] == 'fast-run-1'
    assert frozen['llm_session_id'] == 'frozen-run-1'
    assert 'token' not in frozen['binding']
    gateway, config, _ = tg.provider(studio, project['id'], document['id'], profile=profile, frozen_configuration=frozen)
    assert config.binding.flow == 'fast-run-1'
    assert gateway.bindings[config.binding.project_id].token.get_secret_value() == 'PRIVATE-TEST-TOKEN'
    with pytest.raises(Problem, match='profile'):
        tg.freeze_profile_binding(studio.settings, project['id'], {'id': 'fast', 'revision': 'b' * 64})


def test_frozen_flow_survives_default_changes_but_not_authorized_binding_drift(provider):  # noqa: F811
    studio, project, document, path = provider
    profile = {'id': 'fast', 'revision': 'a' * 64}
    mapped_config(path)
    frozen = tg.freeze_profile_binding(studio.settings, project['id'], profile)
    data = json.loads(path.read_text())
    data['projects'][0]['binding']['flow'] = 'new-default'
    data['projects'].reverse()
    path.write_text(json.dumps(data))
    _, config, _ = tg.provider(studio, project['id'], document['id'], profile=profile, frozen_configuration=frozen)
    assert config.binding.flow == 'fast-run-1'
    data['projects'][0]['binding']['config_digest'] = '2' * 64
    path.write_text(json.dumps(data))
    with pytest.raises(Problem, match='binding'):
        tg.provider(studio, project['id'], document['id'], profile=profile, frozen_configuration=frozen)


def test_recovery_list_and_import_use_recorded_profile_binding(provider, client, monkeypatch):  # noqa: F811
    from oe_studio.integrations.trustgraph.gateway import PinnedTrustGraphGateway
    studio, project, document, path = provider
    profile = {'id': 'fast', 'revision': 'a' * 64}
    mapped_config(path)
    frozen = tg.freeze_profile_binding(studio.settings, project['id'], profile)
    studio.settings.eager_jobs = False
    handle = studio.create_job(project['id'], 'trustgraph-ingestion', {
        'document_id': document['id'], '_resolved_llm_profile': profile,
        '_trustgraph_configuration': frozen, '_llm_session_id': 'frozen-run-1'}, 'frozen-profile', {'id': 'test', 'role': 'owner'})
    # create_job may resolve defaults; explicit internal worker payload is exercised directly.
    from oe_studio.db import Job
    with studio.db.session(write=True) as session:
        job = session.get(Job, handle['job_id'])
        job.payload = {**job.payload, '_resolved_llm_profile': profile, '_trustgraph_configuration': frozen,
                       '_llm_session_id': 'frozen-run-1'}
    studio.execute_job(handle['job_id'])
    with studio.db.session() as session:
        record = studio.items(session, project['id'], 'trustgraph_preparation')[0]
        assert record.data['llm_profile'] == profile
        assert record.data['server_configuration'] == frozen
        ingestion = studio.items(session, project['id'], 'trustgraph_ingestion')[0]
        ingestion_id, preparation_id = ingestion.id, record.id
    data = json.loads(path.read_text())
    data['projects'][0]['binding']['flow'] = 'new-default'
    path.write_text(json.dumps(data))
    async def chunks(gateway, prepared, receipt):
        assert gateway.bindings[prepared.request.project_id].flow == 'fast-run-1'
        return {'items': []}
    monkeypatch.setattr(PinnedTrustGraphGateway, 'list_registered_chunks', chunks)
    assert tg.list_chunks(studio, project['id'], ingestion_id) == {'items': []}
    studio.settings.eager_jobs = True
    recovery = run(client, project['id'], 'trustgraph-ingestion-recoveries', {'preparation_id': preparation_id}, 'profile-recovery')
    assert recovery['status'] == 'succeeded', recovery
    snapshot = run(client, project['id'], 'trustgraph-snapshots', {
        'ingestion_run_id': ingestion_id, 'chunk_uris': ['urn:test:chunk']}, 'profile-snapshot')
    assert snapshot['status'] == 'succeeded', snapshot


def test_profile_revision_must_match_remotely_checked_flow_markers(provider):  # noqa: F811
    studio, project, _, path = provider
    mapped_config(path)
    data = json.loads(path.read_text())
    data['projects'][1]['expected_configuration'] = {}
    path.write_text(json.dumps(data))
    with pytest.raises(Problem, match='marker'):
        tg.freeze_profile_binding(studio.settings, project['id'], {'id': 'fast', 'revision': 'a' * 64})


def test_profiled_flow_cannot_target_legacy_shared_completion_processor(provider):  # noqa: F811
    studio, project, _, path = provider
    mapped_config(path)
    data = json.loads(path.read_text())
    expected = data['projects'][1]['expected_configuration']
    expected['flow-blueprint']['profile-blueprint']['flow'] = {'text-completion:{id}': {}}
    parameters = expected['flow']['fast-run-1']['parameters']
    expected['processor:text-completion'] = {'fast-run-1': {'parameters': parameters}}
    path.write_text(json.dumps(data))
    with pytest.raises(Problem, match='marker'):
        tg.freeze_profile_binding(studio.settings, project['id'], {'id': 'fast', 'revision': 'a' * 64})
