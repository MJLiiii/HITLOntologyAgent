"""Live synthetic packet smoke. Submitted metadata never means completed.

Run phases explicitly; all durable output is synthetic and excludes auth tokens.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import asyncio
from uuid import NAMESPACE_URL, uuid5

from init_pipeline import BASE, api

TEXT = "Atlas is a service. The Platform team owns the Atlas service. Atlas is owned by the Platform team."
DOCS = {mode: "urn:oe:synthetic:" + mode + ":ownership-v1" for mode in ("oe-graph", "oe-ontology")}
CONFIG_NAME = "pipeline-config.json"


def sha(content):
    return hashlib.sha256(content).hexdigest()


def write(path, value):
    if path.exists():
        previous = path.read_bytes()
        history = path.with_name(path.stem + '.' + sha(previous)[:16] + path.suffix)
        if not history.exists():
            history.write_bytes(previous)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def triples(client, mode, graph=None):
    body = {"collection": mode, "limit": 2000}
    if graph:
        body["g"] = graph
    return client.flow().id(mode).request("service/triples", body)


def ingest(client, output):
    if (output / "submitted.json").exists():
        raise ValueError("This packet is already submitted; choose observe/retrieve")
    packet = {"schema_version": 1, "mode": "synthetic_engineering_smoke", "source": TEXT,
              "source_sha256": sha(TEXT.encode()), "expected_chunk_count_per_flow": 1,
              "byte_length": len(TEXT.encode()), "documents": DOCS,
              "flow_config_sha256": sha((BASE / CONFIG_NAME).read_bytes()),
              "pipeline_pins_sha256": sha((BASE / "pipeline-pins.json").read_bytes()),
              'provider_source_sha256': {name: sha((BASE / name).read_bytes()) for name in ('bounded_ollama.py', 'bounded_ollama_client.py')} if CONFIG_NAME.endswith('-v4.json') else None,
              "automatic_completion_supported": False, "real_study_approved": False}
    write(output / "frozen-packet.json", packet)
    (output / 'flow-config.json').write_bytes((BASE / CONFIG_NAME).read_bytes())
    (output / 'pipeline-pins.json').write_bytes((BASE / 'pipeline-pins.json').read_bytes())
    records = []
    for mode, doc_id in DOCS.items():
        client.library().add_document(TEXT.encode(), doc_id, [], "Synthetic Atlas ownership", "Engineering smoke; invented entities", tags=["synthetic"])
        processing = doc_id + ":processing"
        client.library().start_processing(processing, doc_id, flow=mode, collection=mode, tags=["synthetic"])
        records.append({"flow": mode, "collection": mode, "document_id": doc_id,
                        "processing_id": processing, "status": "submitted", "completion_supported": False})
    write(output / "submitted.json", records)
    print("Submitted two synthetic documents; downstream completion remains unknown.", flush=True)


def observe(client, output, seconds):
    deadline = time.monotonic() + seconds
    records = {}
    while True:
        for mode, doc_id in DOCS.items():
            source = client.library().get_document_content(doc_id)
            if source != TEXT.encode():
                raise ValueError("Stored source differs from frozen packet")
            raw_graph = triples(client, mode, "urn:graph:source")
            graph_rows = raw_graph.get("response", [])
            # list-children exists in SDK/service but is absent from the 2.11.1
            # gateway operation registry (HTTP400). Use actual source graph links.
            child_ids = sorted({r["s"]["i"] for r in graph_rows
                                if r.get("p", {}).get("i") == "http://www.w3.org/ns/prov#wasDerivedFrom"
                                and r.get("o", {}).get("i") == doc_id
                                and r.get("s", {}).get("i", "").startswith("urn:chunk:")})
            children = []
            for child_id in child_ids:
                child = client.library().request({"operation": "get-document-metadata", "workspace": "default", "document-id": child_id})
                content = client.library().get_document_content(child_id)
                # This bounded packet has one exact chunk; never trust upstream charOffset as a byte span.
                children.append({"metadata": child, "sha256": sha(content), "content": content.decode(),
                                 "exact_frozen_source_match": content == TEXT.encode()})
            contains = [row for row in graph_rows if row.get("p", {}).get("i", "").endswith("contains")]
            records[mode] = {"source_sha256": sha(source), "children": children, "source_graph": raw_graph,
                             "default_graph": triples(client, mode), "extracted_statement_count": len(contains),
                             "stored_chunk_verified": len(children) == 1 and all(c["exact_frozen_source_match"] for c in children),
                             "librarian_processing": client.library().request({"operation": "list-processing", "workspace": "default"}),
                             "completion_supported": False, "observed_at": datetime.now(timezone.utc).isoformat()}
        write(output / "observations.json", records)
        ready = all(r["stored_chunk_verified"] and r["extracted_statement_count"] > 0 for r in records.values())
        if ready or time.monotonic() >= deadline:
            print(json.dumps({"stored_chunk_and_extraction_observed": ready,
                              "flows": {k: {"chunks": len(v["children"]), "statements": v["extracted_statement_count"]} for k, v in records.items()},
                              "completion_supported": False}), flush=True)
            return
        time.sleep(2)


def retrieve(client, output):
    results = {}
    for mode in DOCS:
        started = time.monotonic()
        try:
            raw = client.flow().id(mode).request("service/graph-rag", {
                "query": "Which team owns the Atlas service?", "collection": mode,
                "entity-limit": 5, "triple-limit": 12, "max-subgraph-size": 20, "max-path-length": 1,
                "edge-limit": 12, "edge-score-limit": 12, "max-reranker-input": 40,
                "grounding-seeds": ["Atlas", "Platform team"]})
            results[mode] = {"status": "returned", "raw": raw, "retrieval_graph": triples(client, mode, "urn:graph:retrieval")}
        except Exception as exc:
            results[mode] = {"status": "failed", "exception_type": type(exc).__name__, "error": str(exc)}
        results[mode]["elapsed_seconds"] = time.monotonic() - started
        write(output / "retrieval.json", results)
        print(json.dumps({"flow": mode, "status": results[mode]["status"], "elapsed_seconds": results[mode]["elapsed_seconds"]}), flush=True)


def reconcile(output):
    from oe_studio.integrations.trustgraph.reconcile import reconcile_synthetic_snapshot
    packet = json.loads((output / 'frozen-packet.json').read_text())
    for filename, field in [('flow-config.json', 'flow_config_sha256'), ('pipeline-pins.json', 'pipeline_pins_sha256')]:
        if sha((output / filename).read_bytes()) != packet[field]:
            raise ValueError('Frozen configuration identity changed')
    result = reconcile_synthetic_snapshot(packet, json.loads((output / 'observations.json').read_text()),
                                          json.loads((output / 'retrieval.json').read_text()))
    write(output / 'reconciliation.json', result)
    print(json.dumps({'bounded_snapshot_verified': result['bounded_snapshot_verified'], 'issues': result['issues']}))


def adapter(client, output):
    from oe_studio.artifacts import ArtifactStore
    from oe_studio.integrations.trustgraph.contracts import Artifact, Binding, CorpusRegistration, DocumentRegistration, EvidenceRef, RetrievalRequest
    from oe_studio.integrations.trustgraph.gateway import PinnedTrustGraphGateway
    from trustgraph.api import ConfigKey
    observations = json.loads((output / 'observations.json').read_text())
    packet = json.loads((output / 'frozen-packet.json').read_text())
    store = ArtifactStore(output / 'adapter-artifacts')
    seed = client.config().get([ConfigKey(type='ontology', key='oe-synthetic-ownership')])[0].value
    seed_artifact = store.put(seed.encode(), 'application/json')
    seed_digest = sha(seed.encode())
    results = {}
    for mode, document in packet['documents'].items():
        project, source, corpus, evidence = [uuid5(NAMESPACE_URL, document + ':' + part) for part in ('project', 'source', 'corpus', 'evidence')]
        child = observations[mode]['children'][0]
        chunk = child['metadata']['document-metadata']['id']
        artifact = Artifact(**store.put(packet['source'].encode(), 'text/plain'))
        # This is a diagnostic binding to copied observations, not approved input
        # for a Studio corpus. Source/seed approval integration remains gated.
        binding = Binding(project_id=project, url='http://127.0.0.1:18888', workspace='default', flow=mode,
                          collection=mode, seed_digest=seed_digest, config_digest=packet['flow_config_sha256'],
                          token=client.token, timeout=60)
        doc = DocumentRegistration(project_id=project, source_id=source, upstream_document_id=document,
                                   artifact=artifact, source_uri=document, title='Synthetic ownership')
        ref = EvidenceRef(id=evidence, project_id=project, corpus_id=corpus, source_id=source,
                          upstream_chunk_uri=chunk, source_sha256=artifact.sha256, chunk_sha256=artifact.sha256,
                          byte_start=0, byte_end=len(packet['source'].encode()), quote=packet['source'], graph_uri='urn:graph:source')
        frozen = CorpusRegistration(project_id=project, corpus_id=corpus, evidence=(ref,), graph_uri='urn:graph:source', provenance_verified=False)
        gateway = PinnedTrustGraphGateway(artifacts=store, bindings=[binding], documents=[doc], corpora=[frozen])
        resolved = asyncio.run(gateway.resolve_evidence(ref))
        context = asyncio.run(gateway.retrieve(RetrievalRequest(project_id=project, corpus_id=corpus,
                               query='Which team owns the Atlas service?', base_ontology_digest=binding.seed_digest,
                               retrieval_config_digest=binding.config_digest, triple_limit=100)))
        results[mode] = {'resolved': resolved.model_dump(mode='json'), 'context': context.model_dump(mode='json'),
                         'seed_config_artifact': seed_artifact, 'seed_observed_after_ingestion': True,
                         'binding_purpose': 'Diagnostic frozen-observation adapter test; no approved seed/corpus binding'}
        write(output / 'adapter.json', results)
        print(json.dumps({'flow': mode, 'exact_evidence_resolved': resolved.resolved,
                          'context_evidence_count': len(context.evidence), 'review_eligible': context.review_eligible, 'reasons': context.reasons}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["ingest", "observe", "retrieve", "reconcile", "adapter"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--structured-ontology", action="store_true")
    parser.add_argument("--bounded-model", action="store_true")
    parser.add_argument("--nonthinking-provider", action="store_true")
    args = parser.parse_args()
    if args.nonthinking_provider:
        DOCS = {mode: 'urn:oe:synthetic:' + mode + ':ownership-v4' for mode in ('oe-graph-v4', 'oe-ontology-v4')}
        CONFIG_NAME = 'pipeline-config-v4.json'
    elif args.bounded_model:
        DOCS = {mode: "urn:oe:synthetic:" + mode + ":ownership-v3" for mode in ("oe-graph-v3", "oe-ontology-v3")}
        CONFIG_NAME = "pipeline-config-v3.json"
    elif args.structured_ontology:
        DOCS = {mode: "urn:oe:synthetic:" + mode + ":ownership-v2" for mode in ("oe-graph-v2", "oe-ontology-v2")}
        CONFIG_NAME = "pipeline-config-v2.json"
    if not 0 <= args.seconds <= 180:
        parser.error("Observation budget must be between 0 and 180 seconds")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase == 'reconcile':
        reconcile(args.output)
    else:
        client = api()
        if args.phase == "observe":
            observe(client, args.output, args.seconds)
        else:
            {"ingest": ingest, "retrieve": retrieve, 'adapter': adapter}[args.phase](client, args.output)
