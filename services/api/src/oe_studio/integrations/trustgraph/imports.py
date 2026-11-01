"""Preparation, retry reconciliation and immutable *selected* corpus imports.

The application owns atomic Job/Item persistence and leases. Preparation must be
durably stored before ingest_prepared. No helper declares global processing done.
"""
import hashlib
import json
import re
from uuid import NAMESPACE_URL, uuid5

from ...artifacts import canonical_json, digest
from ...schemas import Triple
from .contracts import Artifact, ImportedChunk, ImportedSnapshot, IngestReceipt, PreparedIngestion
from .gateway import GatewayError, plain
from .seed import project_seed_ontology

NO_SEED_DIGEST = hashlib.sha256(canonical_json({'mode': 'ordinary', 'seed': None})).hexdigest()
SOURCE_GRAPH = 'urn:graph:source'
PROV = 'http://www.w3.org/ns/prov#'
TG = 'https://trustgraph.ai/ns/'
GRAPH_LIMIT = 2000


def configuration_digest(configuration):
    return hashlib.sha256(canonical_json(configuration)).hexdigest()


def _public_configuration(value):
    if isinstance(value, dict):
        for key, child in value.items():
            name = re.sub(r'[^a-z0-9]', '', key.lower())
            if any(word in name for word in ('password', 'secret', 'credential', 'apikey', 'authorization')) or name in {'token', 'accesstoken', 'refreshtoken', 'authtoken'}:
                raise GatewayError('private_configuration_not_admitted')
            _public_configuration(child)
    elif isinstance(value, list):
        for child in value:
            _public_configuration(child)


def _run_source(source, request, version):
    # A new intent/configuration gets a distinct remote parent. Processor-name
    # provenance alone cannot distinguish extraction runs of the same bytes.
    identity = uuid5(NAMESPACE_URL, digest({'request': request.model_dump(mode='json'), 'configuration_version': version}))
    return identity, source.model_copy(update={'upstream_document_id': 'urn:oe:ingestion-source:' + str(identity)})


async def _configuration(gateway, project, expected):
    binding, client = gateway.bindings[project], gateway._client(project)
    if not isinstance(expected, dict) or not expected or len(canonical_json(expected)) > 1_048_576:
        raise GatewayError('invalid_expected_configuration')
    if any(kind not in {'ontology', 'flow', 'flow-blueprint', 'prompt'} and not kind.startswith('processor:') for kind in expected):
        raise GatewayError('configuration_type_not_admitted')
    _public_configuration(expected)
    keys = [{'type': kind, 'key': key} for kind, values in expected.items() for key in values]
    if len(keys) > 200 or 'ontology' not in expected or binding.flow not in expected.get('flow', {}):
        raise GatewayError('configuration_selection_incomplete')
    response = plain(await gateway._call(project, client.request, path='config', request={
        'operation': 'get', 'workspace': binding.workspace, 'keys': keys}))
    observed = {kind: {} for kind in expected}
    for row in response.get('values', []):
        if row.get('type') not in observed or row.get('key') not in expected[row['type']]:
            raise GatewayError('unexpected_configuration_record')
        try:
            observed[row['type']][row['key']] = json.loads(row['value'])
        except (TypeError, ValueError, KeyError) as exc:
            raise GatewayError('invalid_configuration_record') from exc
    # All ontology definitions influence the upstream selector. Extra seeds may
    # not be hidden by querying only the expected key.
    all_seeds = plain(await gateway._call(project, client.request, path='config', request={
        'operation': 'getvalues', 'workspace': binding.workspace, 'type': 'ontology'}))
    try:
        observed['ontology'] = {row['key']: json.loads(row['value']) for row in all_seeds['values']}
    except (TypeError, ValueError, KeyError) as exc:
        raise GatewayError('invalid_seed_configuration') from exc
    version = response.get('version')
    if not isinstance(version, int) or version < 1 or all_seeds.get('version') != version:
        raise GatewayError('configuration_changed_during_read')
    all_prompts = plain(await gateway._call(project, client.request, path='config', request={
        'operation': 'getvalues', 'workspace': binding.workspace, 'type': 'prompt'}))
    try:
        observed['prompt'] = {row['key']: json.loads(row['value']) for row in all_prompts['values']}
    except (TypeError, ValueError, KeyError) as exc:
        raise GatewayError('invalid_prompt_configuration') from exc
    if all_prompts.get('version') != version:
        raise GatewayError('configuration_changed_during_read')
    if observed != expected:
        raise GatewayError('remote_configuration_mismatch')
    return version


def _validate_configuration_scope(binding, expected, seeded):
    flow = expected.get('flow', {}).get(binding.flow, {})
    blueprint_name = flow.get('blueprint-name')
    blueprint = expected.get('flow-blueprint', {}).get(blueprint_name, {})
    if not blueprint or not expected.get('prompt'):
        raise GatewayError('configuration_selection_incomplete')
    processors = set()
    params = flow.get('parameters', {})
    for area in ('flow', 'blueprint'):
        for declaration in blueprint.get(area, {}):
            processor, variant = declaration.split(':', 1)
            processors.add(processor)
            variant = variant.replace('{id}', binding.flow).replace('{workspace}', binding.workspace).replace('{blueprint}', blueprint_name)
            for key, value in params.items():
                variant = variant.replace('{' + key + '}', str(value))
            if variant not in expected.get('processor:' + processor, {}):
                raise GatewayError('processor_configuration_missing')
    if ('kg-extract-ontology' in processors) != seeded:
        raise GatewayError('seed_mode_flow_mismatch')


async def prepare_ingestion(gateway, request, *, approved_version_id=None, approved_ontology=None, expected_configuration):
    binding = gateway.bindings[request.project_id]
    source = gateway._document(request.project_id, request.source_id)
    if request.artifact != source.artifact or source.artifact.media_type != 'text/plain':
        raise GatewayError('unsupported_source_registration')
    gateway.artifacts.get_verified(source.artifact.model_dump())
    seeded = approved_ontology is not None
    if seeded:
        approved_ontology = Artifact.model_validate(approved_ontology)
        if approved_version_id is None or request.seed_digest.removeprefix('sha256:') != approved_ontology.sha256:
            raise GatewayError('approved_seed_binding_missing')
        projection = project_seed_ontology(gateway.artifacts.get_verified(approved_ontology.model_dump()))
        seeds = expected_configuration.get('ontology', {})
        if len(seeds) != 1 or next(iter(seeds.values())) != projection:
            raise GatewayError('approved_seed_projection_mismatch')
    elif approved_version_id is not None or request.seed_digest.removeprefix('sha256:') != NO_SEED_DIGEST:
        raise GatewayError('ordinary_no_seed_binding_required')
    config_hash = configuration_digest(expected_configuration)
    if (request.seed_digest != binding.seed_digest or request.config_digest != binding.config_digest
            or binding.config_digest.removeprefix('sha256:') != config_hash):
        raise GatewayError('ingestion_configuration_mismatch')
    _validate_configuration_scope(binding, expected_configuration, seeded)
    version = await _configuration(gateway, request.project_id, expected_configuration)
    identity, source = _run_source(source, request, version)
    gateway.documents[(request.project_id, request.source_id)] = source
    body = {'id': str(identity),
            'request': request.model_dump(mode='json'), 'binding_digest': gateway._binding_digest(request.project_id),
            'source': source.model_dump(mode='json'), 'seed_mode': 'approved_ontology' if seeded else 'ordinary',
            'approved_version_id': str(approved_version_id) if approved_version_id else None,
            'approved_ontology': approved_ontology.model_dump(mode='json') if seeded else None,
            'configuration_artifact': gateway._store(expected_configuration).model_dump(),
            'configuration_version': version}
    return PreparedIngestion(**body, manifest_artifact=gateway._store(body), manifest_digest=digest(body))


async def _verify_prepared(gateway, prepared):
    body = prepared.model_dump(mode='json', exclude={'manifest_artifact', 'manifest_digest'})
    if digest(body) != prepared.manifest_digest or gateway.artifacts.get_verified(prepared.manifest_artifact.model_dump()) != canonical_json(body):
        raise GatewayError('preparation_integrity_failed')
    project = prepared.request.project_id
    identity, source = _run_source(gateway._document(project, prepared.request.source_id), prepared.request, prepared.configuration_version)
    if gateway._binding_digest(project) != prepared.binding_digest or source != prepared.source or identity != prepared.id:
        raise GatewayError('preparation_binding_changed')
    gateway.documents[(project, prepared.request.source_id)] = source
    gateway.artifacts.get_verified(prepared.source.artifact.model_dump())
    if prepared.approved_ontology is not None:
        gateway.artifacts.get_verified(prepared.approved_ontology.model_dump())
    expected = json.loads(gateway.artifacts.get_verified(prepared.configuration_artifact.model_dump()))
    if await _configuration(gateway, project, expected) != prepared.configuration_version:
        raise GatewayError('configuration_version_changed')
    return expected


def _verify_receipt(prepared, receipt):
    expected = {'ingestion_id': prepared.id, 'project_id': prepared.request.project_id,
                'source_id': prepared.source.source_id, 'document_uri': prepared.source.upstream_document_id,
                'processing_id': 'urn:oe:processing:' + str(prepared.id), 'binding_digest': prepared.binding_digest,
                'seed_digest': prepared.request.seed_digest, 'config_digest': prepared.request.config_digest}
    if any(getattr(receipt, key) != value for key, value in expected.items()):
        raise GatewayError('receipt_preparation_mismatch')


async def ingest_prepared(gateway, prepared, *, prior_receipt=None, may_have_submitted=False):
    await _verify_prepared(gateway, prepared)
    request, source = prepared.request, prepared.source
    project, binding = request.project_id, gateway.bindings[request.project_id]
    library = gateway._client(project).library()
    processing_id = 'urn:oe:processing:' + str(prepared.id)
    rows = plain(await gateway._call(project, library.get_processings))
    matches = [row for row in rows if row.get('id') == processing_id]
    if len(matches) > 1 or any(any(row.get(k) != v for k, v in {
        'document_id': source.upstream_document_id, 'flow': binding.flow, 'collection': binding.collection}.items()) for row in matches):
        raise GatewayError('processing_scope_mismatch')
    if prior_receipt is not None:
        _verify_receipt(prepared, prior_receipt)
    if matches:
        content = await gateway._call(project, library.get_document_content, id=source.upstream_document_id)
        if hashlib.sha256(content).hexdigest() != source.artifact.sha256:
            raise GatewayError('source_hash_mismatch')
        await _verify_prepared(gateway, prepared)
        if prior_receipt is not None:
            return prior_receipt
        submitted = {'recovered_existing_submission': matches}
        uploaded = {'verified_existing_source_sha256': source.artifact.sha256}
    else:
        if may_have_submitted or prior_receipt is not None:
            raise GatewayError('ambiguous_submission_requires_reconciliation')
        listed = plain(await gateway._call(project, library.request, request={
            'operation': 'list-documents', 'workspace': binding.workspace}))
        gateway._store(listed)
        documents = listed.get('document-metadatas', [])
        if len(documents) >= 1000:
            raise GatewayError('document_inventory_exceeds_bound')
        existing = [row for row in documents if row.get('id') == source.upstream_document_id]
        content = gateway.artifacts.get_verified(source.artifact.model_dump())
        if existing:
            remote = await gateway._call(project, library.get_document_content, id=source.upstream_document_id)
            if remote != content:
                raise GatewayError('existing_document_conflict')
            uploaded = {'verified_existing_source_sha256': source.artifact.sha256}
        else:
            uploaded = await gateway._call(project, library.add_document, document=content, id=source.upstream_document_id,
                                           metadata=[], title=source.title, comments='Ontology Studio registered source',
                                           kind=source.artifact.media_type, tags=['ontology-studio'])
        await _verify_prepared(gateway, prepared)
        submitted = await gateway._call(project, library.start_processing, id=processing_id, document_id=source.upstream_document_id,
                                        flow=binding.flow, collection=binding.collection, tags=['ontology-studio'])
        await _verify_prepared(gateway, prepared)
    return IngestReceipt(ingestion_id=prepared.id, project_id=project, source_id=request.source_id,
                         document_uri=source.upstream_document_id, processing_id=processing_id,
                         binding_digest=prepared.binding_digest, seed_digest=request.seed_digest,
                         config_digest=request.config_digest, status='queued',
                         raw_artifact=gateway._store({'preparation_digest': prepared.manifest_digest, 'upload': uploaded, 'submission': submitted}))


async def _source_graph(gateway, prepared, receipt):
    await _verify_prepared(gateway, prepared)
    _verify_receipt(prepared, receipt)
    project = prepared.request.project_id
    status = await gateway.ingestion_status(receipt)
    if status.status != 'processing':
        raise GatewayError('submission_not_observed')
    binding = gateway.bindings[project]
    flow = gateway._client(project).flow().id(binding.flow)
    response = plain(await gateway._call(project, flow.request, path='service/triples', request={
        'collection': binding.collection, 'g': SOURCE_GRAPH, 'limit': GRAPH_LIMIT}))
    rows = response.get('response')
    if not isinstance(rows, list) or len(rows) >= GRAPH_LIMIT or any(row.get('g') != SOURCE_GRAPH for row in rows):
        raise GatewayError('provenance_graph_scope_or_limit')
    return rows, gateway._store(response)


async def list_registered_chunks(gateway, prepared, receipt):
    rows, artifact = await _source_graph(gateway, prepared, receipt)
    ids = sorted({row['s']['i'] for row in rows if row.get('p', {}).get('i') == PROV + 'wasDerivedFrom'
                  and row.get('o', {}).get('i') == prepared.source.upstream_document_id
                  and row.get('s', {}).get('i', '').startswith('urn:chunk:')})
    await _verify_prepared(gateway, prepared)
    return {'chunk_uris': ids, 'source_id': str(prepared.source.source_id), 'provenance_artifact': artifact.model_dump(),
            'selection_required': True, 'upstream_completion_supported': False}


def _normalized_triple(wire):
    s, p, o = wire.get('s', {}), wire.get('p', {}), wire.get('o', {})
    if s.get('t') != 'i' or p.get('t') != 'i' or o.get('t') not in ('i', 'l'):
        raise GatewayError('unsupported_extracted_rdf_term')
    return Triple(subject=s['i'], predicate=p['i'], object=o.get('i') if o['t'] == 'i' else o.get('v'),
                  object_type='iri' if o['t'] == 'i' else 'literal',
                  datatype=o.get('dt') or o.get('d') or o.get('datatype'),
                  language=o.get('ln') or o.get('l') or o.get('language')).model_dump()


async def import_snapshot(gateway, prepared, receipt, *, chunk_uris, corpus_id):
    if not 1 <= len(chunk_uris) <= 50 or len(set(chunk_uris)) != len(chunk_uris):
        raise GatewayError('invalid_explicit_chunk_selection')
    rows, provenance = await _source_graph(gateway, prepared, receipt)
    project, source = prepared.request.project_id, prepared.source
    binding, library = gateway.bindings[project], gateway._client(project).library()
    source_bytes = await gateway._call(project, library.get_document_content, id=source.upstream_document_id)
    if source_bytes != gateway.artifacts.get_verified(source.artifact.model_dump()):
        raise GatewayError('source_hash_mismatch')
    normalized = source_bytes.decode('utf-8-sig').replace('\r\n', '\n')
    normalized_artifact = Artifact(**gateway.artifacts.put(normalized.encode(), 'text/plain'))
    chunks = []

    def links(subject, predicate):
        return [row['o'] for row in rows if row.get('s', {}).get('i') == subject and row.get('p', {}).get('i') == predicate]

    for uri in sorted(chunk_uris):
        if links(uri, PROV + 'wasDerivedFrom') != [{'t': 'i', 'i': source.upstream_document_id}]:
            raise GatewayError('selected_chunk_parent_not_verified')
        metadata = plain(await gateway._call(project, library.request, request={
            'operation': 'get-document-metadata', 'workspace': binding.workspace, 'document-id': uri}))
        row = metadata.get('document-metadata', {})
        if row.get('id') != uri or row.get('parent-id') != source.upstream_document_id or row.get('document-type') != 'chunk':
            raise GatewayError('selected_chunk_metadata_mismatch')
        chunk = await gateway._call(project, library.get_document_content, id=uri)
        start = source_bytes.find(chunk)
        if not chunk or len(chunk) > 32000 or start < 0 or source_bytes.rfind(chunk) != start:
            raise GatewayError('chunk_span_missing_or_ambiguous')
        quote = chunk.decode('utf-8-sig').replace('\r\n', '\n')
        span_start = len(source_bytes[:start].decode('utf-8-sig').replace('\r\n', '\n'))
        if normalized[span_start:span_start + len(quote)] != quote:
            raise GatewayError('normalized_chunk_span_mismatch')
        subgraphs, facts = set(), []
        required = {'kg-extract-ontology'} if prepared.seed_mode == 'approved_ontology' else {'kg-extract-definitions', 'kg-extract-relationships'}
        stages = set()
        for statement in rows:
            if statement.get('p', {}).get('i') != TG + 'contains' or statement.get('o', {}).get('t') != 't':
                continue
            sg = statement.get('s', {}).get('i')
            if links(sg, PROV + 'wasDerivedFrom') != [{'t': 'i', 'i': uri}]:
                continue
            verified_stages = {agent.get('i', '').removeprefix('https://trustgraph.ai/agent/')
                               for activity in links(sg, PROV + 'wasGeneratedBy')
                               for agent in links(activity.get('i'), PROV + 'wasAssociatedWith')}
            if not verified_stages & required:
                continue
            stages.update(verified_stages & required)
            subgraphs.add(sg)
            facts.append(_normalized_triple(statement['o']['tr']))
        if stages != required or not facts:
            raise GatewayError('required_extraction_stage_evidence_missing')
        chunks.append(ImportedChunk(evidence_id=uuid5(NAMESPACE_URL, f'{corpus_id}:{uri}'), upstream_chunk_uri=uri,
                      source_id=source.source_id, source_artifact=source.artifact,
                      upstream_chunk_artifact=Artifact(**gateway.artifacts.put(chunk, 'text/plain')),
                      normalized_source_artifact=normalized_artifact,
                      chunk_artifact=Artifact(**gateway.artifacts.put(quote.encode(), 'text/plain')),
                      metadata_artifact=gateway._store(metadata), quote=quote, byte_start=start, byte_end=start + len(chunk),
                      span_start=span_start, span_end=span_start + len(quote), subgraph_uris=tuple(sorted(subgraphs)),
                      extracted_triples=tuple(sorted(facts, key=canonical_json))))
    await _verify_prepared(gateway, prepared)
    body = {'id': str(corpus_id), 'project_id': str(project), 'ingestion_id': str(prepared.id),
            'status': 'verified_selection', 'selection_kind': 'explicit_registered_chunks', 'upstream_completion_supported': False,
            'source_artifact': source.artifact.model_dump(), 'configuration_artifact': prepared.configuration_artifact.model_dump(),
            'provenance_artifact': provenance.model_dump(), 'chunks': [chunk.model_dump(mode='json') for chunk in chunks]}
    return ImportedSnapshot(**body, manifest_artifact=gateway._store(body), manifest_digest=digest(body))
