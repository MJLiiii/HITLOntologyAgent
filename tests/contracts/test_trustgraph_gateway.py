import asyncio
import base64
import hashlib
import json
import os
from importlib import util
from uuid import UUID

import pytest
from pydantic import ValidationError

from oe_studio.artifacts import ArtifactStore
from oe_studio.integrations.trustgraph.contracts import (
    Artifact, Binding, CorpusRegistration, DocumentRegistration, EvidenceRef, IngestRequest, RetrievalRequest)
from oe_studio.integrations.trustgraph.fake_gateway import FakeTrustGraphGateway
from oe_studio.integrations.trustgraph.gateway import GatewayError, PinnedTrustGraphGateway, plain, verified_sdk

PROJECT, SOURCE, CORPUS, EVIDENCE = [UUID(int=i) for i in range(1, 5)]
CONTENT = b'Payroll belongs to Operations.\n'
HASH = hashlib.sha256(CONTENT).hexdigest()


@pytest.fixture
def gateway(tmp_path):
    store = ArtifactStore(tmp_path / 'artifacts')
    artifact = Artifact(**store.put(CONTENT, 'text/plain'))
    binding = Binding(project_id=PROJECT, url='http://127.0.0.1:8888', workspace='approved-workspace',
                      flow='reviewed-flow', collection='fixed-collection', token='test-private-token',
                      seed_digest='a' * 64, config_digest='b' * 64)
    document = DocumentRegistration(project_id=PROJECT, source_id=SOURCE,
                                    upstream_document_id='urn:synthetic:document', artifact=artifact,
                                    source_uri='https://example.org/demo/source', title='Synthetic source')
    evidence = EvidenceRef(id=EVIDENCE, project_id=PROJECT, corpus_id=CORPUS, source_id=SOURCE,
                           upstream_chunk_uri='urn:synthetic:chunk', source_sha256=HASH,
                           chunk_sha256=HASH, byte_start=0, byte_end=len(CONTENT), quote=CONTENT.decode(),
                           graph_uri='urn:synthetic:graph')
    corpus = CorpusRegistration(project_id=PROJECT, corpus_id=CORPUS, evidence=(evidence,),
                                graph_uri='urn:synthetic:graph', provenance_verified=True)
    return FakeTrustGraphGateway(artifacts=store, bindings=[binding], documents=[document], corpora=[corpus])


def ingest_request(gateway, **changes):
    values = {'project_id': PROJECT, 'source_id': SOURCE, 'artifact': gateway.documents[(PROJECT, SOURCE)].artifact,
              'seed_digest': 'a' * 64, 'config_digest': 'b' * 64, 'idempotency_key': 'upload-1'}
    return IngestRequest(**{**values, **changes})


def retrieval(**changes):
    return RetrievalRequest(**{'project_id': PROJECT, 'corpus_id': CORPUS, 'query': 'Who owns Payroll?',
                               'base_ontology_digest': 'a' * 64, 'retrieval_config_digest': 'b' * 64, **changes})


def test_upload_is_not_processing_complete(gateway):
    receipt = asyncio.run(gateway.ingest(ingest_request(gateway)))
    assert receipt.status == 'queued'
    pending = asyncio.run(gateway.ingestion_status(receipt))
    assert pending.status == 'processing' and not pending.corpus_freeze_allowed
    gateway.processings.clear()
    absent = asyncio.run(gateway.ingestion_status(receipt))
    assert absent.status == 'unknown' and not absent.completion_supported
    gateway.completed.add(receipt.ingestion_id)
    completed = asyncio.run(gateway.ingestion_status(receipt))
    assert completed.status == 'completed' and completed.mode == 'fake'


def test_workspace_binding_is_server_selected_and_wrong_scope_rejected(gateway):
    with pytest.raises(ValidationError):
        ingest_request(gateway, workspace='attacker')
    with pytest.raises(ValidationError):
        retrieval(collection='attacker')
    with pytest.raises(GatewayError, match='source_not_authorized'):
        asyncio.run(gateway.ingest(ingest_request(gateway, project_id=UUID(int=99))))
    gateway._client(PROJECT).workspace = 'attacker'
    with pytest.raises(GatewayError, match='workspace_binding_mismatch'):
        asyncio.run(gateway.retrieve(retrieval()))


def test_ingestion_configuration_and_processing_scope_are_bound(gateway):
    with pytest.raises(GatewayError, match='configuration_mismatch'):
        asyncio.run(gateway.ingest(ingest_request(gateway, config_digest='c' * 64)))
    with pytest.raises(GatewayError, match='retrieval_configuration_mismatch'):
        asyncio.run(gateway.retrieve(retrieval(retrieval_config_digest='c' * 64)))
    receipt = asyncio.run(gateway.ingest(ingest_request(gateway)))
    gateway.processings[0]['collection'] = 'other'
    with pytest.raises(GatewayError, match='processing_scope_mismatch'):
        asyncio.run(gateway.ingestion_status(receipt))


def test_retries_keep_stable_document_and_processing_identity(gateway):
    one = asyncio.run(gateway.ingest(ingest_request(gateway)))
    two = asyncio.run(gateway.ingest(ingest_request(gateway)))
    assert one == two
    assert len([c for c in gateway.calls if c[0] == 'add_document']) == 1


def test_exact_quote_hash_and_graph_evidence_preserved(gateway):
    gateway.triples = [{'s': {'kind': 'iri', 'value': 'urn:payroll'},
                        'p': {'kind': 'iri', 'value': 'urn:owner'},
                        'o': {'kind': 'literal', 'value': 'Operations', 'language': 'en', 'datatype': None},
                        'g': 'urn:synthetic:graph'}]
    bundle = asyncio.run(gateway.retrieve(retrieval()))
    assert bundle.review_eligible and bundle.mode == 'fake'
    record = bundle.evidence[0]
    assert record.resolved and record.quote == CONTENT.decode()
    assert gateway.artifacts.get_verified(record.chunk_artifact.model_dump()) == CONTENT
    graph = json.loads(gateway.artifacts.get_verified(bundle.graph_artifact.model_dump()))
    assert graph['triples'] == gateway.triples and graph['graph_uri'] == 'urn:synthetic:graph'
    manifest = gateway.artifacts.get_verified(bundle.manifest_artifact.model_dump())
    assert b'Explicit synthetic fake answer' not in manifest and b'test-private-token' not in manifest
    assert asyncio.run(gateway.retrieve(retrieval())).manifest_digest == bundle.manifest_digest


def test_fabricated_quote_changed_chunk_and_unknown_sources_block_review(gateway):
    ref = gateway.corpora[(PROJECT, CORPUS)].evidence[0]
    forged = ref.model_copy(update={'quote': 'Fabricated statement'})
    assert not asyncio.run(gateway.resolve_evidence(forged)).resolved
    gateway.content[ref.upstream_chunk_uri] = b'changed'
    bundle = asyncio.run(gateway.retrieve(retrieval()))
    assert not bundle.review_eligible and not bundle.evidence[0].resolved
    gateway.answer['sources'] = [{'uri': 'urn:unmapped:source', 'title': 'Unverified'}]
    bundle = asyncio.run(gateway.retrieve(retrieval()))
    assert bundle.unresolved_source_uris == ('urn:unmapped:source',)
    assert not bundle.review_eligible


def test_unverified_completion_and_result_caps_block_review(gateway):
    corpus = gateway.corpora[(PROJECT, CORPUS)]
    gateway.corpora[(PROJECT, CORPUS)] = corpus.model_copy(update={'provenance_verified': False})
    bundle = asyncio.run(gateway.retrieve(retrieval()))
    assert not bundle.review_eligible
    assert 'corpus_completion_and_provenance_not_verified' in bundle.reasons
    gateway.triples = [{'s': 'urn:a', 'p': 'urn:b', 'o': 'urn:c', 'g': ''}]
    assert asyncio.run(gateway.retrieve(retrieval(triple_limit=1))).truncated


def test_literal_metadata_is_not_lost_during_normalization():
    class Literal(str):
        datatype, language = 'urn:datatype', 'en'
        def is_literal(self):
            return True
    assert plain(Literal('001')) == {'kind': 'literal', 'value': '001', 'datatype': 'urn:datatype', 'language': 'en'}


def test_malformed_source_is_retained_as_unresolved(gateway):
    gateway.answer['sources'].append('invalid upstream source record')
    result = asyncio.run(gateway.retrieve(retrieval()))
    assert not result.review_eligible and result.unresolved_source_uris == ('None',)


def test_source_document_uri_resolves_only_its_frozen_exact_child(gateway):
    gateway.answer['sources'] = [{'uri': 'urn:synthetic:document', 'title': 'Source document'}]
    result = asyncio.run(gateway.retrieve(retrieval()))
    assert result.evidence and result.evidence[0].resolved
    assert result.evidence[0].ref.upstream_chunk_uri == 'urn:synthetic:chunk'
    gateway.document_metadata['urn:synthetic:chunk']['parent_id'] = 'urn:another:document'
    assert not asyncio.run(gateway.retrieve(retrieval())).review_eligible


@pytest.mark.skipif(util.find_spec('trustgraph') is None, reason='Optional source-pinned SDK not installed')
def test_real_sdk_wire_uses_only_bound_workspace_and_distinct_upload_submission(gateway, monkeypatch):
    import requests
    from types import SimpleNamespace
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        operation = kwargs['json'].get('operation')
        result = {'processing-metadatas': []} if operation == 'list-processing' else {}
        return SimpleNamespace(status_code=200, json=lambda: result)

    monkeypatch.setattr(requests, 'post', post)
    real = PinnedTrustGraphGateway(artifacts=gateway.artifacts, bindings=gateway.bindings.values(),
                                  documents=gateway.documents.values())
    receipt = asyncio.run(real.ingest(ingest_request(gateway)))
    status = asyncio.run(real.ingestion_status(receipt))
    assert status.status == 'unknown' and status.mode == 'real' and not status.corpus_freeze_allowed
    assert [call[1]['json']['operation'] for call in calls] == ['add-document', 'add-processing', 'list-processing']
    assert all(call[1]['json']['workspace'] == 'approved-workspace' for call in calls)
    assert all(call[0] == 'http://127.0.0.1:8888/api/v1/librarian' for call in calls)
    assert all(call[1]['headers']['Authorization'] == 'Bearer test-private-token' for call in calls)


@pytest.mark.skipif(util.find_spec('trustgraph') is None, reason='Optional source-pinned SDK not installed')
def test_real_sdk_graph_rag_and_evidence_wire_preserve_literal_and_exact_quote(gateway, monkeypatch):
    import requests
    from types import SimpleNamespace
    calls = []

    def post(url, **kwargs):
        payload = kwargs['json']
        calls.append((url, payload))
        if url.endswith('/service/graph-rag'):
            response = {'response': 'Untrusted generated prose', 'sources': [
                {'uri': 'urn:synthetic:chunk', 'title': 'Source'}]}
        elif url.endswith('/service/triples'):
            response = {'response': [{'s': {'t': 'i', 'i': 'urn:payroll'}, 'p': {'t': 'i', 'i': 'urn:name'},
                                      'o': {'t': 'l', 'v': 'Payroll', 'language': 'en'}}]}
        elif payload['operation'] == 'get-document-content':
            response = {'content': base64.b64encode(CONTENT).decode()}
        else:
            # The real 2.11.1 gateway rejects SDK get-document/list-children;
            # it accepts get-document-metadata and may omit child time.
            assert payload['operation'] == 'get-document-metadata'
            response = {'document-metadata': {'id': 'urn:synthetic:chunk', 'kind': 'text/plain',
                                              'title': 'Chunk', 'metadata': [], 'tags': [],
                                              'parent-id': 'urn:synthetic:document'}}
        return SimpleNamespace(status_code=200, json=lambda: response)

    monkeypatch.setattr(requests, 'post', post)
    real = PinnedTrustGraphGateway(artifacts=gateway.artifacts, bindings=gateway.bindings.values(),
                                  documents=gateway.documents.values(), corpora=gateway.corpora.values())
    result = asyncio.run(real.retrieve(retrieval()))
    assert result.review_eligible and result.evidence[0].quote == CONTENT.decode()
    graph = json.loads(real.artifacts.get_verified(result.graph_artifact.model_dump()))
    assert graph['graph_uri'] == 'urn:synthetic:graph'
    assert graph['triples'][0]['o'] == {'t': 'l', 'v': 'Payroll', 'language': 'en'}
    assert all(payload['workspace'] == 'approved-workspace' for _, payload in calls)
    assert calls[1][1]['g'] == 'urn:synthetic:graph'


@pytest.mark.live
@pytest.mark.skipif(os.getenv('OE_TG_LIVE_READONLY') != '1', reason='Explicit configured TrustGraph read-only probe required')
def test_live_source_pinned_runtime_and_processing_read():
    """Only an authenticated read; does not upload data or claim ingestion completion."""
    binding = Binding(project_id=PROJECT, url=os.environ['OE_TG_URL'], workspace=os.environ['OE_TG_WORKSPACE'],
                      flow=os.environ['OE_TG_FLOW'], collection=os.environ['OE_TG_COLLECTION'],
                      token=os.environ.get('OE_TG_TOKEN', ''), seed_digest='a' * 64, config_digest='b' * 64)
    client = verified_sdk(binding)
    assert isinstance(client.library().get_processings(), list)
    assert PinnedTrustGraphGateway.mode == 'real'
