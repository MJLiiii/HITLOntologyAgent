"""Optional TrustGraph 2.11.1 SDK boundary; unsupported provenance fails closed."""
import asyncio
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import os
from uuid import NAMESPACE_URL, uuid5

from ...artifacts import canonical_json, digest
from .contracts import (Artifact, ContextBundle, EvidenceRecord, IngestReceipt, IngestStatus)
from .contracts import Binding

SDK_VERSION = '2.11.1'
SDK_FILES = {
    'api.py': '8e99dfd93410d0aba325a6b455d93983706801983f82d23fbcbeca8e121ccd3d',
    'flow.py': '21916eda89892abcc36ea59505c67ae817c602b0e917c4591f3613e8adbe3c66',
    'library.py': '0d552c8eda5e198ab1bfc1e09998cc1aae51b15f4839536e2cd64e70460cdd76',
    'types.py': 'bd34fc2d36efd2370aa20b046335368b7878f19191838a4af9e0f42db53047e1',
}


class GatewayError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def binding_from_environment(*, project_id, seed_digest, config_digest):
    """Called by server startup only; credentials never become request fields."""
    return Binding(project_id=project_id, url=os.environ['OE_TG_URL'], workspace=os.environ['OE_TG_WORKSPACE'],
                   flow=os.environ['OE_TG_FLOW'], collection=os.environ['OE_TG_COLLECTION'],
                   token=os.environ.get('OE_TG_TOKEN', ''), seed_digest=seed_digest, config_digest=config_digest)


def verified_sdk(binding):
    try:
        distribution = metadata.distribution('trustgraph-base')
        if distribution.version != SDK_VERSION:
            raise GatewayError('trustgraph_runtime_pin_mismatch')
        for name, expected in SDK_FILES.items():
            path = distribution.locate_file('trustgraph/api/' + name)
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise GatewayError('trustgraph_runtime_source_mismatch')
        from trustgraph.api import Api
    except (metadata.PackageNotFoundError, ImportError, OSError) as exc:
        raise GatewayError('trustgraph_runtime_unavailable_install_optional_extra') from exc
    return Api(url=binding.url, timeout=binding.timeout,
               token=binding.token.get_secret_value() or None, workspace=binding.workspace)


def plain(value):
    """Retain SDK RDF term kinds and literal metadata before JSON serialization."""
    if callable(getattr(value, 'is_literal', None)) and value.is_literal():
        return {'kind': 'literal', 'value': str(value), 'datatype': getattr(value, 'datatype', None),
                'language': getattr(value, 'language', None)}
    if callable(getattr(value, 'is_uri', None)) and value.is_uri():
        return {'kind': 'iri', 'value': str(value)}
    if is_dataclass(value):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise GatewayError('unsupported_upstream_response_type')


class PinnedTrustGraphGateway:
    """Server-owned registries establish scope; none is populated from HTTP payloads.

    Receipt idempotency is process-local. Persist receipts/idempotency in the root
    workflow job ledger before activating this provider for restart recovery.
    """
    mode = 'real'

    def __init__(self, *, artifacts, bindings, documents=(), corpora=()):
        self.artifacts = artifacts
        self.bindings = {b.project_id: b for b in bindings}
        self.documents = {(d.project_id, d.source_id): d for d in documents}
        self.corpora = {(c.project_id, c.corpus_id): c for c in corpora}
        self._clients = {}
        self._receipts = {}

    def _build_client(self, binding):
        return verified_sdk(binding)

    def _client(self, project_id):
        if project_id not in self.bindings:
            raise GatewayError('project_binding_not_authorized')
        if project_id not in self._clients:
            self._clients[project_id] = self._build_client(self.bindings[project_id])
        client = self._clients[project_id]
        if client.workspace != self.bindings[project_id].workspace:
            raise GatewayError('workspace_binding_mismatch')
        return client

    def _document(self, project_id, source_id):
        document = self.documents.get((project_id, source_id))
        if document is None:
            raise GatewayError('source_not_authorized')
        return document

    def _corpus(self, project_id, corpus_id):
        corpus = self.corpora.get((project_id, corpus_id))
        if corpus is None or any(r.project_id != project_id or r.corpus_id != corpus_id
                                 or r.graph_uri not in (None, corpus.graph_uri) for r in corpus.evidence):
            raise GatewayError('corpus_not_authorized')
        return corpus

    def _binding_digest(self, project_id):
        return digest(self.bindings[project_id].model_dump(mode='json', exclude={'token'}))

    def _store(self, value):
        content = canonical_json(plain(value))
        if len(content) > 2_097_152:
            raise GatewayError('upstream_response_exceeds_limit')
        return Artifact(**self.artifacts.put(content, 'application/json'))

    async def _call(self, project_id, function, **kwargs):
        try:
            return await asyncio.wait_for(asyncio.to_thread(function, **kwargs),
                                          timeout=self.bindings[project_id].timeout + 1)
        except GatewayError:
            raise
        except Exception as exc:
            # Upstream exceptions can include URLs or credentials; expose only a safe code.
            raise GatewayError('trustgraph_upstream_call_failed') from exc

    async def ingest(self, request):
        document = self._document(request.project_id, request.source_id)
        client = self._client(request.project_id)
        binding = self.bindings[request.project_id]
        if request.seed_digest != binding.seed_digest or request.config_digest != binding.config_digest:
            raise GatewayError('ingestion_configuration_mismatch')
        if request.artifact != document.artifact:
            raise GatewayError('document_artifact_mismatch')
        content = self.artifacts.get_verified(document.artifact.model_dump())
        key = (request.project_id, request.idempotency_key)
        payload_digest = digest(request.model_dump(mode='json'))
        if key in self._receipts:
            previous_digest, receipt = self._receipts[key]
            if previous_digest != payload_digest:
                raise GatewayError('idempotency_payload_conflict')
            return receipt
        ingestion_id = uuid5(NAMESPACE_URL, f'{request.project_id}:{request.idempotency_key}')
        processing_id = 'urn:oe:processing:' + str(ingestion_id)
        library = client.library()
        uploaded = await self._call(request.project_id, library.add_document, document=content,
                                    id=document.upstream_document_id, metadata=[], title=document.title,
                                    comments='Ontology Studio synthetic/source import',
                                    kind=document.artifact.media_type, tags=['ontology-studio'])
        submitted = await self._call(request.project_id, library.start_processing, id=processing_id,
                                     document_id=document.upstream_document_id, flow=binding.flow,
                                     collection=binding.collection, tags=['ontology-studio'])
        receipt = IngestReceipt(ingestion_id=ingestion_id, project_id=request.project_id,
                                source_id=request.source_id, document_uri=document.upstream_document_id,
                                processing_id=processing_id, binding_digest=self._binding_digest(request.project_id),
                                seed_digest=request.seed_digest, config_digest=request.config_digest, status='queued',
                                raw_artifact=self._store({'upload': uploaded, 'submission': submitted}))
        self._receipts[key] = (payload_digest, receipt)
        return receipt

    async def ingestion_status(self, receipt):
        client = self._client(receipt.project_id)
        binding = self.bindings[receipt.project_id]
        document = self._document(receipt.project_id, receipt.source_id)
        if (receipt.binding_digest != self._binding_digest(receipt.project_id)
                or receipt.document_uri != document.upstream_document_id):
            raise GatewayError('receipt_binding_mismatch')
        rows = await self._call(receipt.project_id, client.library().get_processings)
        raw = self._store(rows)
        matches = [plain(row) for row in rows if plain(row).get('id') == receipt.processing_id]
        if len(matches) > 1:
            raise GatewayError('ambiguous_processing_status')
        if matches and any(matches[0].get(key) != expected for key, expected in (
            ('document_id', document.upstream_document_id), ('flow', binding.flow), ('collection', binding.collection))):
            raise GatewayError('processing_scope_mismatch')
        # This SDK exposes active metadata, not a completion/error event contract.
        return IngestStatus(ingestion_id=receipt.ingestion_id,
                            status='processing' if matches else 'unknown',
                            observed_at=datetime.now(timezone.utc).isoformat(), completion_supported=False,
                            reason='completion_not_observable_from_active_processing_list',
                            provenance_artifacts=(raw,), mode=self.mode)

    async def resolve_evidence(self, ref):
        corpus = self._corpus(ref.project_id, ref.corpus_id)

        def unresolved(reason):
            return EvidenceRecord(ref=ref, resolved=False, reason=reason)

        if ref not in corpus.evidence:
            return unresolved('reference_not_in_frozen_corpus')
        document = self._document(ref.project_id, ref.source_id)
        if document.artifact.sha256 != ref.source_sha256 or document.artifact.media_type != 'text/plain':
            return unresolved('unsupported_or_mismatched_source')
        try:
            library = self._client(ref.project_id).library()
            source = await self._call(ref.project_id, library.get_document_content, id=document.upstream_document_id)
            if (not isinstance(source, bytes) or len(source) > 2_097_152
                    or hashlib.sha256(source).hexdigest() != ref.source_sha256):
                return unresolved('source_hash_mismatch')
            if ref.upstream_chunk_uri == document.upstream_document_id:
                chunk = source
                raw_metadata = {'id': document.upstream_document_id, 'kind': 'source'}
            else:
                # SDK get_document emits the unregistered get-document operation
                # and requires a time field absent from actual child metadata.
                metadata_response = plain(await self._call(ref.project_id, library.request, request={
                    'operation': 'get-document-metadata', 'workspace': self.bindings[ref.project_id].workspace,
                    'document-id': ref.upstream_chunk_uri}))
                raw_metadata = metadata_response.get('document-metadata', {})
                if (not isinstance(raw_metadata, dict)
                        or raw_metadata.get('parent-id') != document.upstream_document_id
                        or raw_metadata.get('id') != ref.upstream_chunk_uri):
                    return unresolved('chunk_parent_not_verified')
                chunk = await self._call(ref.project_id, library.get_document_content, id=ref.upstream_chunk_uri)
            if (not isinstance(chunk, bytes) or hashlib.sha256(chunk).hexdigest() != ref.chunk_sha256
                    or ref.byte_end > len(source) or source[ref.byte_start:ref.byte_end] != chunk):
                return unresolved('chunk_hash_or_span_mismatch')
            text = chunk.decode('utf-8')
            if ref.quote != text:
                return unresolved('quotation_mismatch')
            artifact = Artifact(**self.artifacts.put(chunk, 'text/plain'))
            return EvidenceRecord(ref=ref, resolved=True, quote=text, chunk_artifact=artifact,
                                  raw_artifact=self._store(raw_metadata))
        except (GatewayError, UnicodeDecodeError, OSError, ValueError):
            return unresolved('evidence_resolution_failed')

    async def retrieve(self, request):
        corpus = self._corpus(request.project_id, request.corpus_id)
        client = self._client(request.project_id)
        binding = self.bindings[request.project_id]
        flow = client.flow().id(binding.flow)
        if request.retrieval_config_digest != binding.config_digest:
            raise GatewayError('retrieval_configuration_mismatch')
        answer = plain(await self._call(request.project_id, flow.graph_rag, query=request.query,
                                        collection=binding.collection, entity_limit=request.entity_limit,
                                        triple_limit=min(30, request.triple_limit),
                                        max_subgraph_size=request.triple_limit))
        # SDK triples_query() drops wire literal metadata and named-graph fields.
        # Use its inspected fixed service path through FlowInstance.request so the
        # exact RDF wire objects survive. No caller-supplied paths or payload scope.
        triple_response = plain(await self._call(request.project_id, flow.request, path='service/triples',
                                                request={'collection': binding.collection, 'g': corpus.graph_uri,
                                                         'limit': request.triple_limit}))
        triples = triple_response.get('response') if isinstance(triple_response, dict) else None
        if not isinstance(answer, dict) or not isinstance(answer.get('sources'), list) or not isinstance(triples, list):
            raise GatewayError('invalid_retrieval_response')
        if any(t.get('g') not in ('', None, corpus.graph_uri) for t in triples):
            raise GatewayError('graph_scope_mismatch')
        source_uris = [s.get('uri') if isinstance(s, dict) else None for s in answer['sources']]
        # No tokenizer is supplied by this SDK; use a conservative UTF-8 byte budget
        # and record that basis rather than inventing an observed model token count.
        truncated = (len(triples) >= request.triple_limit or len(source_uris) > request.chunk_limit
                     or len((answer.get('text') or '').encode()) > request.token_limit)
        records, unresolved = [], []
        for uri in source_uris[:request.chunk_limit]:
            # Actual GraphRAG sources identify original documents. Resolve only
            # children already frozen for that document in this project's corpus.
            refs = [r for r in corpus.evidence if r.upstream_chunk_uri == uri or (
                (document := self.documents.get((request.project_id, r.source_id))) is not None
                and document.upstream_document_id == uri)]
            if not isinstance(uri, str) or not refs:
                unresolved.append(str(uri))
                continue
            remaining = request.chunk_limit - len(records)
            if len(refs) > remaining:
                truncated = True
            for ref in refs[:remaining]:
                records.append(await self.resolve_evidence(ref))
        if sum(len((record.quote or '').encode()) for record in records) > request.token_limit:
            truncated = True
        reasons = []
        if not corpus.provenance_verified:
            reasons.append('corpus_completion_and_provenance_not_verified')
        if unresolved or not records or any(not r.resolved for r in records):
            reasons.append('unresolved_source_evidence')
        if truncated:
            reasons.append('retrieval_limit_reached')
        raw = self._store({'graph_rag': answer, 'triples_response': triple_response})
        graph = self._store({'graph_uri': corpus.graph_uri, 'collection': binding.collection, 'triples': triples})
        manifest = {'request': request.model_dump(mode='json'), 'binding_digest': self._binding_digest(request.project_id),
                    'graph_artifact': graph.model_dump(), 'raw_trace_artifact': raw.model_dump(),
                    'evidence': [r.model_dump(mode='json') for r in records],
                    'unresolved_source_uris': unresolved, 'truncated': truncated,
                    'token_budget_basis': 'conservative_utf8_bytes', 'observed_tokens': None,
                    'review_eligible': not reasons, 'reasons': reasons, 'mode': self.mode}
        return ContextBundle(manifest_digest=digest(manifest), manifest_artifact=self._store(manifest),
                             graph_artifact=graph, raw_artifact=raw, evidence=tuple(records),
                             unresolved_source_uris=tuple(unresolved), truncated=truncated,
                             review_eligible=not reasons, reasons=tuple(reasons), mode=self.mode)
