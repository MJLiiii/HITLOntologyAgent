"""Explicit in-memory fixture provider; never presented as a live TrustGraph run."""
from datetime import datetime, timezone
from types import SimpleNamespace

from .contracts import IngestStatus
from .gateway import PinnedTrustGraphGateway


class FakeTrustGraphGateway(PinnedTrustGraphGateway):
    mode = 'fake'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.content = {}
        self.document_metadata = {}
        self.processings = []
        self.completed = set()
        self.calls = []
        self.answer = {'text': 'Explicit synthetic fake answer', 'sources': []}
        self.triples = []
        for document in self.documents.values():
            self.content[document.upstream_document_id] = self.artifacts.get_verified(document.artifact.model_dump())
        for corpus in self.corpora.values():
            for ref in corpus.evidence:
                document = self.documents[(ref.project_id, ref.source_id)]
                content = self.content[document.upstream_document_id]
                self.content[ref.upstream_chunk_uri] = content[ref.byte_start:ref.byte_end]
                self.document_metadata[ref.upstream_chunk_uri] = {'id': ref.upstream_chunk_uri,
                                                                'parent_id': document.upstream_document_id}
                self.answer['sources'].append({'uri': ref.upstream_chunk_uri, 'title': document.title})

    def _build_client(self, binding):
        owner = self

        class Library:
            def add_document(self, **kwargs):
                owner.calls.append(('add_document', kwargs))
                owner.content[kwargs['id']] = kwargs['document']
                return {}

            def start_processing(self, **kwargs):
                owner.calls.append(('start_processing', kwargs))
                owner.processings.append(kwargs)
                return {}

            def get_processings(self):
                return owner.processings

            def get_document_content(self, id):
                return owner.content[id]

            def get_document(self, id):
                return owner.document_metadata[id]

            def request(self, request):
                if request['operation'] != 'get-document-metadata' or request['workspace'] != binding.workspace:
                    raise ValueError('Unsupported fake metadata operation or workspace')
                row = owner.document_metadata[request['document-id']]
                return {'document-metadata': {'id': row['id'], 'parent-id': row['parent_id']}}

        class Flow:
            def graph_rag(self, **kwargs):
                owner.calls.append(('graph_rag', kwargs))
                return owner.answer

            def request(self, *, path, request):
                if path != 'service/triples':
                    raise ValueError('Unknown fake service')
                owner.calls.append(('triples_query', request))
                return {'response': owner.triples}

        return SimpleNamespace(workspace=binding.workspace, library=Library,
                               flow=lambda: SimpleNamespace(id=lambda flow_id: Flow()))

    async def ingestion_status(self, receipt):
        observed = await super().ingestion_status(receipt)
        if receipt.ingestion_id not in self.completed:
            return observed
        return IngestStatus(ingestion_id=receipt.ingestion_id, status='completed',
                            observed_at=datetime.now(timezone.utc).isoformat(),
                            completion_supported=True, corpus_freeze_allowed=True,
                            reason='explicit_fake_completion_fixture',
                            provenance_artifacts=observed.provenance_artifacts, mode='fake')
