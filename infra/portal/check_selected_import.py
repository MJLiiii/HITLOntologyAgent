"""Real synthetic adapter contract probe; approved-version input is a test fixture.

It never writes a Studio project, review or publication. All remote writes target
the explicit oe-ontology-v5 synthetic flow/collection; previous runs are retained.
"""
import asyncio
import copy
import json
from pathlib import Path
import time
from uuid import NAMESPACE_URL, uuid5

from trustgraph.api import ConfigKey, ConfigValue
from oe_studio.artifacts import ArtifactStore
from oe_studio.integrations.trustgraph.contracts import Artifact, Binding, DocumentRegistration, IngestRequest, PreparedIngestion
from oe_studio.integrations.trustgraph.gateway import GatewayError, PinnedTrustGraphGateway
from oe_studio.integrations.trustgraph.imports import configuration_digest
from oe_studio.integrations.trustgraph.seed import project_seed_ontology

from init_pipeline import BASE, api
from check_pipeline import TEXT, write

FLOW = 'oe-ontology-v5'
SEED = '''@prefix ex: <https://example.org/demo#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:Service a owl:Class ; rdfs:label "Service" .
ex:Team a owl:Class ; rdfs:label "Team" .
ex:ownedBy a owl:ObjectProperty ; rdfs:label "owned by" ; rdfs:domain ex:Service ; rdfs:range ex:Team .
'''


def capture_configuration(client, flow_id):
    def get(kind, key):
        return json.loads(client.config().get([ConfigKey(type=kind, key=key)])[0].value)
    flow = get('flow', flow_id)
    name = flow['blueprint-name']
    blueprint = get('flow-blueprint', name)
    config = {'flow': {flow_id: flow}, 'flow-blueprint': {name: blueprint},
              'prompt': {item.key: json.loads(item.value) for item in client.config().get_values('prompt')},
              'ontology': {item.key: json.loads(item.value) for item in client.config().get_values('ontology')}}
    for area in ('flow', 'blueprint'):
        for declaration in blueprint.get(area, {}):
            processor, variant = declaration.split(':', 1)
            variant = variant.replace('{id}', flow_id).replace('{workspace}', client.workspace).replace('{blueprint}', name)
            for key, value in flow.get('parameters', {}).items():
                variant = variant.replace('{' + key + '}', str(value))
            config.setdefault('processor:' + processor, {})[variant] = get('processor:' + processor, variant)
    return config


def main(output):
    if output.exists():
        raise ValueError('Choose a fresh output directory; prior probe evidence is immutable')
    output.mkdir(parents=True)
    client = api()
    if FLOW in client.flow().list():
        raise ValueError('Synthetic v5 flow already exists; do not silently repeat this ingestion')
    original = json.loads((BASE / 'pipeline-config-v4.json').read_text())
    blueprint = copy.deepcopy(original['blueprints']['oe-ontology-v4'])
    client.config().put([
        ConfigValue(type='flow-blueprint', key=FLOW, value=json.dumps(blueprint)),
        ConfigValue(type='ontology', key='oe-synthetic-ownership', value=json.dumps(project_seed_ontology(SEED.encode()))),
        ConfigValue(type='collection', key=FLOW, value=json.dumps({'collection': FLOW, 'name': FLOW, 'description': 'Synthetic selected import contract test', 'tags': ['synthetic']})),
    ])
    params = {'llm-model': 'oe-qwen3-smoke:1.7b', 'llm-rag-model': 'oe-qwen3-smoke:1.7b', 'llm-temperature': '0',
              'llm-rag-temperature': '0', 'embeddings-model': 'all-minilm:latest', 'reranker-model': 'ms-marco-TinyBERT-L-2-v2',
              'chunk-size': '2000', 'chunk-overlap': '0'}
    client.flow().start(FLOW, FLOW, 'Explicit synthetic seed-projection/import probe', parameters=params)
    config = capture_configuration(client, FLOW)
    artifacts = ArtifactStore(output / 'artifacts')
    seed = Artifact(**artifacts.put(SEED.encode(), 'text/turtle'))
    source = Artifact(**artifacts.put(TEXT.encode(), 'text/plain'))
    project, document, version, corpus = [uuid5(NAMESPACE_URL, FLOW + ':' + key) for key in ('project', 'source', 'simulated-approved-version', 'corpus')]
    binding = Binding(project_id=project, url='http://127.0.0.1:18888', workspace='default', flow=FLOW, collection=FLOW,
                      token=client.token, seed_digest=seed.sha256, config_digest=configuration_digest(config), timeout=60)
    registration = DocumentRegistration(project_id=project, source_id=document, upstream_document_id='urn:oe:document:' + str(document),
                                        artifact=source, source_uri='https://example.org/synthetic/atlas', title='Synthetic Atlas ownership')
    gateway = PinnedTrustGraphGateway(artifacts=artifacts, bindings=[binding], documents=[registration])
    request = IngestRequest(project_id=project, source_id=document, artifact=source, seed_digest=seed.sha256,
                            config_digest=binding.config_digest, idempotency_key='synthetic-v5')
    prepared = asyncio.run(gateway.prepare_ingestion(request, approved_version_id=version, approved_ontology=seed, expected_configuration=config))
    write(output / 'prepared.json', prepared.model_dump(mode='json'))
    write(output / 'authority.json', {'mode': 'synthetic_adapter_contract_test', 'approved_version_input': 'simulated isolated test fixture',
                                     'human_study_observation': False, 'main_studio_modified': False})
    prepared = PreparedIngestion.model_validate_json((output / 'prepared.json').read_text())
    receipt = asyncio.run(gateway.ingest_prepared(prepared))
    write(output / 'receipt.json', receipt.model_dump(mode='json'))
    # Process reconstruction: registered binding plus the durable preparation are
    # sufficient to reattach the exact submitted ID without another enqueue.
    reconstructed = PinnedTrustGraphGateway(artifacts=artifacts, bindings=[binding], documents=[registration])
    recovered = asyncio.run(reconstructed.ingest_prepared(prepared, may_have_submitted=True))
    write(output / 'recovered.json', recovered.model_dump(mode='json'))
    deadline = time.monotonic() + 120
    while True:
        hints = asyncio.run(gateway.list_registered_chunks(prepared, receipt))
        write(output / 'chunk-hints.json', hints)
        try:
            imported = asyncio.run(gateway.import_snapshot(prepared, receipt, chunk_uris=tuple(hints['chunk_uris']), corpus_id=corpus))
            break
        except GatewayError as exc:
            write(output / 'pending.json', {'status': 'selection_not_verified', 'reason': exc.code})
            if exc.code not in {'invalid_explicit_chunk_selection', 'required_extraction_stage_evidence_missing'} or time.monotonic() >= deadline:
                raise
            time.sleep(2)
    write(output / 'snapshot.json', imported.model_dump(mode='json'))
    response = client.flow().id(FLOW).request('service/graph-rag', {
        'query': 'Which team owns the Atlas service?', 'collection': FLOW, 'entity-limit': 5, 'triple-limit': 15,
        'max-subgraph-size': 25, 'max-path-length': 1, 'edge-limit': 15, 'edge-score-limit': 15,
        'grounding-seeds': ['Atlas', 'Platform team']})
    write(output / 'retrieval.json', response)
    facts = [triple for chunk in imported.chunks for triple in chunk.extracted_triples]
    ownership = [triple for triple in facts if triple['predicate'] == 'https://example.org/demo#ownedBy']
    report = {'preparation_before_submission': True, 'configuration_version': prepared.configuration_version,
              'receipt_recovered_without_resubmission': recovered.processing_id == receipt.processing_id,
              'selected_snapshot_verified': True, 'upstream_global_completion': False,
              'chunks': len(imported.chunks), 'facts': len(facts), 'ownership_statements': ownership,
              'answer': response.get('response'), 'sources': response.get('sources', []),
              'known_answer_contains_platform': 'Platform' in response.get('response', ''),
              'simulation': 'Approved-version input is a synthetic adapter test fixture; no Studio approval written'}
    write(output / 'report.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
