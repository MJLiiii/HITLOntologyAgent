"""Narrow real TrustGraph probe for an already provisioned disposable ordinary flow.

Separate prepare/submit/chunks/import actions keep outbound extraction explicit.
No approvals, seed fixture, graph-RAG call, publication or main Studio state.
Configure the worker and host with the same smoke ledger before submit.
"""
import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from oe_studio.artifacts import ArtifactStore, digest
from oe_studio.integrations.trustgraph.contracts import (
    Artifact, DocumentRegistration, IngestReceipt, IngestRequest, PreparedIngestion,
)
from oe_studio.integrations.trustgraph.gateway import PinnedTrustGraphGateway
from oe_studio.llm_profiles import Profile
from oe_studio.settings import Settings
from oe_studio.trustgraph_workflow import _select_configuration

TEXT = 'Atlas is a service. Platform is a team. The Atlas service is owned by the Platform team.\n'


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with open(temporary, 'w', opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


async def run(args):
    settings = Settings(trustgraph_config_file=args.server_config)
    if not settings.llm_smoke_budget_file or not settings.llm_smoke_price_file:
        raise ValueError('This probe requires the shared smoke budget and verified price paths')
    output = args.output.resolve()
    if args.action == 'prepare':
        output.mkdir(parents=True, exist_ok=False)
        profile = json.loads(args.profile_snapshot.read_text())
        descriptor = {k: v for k, v in profile.items() if k != 'revision'}
        Profile.model_validate(descriptor)
        if set(descriptor) != set(Profile.model_fields) or digest(descriptor) != profile.get('revision'):
            raise ValueError('Frozen profile revision mismatch')
        config = _select_configuration(settings, args.project_id, profile)
        if config.seed_mode != 'ordinary':
            raise ValueError('This probe admits ordinary flows only; no approved seed fixture')
        write(output / 'selection.json', {'profile': profile, 'configuration': config.public()})
    else:
        selection = json.loads((output / 'selection.json').read_text())
        profile = selection['profile']
        config = _select_configuration(settings, args.project_id, profile, selection['configuration'])
    artifacts = ArtifactStore(output / 'artifacts')
    if args.action == 'prepare':
        source = Artifact(**artifacts.put(TEXT.encode(), 'text/plain'))
        source_id = uuid4()
        registration = DocumentRegistration(project_id=config.binding.project_id, source_id=source_id,
            upstream_document_id='urn:oe:disposable-source:' + str(source_id), artifact=source,
            source_uri='https://example.org/synthetic/atlas', title='Disposable synthetic Atlas ownership')
        write(output / 'registration.json', registration.model_dump(mode='json'))
    else:
        registration = DocumentRegistration.model_validate_json((output / 'registration.json').read_text())
    gateway = PinnedTrustGraphGateway(artifacts=artifacts, bindings=[config.binding], documents=[registration])
    if args.action == 'prepare':
        request = IngestRequest(project_id=config.binding.project_id, source_id=registration.source_id,
            artifact=registration.artifact, seed_digest=config.binding.seed_digest,
            config_digest=config.binding.config_digest, idempotency_key=str(uuid4()))
        prepared = await gateway.prepare_ingestion(request, expected_configuration=config.expected_configuration)
        write(output / 'prepared.json', prepared.model_dump(mode='json'))
        print('Prepared the disposable synthetic source; no extraction submitted.')
        return
    prepared = PreparedIngestion.model_validate_json((output / 'prepared.json').read_text())
    if args.action == 'submit':
        started = output / 'submission-started.json'
        uncertain = started.exists()
        if not uncertain:
            write(started, {'preparation_id': str(prepared.id), 'profile_id': profile['id'],
                            'session_id': config.llm_session_id})
        receipt = await gateway.ingest_prepared(prepared, may_have_submitted=uncertain)
        write(output / 'receipt.json', receipt.model_dump(mode='json'))
        print('Recorded the synthetic submission; upstream completion remains unproven.')
        return
    receipt = IngestReceipt.model_validate_json((output / 'receipt.json').read_text())
    if args.action == 'chunks':
        chunks = await gateway.list_registered_chunks(prepared, receipt)
        write(output / 'chunks.json', chunks)
        print(json.dumps({'chunk_uris': chunks['chunk_uris'], 'upstream_completion_supported': False}))
        return
    if not args.chunk_uri:
        raise ValueError('Explicit --chunk-uri selection is required for import')
    imported = await gateway.import_snapshot(prepared, receipt, chunk_uris=tuple(args.chunk_uri),
        corpus_id=uuid5(NAMESPACE_URL, str(prepared.id) + ':selected-synthetic-probe'))
    write(output / 'snapshot.json', imported.model_dump(mode='json'))
    write(output / 'report.json', {'selected_snapshot_verified': True, 'chunks': len(imported.chunks),
        'facts': sum(len(chunk.extracted_triples) for chunk in imported.chunks),
        'profile_id': profile['id'], 'profile_revision': profile['revision'],
        'session_id': config.llm_session_id, 'upstream_completion_supported': False,
        'approvals_created': 0, 'publications_created': 0, 'main_studio_modified': False})
    print('Verified the explicitly selected synthetic source snapshot; no approval or publication created.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=('prepare', 'submit', 'chunks', 'import'), required=True)
    parser.add_argument('--server-config', type=Path, required=True)
    parser.add_argument('--profile-snapshot', type=Path)
    parser.add_argument('--project-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--chunk-uri', action='append')
    args = parser.parse_args()
    if args.action == 'prepare' and args.profile_snapshot is None:
        parser.error('prepare requires --profile-snapshot')
    lock_path = args.output.resolve().with_suffix('.probe.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run(args))


if __name__ == '__main__':
    main()
