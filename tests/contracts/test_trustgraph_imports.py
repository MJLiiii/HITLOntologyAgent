import asyncio
import copy
import hashlib
from uuid import UUID

import pytest

from oe_studio.artifacts import ArtifactStore
from oe_studio.demo import ONTOLOGY
from oe_studio.integrations.trustgraph.contracts import Artifact, Binding, DocumentRegistration, IngestRequest, PreparedIngestion
from oe_studio.integrations.trustgraph.fake_gateway import FakeTrustGraphGateway
from oe_studio.integrations.trustgraph.gateway import GatewayError
from oe_studio.integrations.trustgraph.imports import NO_SEED_DIGEST, configuration_digest, PROV, TG
from oe_studio.integrations.trustgraph.seed import project_seed_ontology


@pytest.fixture
def context(tmp_path):
    project, source = UUID(int=90), UUID(int=91)
    artifacts = ArtifactStore(tmp_path / 'artifacts')
    content = 'Équipe\r\nAtlas appartient à Platform.\r\n'.encode()
    artifact = Artifact(**artifacts.put(content, 'text/plain'))
    approved = Artifact(**artifacts.put(ONTOLOGY.encode(), 'text/turtle'))
    cfg = {'ontology': {'approved': project_seed_ontology(ONTOLOGY.encode())},
           'flow': {'frozen-flow': {'blueprint-name': 'seeded', 'parameters': {}}},
           'flow-blueprint': {'seeded': {'flow': {'kg-extract-ontology:{id}': {'topics': {}}}, 'blueprint': {}}},
           'processor:kg-extract-ontology': {'frozen-flow': {'topics': {}, 'parameters': {}}},
           'prompt': {'template.extract-with-ontologies': {'prompt': 'Use source and seed', 'response-type': 'json'}}}
    binding = Binding(project_id=project, url='http://127.0.0.1:18888', workspace='registered-workspace', flow='frozen-flow',
                      collection='registered-collection', seed_digest=approved.sha256, config_digest=configuration_digest(cfg), token='private-test-token')
    registration = DocumentRegistration(project_id=project, source_id=source, upstream_document_id='urn:registered:doc',
                                        artifact=artifact, source_uri='https://example.org/source', title='Synthetic')
    gateway = FakeTrustGraphGateway(artifacts=artifacts, bindings=[binding], documents=[registration])
    gateway.configuration = copy.deepcopy(cfg)
    gateway.content.clear()
    request = IngestRequest(project_id=project, source_id=source, artifact=artifact, seed_digest=approved.sha256,
                            config_digest=binding.config_digest, idempotency_key='durable-1')
    return gateway, request, approved, cfg, content


def prepare(context):
    gateway, request, approved, cfg, _ = context
    return asyncio.run(gateway.prepare_ingestion(request, approved_version_id=UUID(int=92), approved_ontology=approved,
                                                 expected_configuration=cfg))


def populated(context):
    gateway, _, _, _, content = context
    prepared = prepare(context)
    receipt = asyncio.run(gateway.ingest_prepared(prepared))
    uri, sg, activity = 'urn:chunk:one', 'https://example.org/subgraph', 'https://example.org/activity'
    gateway.content[uri] = content[len('Équipe\r\n'.encode()):]
    gateway.document_metadata[uri] = {'id': uri, 'parent_id': prepared.source.upstream_document_id}
    def triple(s, p, o):
        return {'s': {'t': 'i', 'i': s}, 'p': {'t': 'i', 'i': p}, 'o': {'t': 'i', 'i': o}, 'g': 'urn:graph:source'}
    gateway.triples = [triple(uri, PROV + 'wasDerivedFrom', prepared.source.upstream_document_id),
                       triple(sg, PROV + 'wasDerivedFrom', uri), triple(sg, PROV + 'wasGeneratedBy', activity),
                       triple(activity, PROV + 'wasAssociatedWith', 'https://trustgraph.ai/agent/kg-extract-ontology')]
    fact = triple('https://example.org/Atlas', 'https://example.org/ownedBy', 'https://example.org/Platform')
    quoted = triple(sg, TG + 'contains', '')
    quoted['o'] = {'t': 't', 'tr': {key: value for key, value in fact.items() if key != 'g'}}
    gateway.triples.append(quoted)
    return gateway, prepared, receipt, uri


def test_preparation_binds_approved_seed_configuration_before_any_effect(context):
    prepared = prepare(context)
    gateway = context[0]
    assert not gateway.calls and prepared.configuration_version == 1
    restored = PreparedIngestion.model_validate_json(prepared.model_dump_json())
    receipt = asyncio.run(gateway.ingest_prepared(restored))
    assert receipt.status == 'queued' and receipt.seed_digest == context[2].sha256
    assert [call[0] for call in gateway.calls] == ['add_document', 'start_processing']
    manifest = gateway.artifacts.get_verified(prepared.manifest_artifact.model_dump())
    assert b'private-test-token' not in manifest


def test_retry_after_lost_response_recovers_existing_submission_without_second_effect(context):
    gateway = context[0]
    prepared = prepare(context)
    original = asyncio.run(gateway.ingest_prepared(prepared))
    gateway._clients.clear()  # Simulate process reconstruction with persisted preparation.
    recovered = asyncio.run(gateway.ingest_prepared(PreparedIngestion.model_validate_json(prepared.model_dump_json()), may_have_submitted=True))
    assert recovered.processing_id == original.processing_id and recovered.ingestion_id == original.ingestion_id
    assert len(gateway.calls) == 2
    gateway.processings.clear()
    with pytest.raises(GatewayError, match='ambiguous_submission'):
        asyncio.run(gateway.ingest_prepared(prepared, may_have_submitted=True))
    assert len(gateway.calls) == 2


def test_changed_and_reverted_remote_configuration_version_invalidates_preparation(context):
    prepared = prepare(context)
    context[0].configuration_version += 2
    with pytest.raises(GatewayError, match='configuration_version_changed'):
        asyncio.run(context[0].ingest_prepared(prepared))
    assert not context[0].calls


def test_unapproved_seed_and_unexpected_workspace_ontology_are_rejected(context):
    gateway, request, approved, cfg, _ = context
    with pytest.raises(GatewayError, match='approved_seed_binding'):
        asyncio.run(gateway.prepare_ingestion(request, approved_ontology=approved, expected_configuration=cfg))
    gateway.configuration['ontology']['unregistered'] = {'classes': {}}
    with pytest.raises(GatewayError, match='remote_configuration_mismatch'):
        prepare(context)


def test_configuration_artifact_tampering_and_secret_types_fail_before_effect(context):
    prepared = prepare(context)
    tampered = prepared.model_copy(update={'configuration_version': 999})
    with pytest.raises(GatewayError, match='preparation_integrity'):
        asyncio.run(context[0].ingest_prepared(tampered))
    gateway, request, approved, cfg, _ = context
    cfg['iam'] = {'secret': {'password': 'not permitted'}}
    gateway.bindings[request.project_id] = gateway.bindings[request.project_id].model_copy(update={'config_digest': configuration_digest(cfg)})
    request = request.model_copy(update={'config_digest': configuration_digest(cfg)})
    with pytest.raises(GatewayError, match='configuration_type_not_admitted'):
        asyncio.run(gateway.prepare_ingestion(request, approved_version_id=UUID(int=92), approved_ontology=approved, expected_configuration=cfg))


def test_explicit_import_copies_normalized_unicode_spans_and_remains_immutable(context):
    gateway, prepared, receipt, uri = populated(context)
    hints = asyncio.run(gateway.list_registered_chunks(prepared, receipt))
    assert hints['chunk_uris'] == [uri] and not hints['upstream_completion_supported']
    imported = asyncio.run(gateway.import_snapshot(prepared, receipt, chunk_uris=(uri,), corpus_id=UUID(int=93)))
    chunk = imported.chunks[0]
    assert imported.status == 'verified_selection' and not imported.upstream_completion_supported
    assert chunk.byte_start == 9 and chunk.span_start == 7
    assert chunk.quote == 'Atlas appartient à Platform.\n'
    assert chunk.extracted_triples[0]['object'] == 'https://example.org/Platform'
    original = gateway.artifacts.get_verified(chunk.chunk_artifact.model_dump())
    gateway.content[uri] = b'changed upstream'
    assert gateway.artifacts.get_verified(chunk.chunk_artifact.model_dump()) == original
    with pytest.raises(GatewayError, match='chunk_span'):
        asyncio.run(gateway.import_snapshot(prepared, receipt, chunk_uris=(uri,), corpus_id=UUID(int=94)))


@pytest.mark.parametrize('failure', ['parent', 'provenance', 'scope', 'version', 'limit', 'selection'])
def test_incomplete_or_wrong_scope_snapshot_never_imports(context, failure):
    gateway, prepared, receipt, uri = populated(context)
    if failure == 'parent':
        gateway.document_metadata[uri]['parent_id'] = 'urn:other'
    elif failure == 'provenance':
        gateway.triples.pop()
    elif failure == 'scope':
        gateway.triples[0]['g'] = 'urn:other'
    elif failure == 'version':
        gateway.configuration_version += 1
    elif failure == 'limit':
        gateway.triples *= 400
    else:
        uri = 'urn:chunk:unregistered'
    with pytest.raises(GatewayError):
        asyncio.run(gateway.import_snapshot(prepared, receipt, chunk_uris=(uri,), corpus_id=UUID(int=93)))


def test_seed_projection_uses_consistent_class_identifiers_and_preserves_full_iris():
    projected = project_seed_ontology(ONTOLOGY.encode())
    owner = projected['objectProperties']['https://example.org/oe-demo/hasOwner']
    assert owner['rdfs:domain'] in projected['classes'] and owner['rdfs:range'] in projected['classes']
    assert owner['uri'] == 'https://example.org/oe-demo/hasOwner'
    assert len(NO_SEED_DIGEST) == 64 and NO_SEED_DIGEST != hashlib.sha256(b'').hexdigest()


@pytest.mark.parametrize('field,value', [('project_id', UUID(int=999)), ('source_id', UUID(int=999)),
    ('seed_digest', 'f' * 64), ('config_digest', 'e' * 64), ('processing_id', 'urn:wrong:processing')])
def test_recovery_rejects_receipt_from_different_preparation(context, field, value):
    gateway, prepared, receipt, _ = populated(context)
    altered = receipt.model_copy(update={field: value})
    with pytest.raises(GatewayError, match='receipt_preparation_mismatch'):
        asyncio.run(gateway.ingest_prepared(prepared, prior_receipt=altered))


@pytest.mark.parametrize('metadata,expected', [({'dt': 'http://www.w3.org/2001/XMLSchema#integer'}, {'datatype': 'http://www.w3.org/2001/XMLSchema#integer'}),
    ({'ln': 'fr'}, {'language': 'fr'})])
def test_import_preserves_pinned_wire_literal_metadata(context, metadata, expected):
    gateway, prepared, receipt, uri = populated(context)
    gateway.triples[-1]['o']['tr']['o'] = {'t': 'l', 'v': '42', **metadata}
    imported = asyncio.run(gateway.import_snapshot(prepared, receipt, chunk_uris=(uri,), corpus_id=UUID(int=93)))
    for field, value in expected.items():
        assert imported.chunks[0].extracted_triples[0][field] == value


def test_ordinary_flow_uses_explicit_no_seed_digest(context):
    gateway, request, _, cfg, _ = context
    cfg['flow-blueprint']['seeded']['flow'] = {'kg-extract-definitions:{id}': {}, 'kg-extract-relationships:{id}': {}}
    cfg.pop('processor:kg-extract-ontology')
    for kind in ('definitions', 'relationships'):
        cfg['processor:kg-extract-' + kind] = {'frozen-flow': {'parameters': {}, 'topics': {}}}
    gateway.configuration = copy.deepcopy(cfg)
    binding = gateway.bindings[request.project_id].model_copy(update={'seed_digest': NO_SEED_DIGEST, 'config_digest': configuration_digest(cfg)})
    gateway.bindings[request.project_id] = binding
    request = request.model_copy(update={'seed_digest': NO_SEED_DIGEST, 'config_digest': binding.config_digest})
    prepared = asyncio.run(gateway.prepare_ingestion(request, expected_configuration=cfg))
    assert prepared.seed_mode == 'ordinary' and prepared.approved_ontology is None and prepared.approved_version_id is None
    receipt = asyncio.run(gateway.ingest_prepared(prepared))
    assert receipt.seed_digest == NO_SEED_DIGEST and receipt.status == 'queued'


@pytest.mark.parametrize('axiom', [
    'demo:Service owl:equivalentClass demo:Team .',
    'demo:hasOwner a owl:FunctionalProperty .',
    'demo:Service rdfs:label demo:Team .',
])
def test_unsupported_seed_schema_does_not_silently_disappear(axiom):
    with pytest.raises(ValueError, match='unsupported|literal'):
        project_seed_ontology((ONTOLOGY + axiom).encode())
