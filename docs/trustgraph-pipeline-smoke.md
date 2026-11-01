# Synthetic TrustGraph pipeline verification

On 2026-11-01 the isolated `oe-portal-smoke` stack exercised real librarian storage, recursive chunking, ordinary and ontology-guided extraction, Cassandra triples, Ollama embeddings, Qdrant vectors, FlashRank, and GraphRAG retrieval. No study is approved and no confidential sources or expert observations were used. The invented packet is the 98-byte Atlas/Platform ownership text.

The final `v4` observations are recorded in `infra/portal/pipeline-evidence.json`; durable raw artifacts remain under `research/results/trustgraph-pipeline/run-20261101-v4/`. One exact source/chunk was verified per flow. Ordinary extraction produced four quoted statements; ontology-guided extraction produced eight. Both have source-graph subgraph→chunk→document lineage and query-time retrieval traces, with 46 and 50 rows respectively. The real optional Studio SDK adapter resolved one frozen exact child for each returned original-document URI. Its `review_eligible` stayed false with `corpus_completion_and_provenance_not_verified`.

This is integration evidence, not answer-equivalence evidence. Ordinary GraphRAG correctly answered **Platform team**. The ontology-guided answer returned the source citation but said ownership could not be determined. Its known-answer check therefore fails. Successful provenance reconciliation does not imply a correct answer, acceptable ontology semantics, or research benefit.

The first three attempts remain retained: original JSONL ontology output parsed zero content triples; a structured-output attempt exceeded the observation window and was stopped; a capped model used its output budget in reasoning and returned empty response text. These are not discarded observations. The final repair is a separately mounted, smoke-only provider extension in `infra/portal/bounded_ollama.py` and `bounded_ollama_client.py`: explicit `think=False`, 512 output tokens, 4,096 context tokens, 64 KiB prompt/response limits, 120-second total deadline, fixed model identity, and no model auto-pull. The official backend sources and image were not modified. Two meaningful wire/deadline tests exercise these bounds.

## Pins and boundaries

`infra/portal/pipeline-pins.json` pins the separate official **deployment configuration** repository `trustgraph-ai/trustgraph-templates` at `5c9853804b2c3aaa30db913cd8c0751b65a3d722`, archive SHA-256 `c23565987bb74adab379bea6b829e22c5c6837606937c9cf9224ff81e5ff9698`. This does not replace the frontend plugin-template pin. Official 2.11 flow modules are rendered with `gojsonnet==0.21.0`; only the enumerated processors/interfaces needed for the synthetic flow are selected. All added Docker services use digest pins and private ports. Only the existing loopback gateway is exposed.

The `all-minilm:latest` registry manifest is pinned to `1b226e2802dbb772b5fc32a58f103ca1804ef7501331012de126ab22f67475ef` (45,949,216-byte model layer, 384 dimensions). Registry content and installed blobs were hash checked. Ollama may wrap the local manifest with an additional layer containing the original manifest; the public model digest and that original layer remain the pinned identity. `oe-qwen3-smoke:1.7b` reuses the already pinned Qwen weights with capped parameters; its digest is `84c467420f6d51cae7ca58914d67196eaa658b26d90b8af6705b7192b3947002`. The base `qwen3:1.7b` configuration was unchanged.

The loaded FlashRank TinyBERT ONNX SHA-256 is `a2b09fb0de692c052a55f4165c9461377b4a31115673b7adb428503d69109196`; tokenizer SHA-256 is `ce64fce797c24f68df90b40a3f74f579b336a493db14bd583fd520ea0d8c9a98`. The observed pin records the actual image/runtime contents, not an assertion that the upstream model name is immutable.

Two actual SDK/gateway mismatches were fixed in the Studio adapter with failing-then-passing tests: SDK `get_document` emits unsupported `get-document` and expects a child timestamp that may be absent, while the gateway supports `get-document-metadata`; GraphRAG sources identify original documents, not chunks. The adapter now uses the supported fixed operation and resolves only children registered for that source/corpus. SDK `list_children` also receives HTTP 400 `unknown operation`; enumeration uses explicit `urn:graph:source` parent links, followed by supported metadata/content reads. See [source contracts](trustgraph-source-contract.md).

The finite reconciliation helper checks exact source and child bytes/hashes/parents, expected chunk count, graph scope/limits, required extraction stages, RDF-star statements linked to the child, returned source references and retrieval trace scope. It seals copied evidence. It does **not** claim global upstream completion, lock remote data, grant review authority, or activate the provider. The librarian still has no terminal processing status. The diagnostic adapter seed hash was observed after ingestion; an approved pre-ingestion seed/config binding and persistent job/corpus ledger remain required for Studio activation.

## Reproduce

First prepare the real local host stack using [portal-smoke.md](portal-smoke.md), and the pinned base model using the project model setup. The commands below affect only the synthetic smoke project and local model test configuration. Keep its generated `runtime/` credentials private.

```sh
UV_PROJECT_ENVIRONMENT=.venv-trustgraph uv sync --frozen --extra trustgraph
uv pip install --python .venv-trustgraph/bin/python gojsonnet==0.21.0
curl -fsSL https://codeload.github.com/trustgraph-ai/trustgraph-templates/tar.gz/5c9853804b2c3aaa30db913cd8c0751b65a3d722 -o infra/portal/upstream/trustgraph-templates-5c985380.tar.gz
# Verify archive SHA against pipeline-pins.json before extracting.
tar -xzf infra/portal/upstream/trustgraph-templates-5c985380.tar.gz -C infra/portal/upstream
.venv/bin/python infra/portal/prepare_pipeline_models.py
.venv-trustgraph/bin/python infra/portal/prepare_pipeline.py --nonthinking-provider
docker compose --env-file infra/portal/runtime/.env -f infra/portal/compose.yaml -f infra/portal/pipeline.compose.yaml up -d --no-deps garage qdrant
.venv-trustgraph/bin/python infra/portal/init_pipeline.py storage
docker compose --env-file infra/portal/runtime/.env -f infra/portal/compose.yaml -f infra/portal/pipeline.compose.yaml up -d --no-deps pipeline
.venv-trustgraph/bin/python infra/portal/init_pipeline.py flows --nonthinking-provider
.venv-trustgraph/bin/python infra/portal/check_pipeline.py ingest --nonthinking-provider --output research/results/trustgraph-pipeline/run-local
.venv-trustgraph/bin/python infra/portal/check_pipeline.py observe --nonthinking-provider --seconds 60 --output research/results/trustgraph-pipeline/run-local
.venv-trustgraph/bin/python infra/portal/check_pipeline.py retrieve --nonthinking-provider --output research/results/trustgraph-pipeline/run-local
PYTHONPATH=services/api/src .venv-trustgraph/bin/python infra/portal/check_pipeline.py reconcile --output research/results/trustgraph-pipeline/run-local
PYTHONPATH=services/api/src .venv-trustgraph/bin/python infra/portal/check_pipeline.py adapter --nonthinking-provider --output research/results/trustgraph-pipeline/run-local
```

The fixed synthetic document/processing IDs must be used on a fresh smoke workspace for a new ingestion. On the retained stack use observe/retrieve/reconcile rather than pretending a repeated submitted ID is a new run. Current tests: `23 passed, 1 skipped` across `test_trustgraph_gateway.py`, `test_trustgraph_reconciliation.py`, and `test_trustgraph_model_bounds.py`; the skipped generic live probe is separate from the actual live script evidence above. Ruff passed for the changed modules/scripts/tests. No broad suite result is asserted here.

Stop only the added services while retaining synthetic evidence and volumes:

```sh
docker compose --env-file infra/portal/runtime/.env -f infra/portal/compose.yaml -f infra/portal/pipeline.compose.yaml stop pipeline garage qdrant
```
