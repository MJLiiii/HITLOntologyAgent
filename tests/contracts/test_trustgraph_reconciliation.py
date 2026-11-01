import copy
import hashlib

import pytest

from oe_studio.integrations.trustgraph.reconcile import reconcile_synthetic_snapshot, PROV, TG


def packet():
    text, document, child, flow = 'Atlas belongs to Platform.', 'urn:doc:atlas', 'urn:chunk:one', 'oe-ontology'
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    frozen = {'mode': 'synthetic_engineering_smoke', 'real_study_approved': False,
              'expected_chunk_count_per_flow': 1, 'source': text, 'source_sha256': content_hash,
              'byte_length': len(text.encode()), 'documents': {flow: document}}
    def triple(s, p, o):
        return {'s': {'t': 'i', 'i': s}, 'p': {'t': 'i', 'i': p},
                'o': {'t': 'i', 'i': o}, 'g': 'urn:graph:source'}
    graph = [triple(child, PROV + 'wasDerivedFrom', document),
             triple('urn:subgraph:one', PROV + 'wasDerivedFrom', child),
             triple('urn:subgraph:one', PROV + 'wasGeneratedBy', 'urn:activity:one'),
             triple('urn:activity:one', PROV + 'wasAssociatedWith', 'https://trustgraph.ai/agent/kg-extract-ontology')]
    statement = triple('urn:subgraph:one', TG + 'contains', '')
    statement['o'] = {'t': 't', 'tr': {'s': {'t': 'i', 'i': 'urn:Atlas'}, 'p': {'t': 'i', 'i': 'urn:ownedBy'},
                                     'o': {'t': 'i', 'i': 'urn:Platform'}}}
    graph.append(statement)
    obs = {flow: {'source_sha256': content_hash, 'source_graph': {'response': graph}, 'children': [{
        'metadata': {'document-metadata': {'id': child, 'parent-id': document, 'document-type': 'chunk'}},
        'content': text, 'sha256': content_hash}]}}
    retrieval = {flow: {'status': 'returned', 'raw': {'end_of_session': True, 'sources': [{'uri': document}]},
                        'retrieval_graph': {'response': [{'g': 'urn:graph:retrieval'}]}}}
    return frozen, obs, retrieval


def test_exact_bounded_snapshot_does_not_grant_global_completion_or_review():
    frozen, obs, retrieval = packet()
    report = reconcile_synthetic_snapshot(frozen, obs, retrieval)
    assert report['bounded_snapshot_verified'] and report['flows']['oe-ontology']['quoted_facts']
    assert not report['upstream_completion_supported'] and not report['review_eligible']
    assert not report['corpus_freeze_allowed']
    assert report == reconcile_synthetic_snapshot(frozen, copy.deepcopy(obs), copy.deepcopy(retrieval))


@pytest.mark.parametrize('failure', ['hash', 'parent', 'stage', 'scope', 'source', 'trace', 'unfinished'])
def test_missing_or_forged_stage_and_source_evidence_never_verify(failure):
    frozen, obs, retrieval = packet()
    row, result = obs['oe-ontology'], retrieval['oe-ontology']
    if failure == 'hash':
        row['children'][0]['sha256'] = '0' * 64
    elif failure == 'parent':
        row['children'][0]['metadata']['document-metadata']['parent-id'] = 'urn:other'
    elif failure == 'stage':
        row['source_graph']['response'].pop()
    elif failure == 'scope':
        row['source_graph']['response'][0]['g'] = 'urn:other-workspace'
    elif failure == 'source':
        result['raw']['sources'] = [{'uri': 'urn:unregistered'}]
    elif failure == 'trace':
        result['retrieval_graph']['response'] = []
    else:
        result['raw']['end_of_session'] = False
    assert not reconcile_synthetic_snapshot(frozen, obs, retrieval)['bounded_snapshot_verified']


def test_real_study_or_different_packet_cannot_use_synthetic_reconciliation():
    frozen, obs, retrieval = packet()
    frozen['real_study_approved'] = True
    with pytest.raises(ValueError, match='synthetic packet'):
        reconcile_synthetic_snapshot(frozen, obs, retrieval)
