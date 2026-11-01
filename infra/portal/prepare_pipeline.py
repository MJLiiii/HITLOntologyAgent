"""Prepare only synthetic pipeline configuration; does not start containers.

Requires gojsonnet==0.21.0 in the isolated .venv-trustgraph environment.
Upstream sources are read unchanged; filtered flow processors are explicit below.
"""
from __future__ import annotations

import hashlib
import argparse
import json
from pathlib import Path
import secrets

import _gojsonnet
import yaml

BASE = Path(__file__).resolve().parent
COMMIT = "5c9853804b2c3aaa30db913cd8c0751b65a3d722"
ARCHIVE_SHA = "c23565987bb74adab379bea6b829e22c5c6837606937c9cf9224ff81e5ff9698"
TEMPLATES = BASE / "upstream" / f"trustgraph-templates-{COMMIT}" / "trustgraph_configurator/templates/2.11"
FLOW_IMAGE = "trustgraph/trustgraph-flow@sha256:29ab8fbb59fcb05318dc9208d946d4a1b2b74e6863099b9f752fc72ffc52bc0e"
QDRANT_IMAGE = "qdrant/qdrant@sha256:f1c7272cdac52b38c1a0e89313922d940ba50afd90d593a1605dbbc214e66ffb"
GARAGE_IMAGE = "dxflrs/garage@sha256:866bd13ed2038ba7e7190e840482bc27234c4afaf77be8cfa439ae088c1e4690"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--structured-ontology", action="store_true")
    parser.add_argument("--bounded-model", action="store_true")
    parser.add_argument("--nonthinking-provider", action="store_true")
    args = parser.parse_args()
    archive = BASE / "upstream/trustgraph-templates-5c985380.tar.gz"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("Deployment template archive digest changed")
    runtime = BASE / "runtime"
    credential_path = runtime / "pipeline-secrets.json"
    if not credential_path.exists():
        credential_path.write_text(json.dumps({
            "access_key": "GK" + secrets.token_hex(12),
            "secret_key": secrets.token_hex(32),
            "rpc_secret": secrets.token_hex(32),
            "admin_token": secrets.token_urlsafe(32),
        }))
        credential_path.chmod(0o600)
    private = json.loads(credential_path.read_text())
    garage = f'''metadata_dir = "/var/lib/garage/meta"
data_dir = "/var/lib/garage/data"
db_engine = "lmdb"
replication_factor = 1
rpc_bind_addr = "[::]:3901"
rpc_public_addr = "garage:3901"
rpc_secret = "{private['rpc_secret']}"
[s3_api]
s3_region = "garage"
api_bind_addr = "[::]:3900"
root_domain = ".s3.garage.local"
[admin]
api_bind_addr = "[::]:3903"
admin_token = "{private['admin_token']}"
'''
    (runtime / "garage.toml").write_text(garage)
    (runtime / "garage.toml").chmod(0o600)
    common = {"pubsub_backend": "rabbitmq", "rabbitmq_host": "rabbitmq",
              "cassandra_host": "cassandra", "cassandra_replication_factor": 1,
              "log_level": "INFO"}
    processors = []

    def proc(identifier, module, **params):
        processors.append({"class": "trustgraph." + module + ".Processor",
                           "params": common | {"id": identifier} | params})

    proc("librarian", "librarian", object_store_endpoint="garage:3900",
         object_store_access_key=private["access_key"], object_store_secret_key=private["secret_key"],
         object_store_region="garage", object_store_use_ssl=False)
    proc("chunker", "chunking.recursive", chunk_size=2000, chunk_overlap=0)
    proc("kg-extract-definitions", "extract.kg.definitions")
    proc("kg-extract-relationships", "extract.kg.relationships")
    proc("kg-extract-ontology", "extract.kg.ontology")
    for ident in ("prompt", "prompt-rag"):
        proc(ident, "prompt.template")
    for ident in ("text-completion", "text-completion-rag"):
        proc(ident, "model.text_completion.ollama", ollama="http://host.docker.internal:11434",
             model="qwen3:1.7b", temperature=0)
    proc("embeddings", "embeddings.ollama", ollama="http://host.docker.internal:11434", model="all-minilm:latest")
    proc("graph-embeddings", "embeddings.graph_embeddings")
    proc("triples-query", "query.triples.cassandra")
    proc("triples-write", "storage.triples.cassandra")
    proc("triples-policy", "policy.triples.service")
    proc("graph-embeddings-query", "query.graph_embeddings.qdrant", store_uri="http://qdrant:6333")
    proc("graph-embeddings-write", "storage.graph_embeddings.qdrant", store_uri="http://qdrant:6333")
    proc("reranker", "reranker.flashrank", model="ms-marco-TinyBERT-L-2-v2")
    proc("graph-rag", "retrieval.graph_rag", entity_limit=5, triple_limit=12, max_path_length=1,
         max_subgraph_size=20, edge_limit=12)
    if args.nonthinking_provider:
        for identifier in ('bounded-text-completion', 'bounded-text-completion-rag'):
            processors.append({'class': 'bounded_ollama.Processor', 'params': common | {
                'id': identifier, 'model': 'oe-qwen3-smoke:1.7b', 'ollama': 'http://host.docker.internal:11434'}})
    (runtime / "pipeline.yaml").write_text(yaml.safe_dump({"processors": processors}, sort_keys=False))
    (runtime / "pipeline.yaml").chmod(0o600)
    selected = {p["params"]["id"] for p in processors}
    definitions = json.loads(_gojsonnet.evaluate_file(str(TEMPLATES / "flows/flow-blueprints.jsonnet")))
    flows = {}
    for mode, original in (("oe-graph", "everything"), ("oe-ontology", "ontology")):
        if args.nonthinking_provider:
            mode += '-v4'
        elif args.bounded_model:
            mode += "-v3"
        elif args.structured_ontology:
            mode += "-v2"
        source = definitions[original]
        flows[mode] = source | {
            "flow": {k: v for k, v in source["flow"].items() if k.split(":")[0] in selected},
            "interfaces": {k: v for k, v in source["interfaces"].items()
                           if k in {"text-load", "triples", "triples-store", "graph-rag", "graph-embeddings", "embeddings", "prompt"}},
            "blueprint": {},
            "description": "Bounded synthetic Ontology Studio smoke: " + mode,
        }
        if args.nonthinking_provider:
            flows[mode]['flow'] = {(('bounded-' + k) if k.split(':')[0] in ('text-completion', 'text-completion-rag') else k): v
                                   for k, v in flows[mode]['flow'].items()}
    prompt_file = str(TEMPLATES / "prompts/default-prompts.jsonnet")
    snippet = 'local p = import ' + json.dumps(prompt_file) + '; {system: p["system-template"], templates: {[k]: p.templates[k] for k in std.objectFieldsAll(p.templates)}}'
    prompts = json.loads(_gojsonnet.evaluate_snippet("pipeline-prompts", snippet))
    if args.structured_ontology or args.bounded_model or args.nonthinking_provider:
        prompt = prompts["templates"]["extract-with-ontologies"]
        item_schema = prompt.pop("object-schema")
        for branch in item_schema["oneOf"]:
            branch["additionalProperties"] = False
        prompt["response-type"] = "json"
        prompt["schema"] = {"type": "array", "items": item_schema}
        prompt["prompt"] = prompt["prompt"].split("## Output Format")[0] + (
            "\nOutput a JSON array of entity, relationship, or attribute objects matching the supplied JSON schema. "
            "Use only exact entity types and property identifiers from the supplied ontology. "
            "Include only facts supported by the source text. Return [] if no facts are supported. /no_think\n")
    config_name = 'pipeline-config-v4.json' if args.nonthinking_provider else ("pipeline-config-v3.json" if args.bounded_model else ("pipeline-config-v2.json" if args.structured_ontology else "pipeline-config.json"))
    (BASE / config_name).write_text(json.dumps({"blueprints": flows, "prompts": prompts}, indent=2) + "\n")
    env = {"PUBSUB_BACKEND": "rabbitmq", "RABBITMQ_HOST": "rabbitmq", "RABBITMQ_USERNAME": "oe_portal",
           "RABBITMQ_PASSWORD": "${OE_PORTAL_BUS_PASSWORD}", 'PYTHONPATH': '/smoke'}
    overlay = {"services": {
        "garage": {"image": GARAGE_IMAGE, "command": ["/garage", "-c", "/etc/garage.toml", "server"],
                   "volumes": ["./runtime/garage.toml:/etc/garage.toml:ro", "pipeline_garage_meta:/var/lib/garage/meta", "pipeline_garage_data:/var/lib/garage/data"], "mem_limit": "256m"},
        "qdrant": {"image": QDRANT_IMAGE, "volumes": ["pipeline_qdrant:/qdrant/storage"], "mem_limit": "512m"},
        "pipeline": {"image": FLOW_IMAGE, "command": ["processor-group", "-c", "/smoke/pipeline.yaml"],
                     "environment": env, "volumes": ["./runtime/pipeline.yaml:/smoke/pipeline.yaml:ro", "pipeline_reranker:/app/.cache",
                                                       './bounded_ollama.py:/smoke/bounded_ollama.py:ro', './bounded_ollama_client.py:/smoke/bounded_ollama_client.py:ro'],
                     "mem_limit": "2g", "depends_on": ["garage", "qdrant", "control"]},
    }, "volumes": {k: {} for k in ["pipeline_garage_meta", "pipeline_garage_data", "pipeline_qdrant", "pipeline_reranker"]}}
    (BASE / "pipeline.compose.yaml").write_text(yaml.safe_dump(overlay, sort_keys=False))
    (BASE / "pipeline-pins.json").write_text(json.dumps({
        "deployment_template_repository": "https://github.com/trustgraph-ai/trustgraph-templates", "commit": COMMIT,
        "archive_sha256": ARCHIVE_SHA, "engine": "gojsonnet==0.21.0", "images": [FLOW_IMAGE, QDRANT_IMAGE, GARAGE_IMAGE],
        "embedding_model": "all-minilm:latest", "embedding_manifest_sha256": "1b226e2802dbb772b5fc32a58f103ca1804ef7501331012de126ab22f67475ef",
        "bounded_generation_model": {"name": "oe-qwen3-smoke:1.7b", "from": "qwen3:1.7b", "num_predict": 512,
                                     "num_ctx": 4096, "temperature": 0, "digest": "84c467420f6d51cae7ca58914d67196eaa658b26d90b8af6705b7192b3947002"},
        "scope": "Synthetic engineering smoke; no study approved; completion is not supplied by librarian"
    }, indent=2) + "\n")
    print("Prepared synthetic pipeline configuration; private credentials remain in runtime/.")


if __name__ == "__main__":
    main()
