# Profile-bound TrustGraph extraction

The optional TrustGraph 2.11.1 worker extends `LlmService` and calls the same bounded LiteLLM helper as Studio. Text completion uses the configured provider; embeddings and reranking keep their existing processors. No website model picker is added.

## Private server and worker bindings

Keep the [existing server configuration and exact upstream configuration capture](trustgraph-import-contract.md#server-owned-configuration). Each profiled project row adds:

```json
{
  "extraction_profile_id": "go-glm",
  "extraction_profile_revision": "sha256:<complete frozen profile descriptor hash>",
  "llm_session_id": "synthetic-extraction-run-unique-id"
}
```

The row's `binding.flow` identifies its preconfigured flow. Its `expected_configuration` must capture that exact deployed flow, blueprint, resolved processor variants, all prompts and ontologies, and the correct digest. Model profiles remain in the private Studio registry described in [multi-llm.md](multi-llm.md). The selected upstream flow's `parameters` and every selected text-completion processor variant's `parameters` must include three exact markers: `oe-llm-profile-id`, `oe-llm-profile-revision`, and `oe-llm-session-id` (empty string for no session). Add corresponding placeholders to each text-completion entry in the blueprint, for example `"oe-llm-profile-revision": "{oe-llm-profile-revision}"`, then supply the literal values when starting the flow. The staging output `flow-markers.json` provides these literal flow parameters and blueprint parameter placeholders. Capture the resulting remote configuration after starting it. The gateway verifies these markers through its exact configuration/version guard, and the worker compares its actual flow parameter markers to its private frozen mapping before any SDK dispatch. A mismatched worker mapping therefore fails before provider traffic. Changing a profile requires an explicitly provisioned matching flow/binding revision. A project can retain one legacy unprofiled binding plus different profile bindings; duplicate project/profile/revision mappings and reused workspace/flow pairs are rejected. Legacy configuration with one unprofiled project binding continues to work without an LLM registry.

Create a separate private worker binding file, mode 0600:

```json
{
  "bindings": [{
    "workspace": "synthetic-workspace",
    "flow": "synthetic-go-glm-run-unique-id",
    "profile": {"<complete resolve_profile snapshot including revision>": "..."},
    "session_id": "synthetic-extraction-run-unique-id"
  }]
}
```

`profile` is the complete JSON-compatible snapshot returned by `oe_studio.llm_profiles.resolve_profile(settings, project_id, "extraction", profile_id)`, including every descriptor field and its revision. It contains an `api_key_env` reference, never the key value. Use the same exact snapshot ID/revision and session in server and worker bindings. The worker validates the snapshot revision at startup and holds the loaded mapping fixed until restart. Configure only credentials needed by this worker in its private environment.

For OpenCode Go, provision a distinct flow and explicit session for each extraction run. The first durable preparation reserves that session atomically; another new ingestion using it fails before submission. Recovery reuses the existing preparation and session. Neither a processor ID nor an individual prompt/message correlation ID is a run session. Worker mappings reject repeated Go sessions. Retain historical server bindings while recovery/list/import is needed.

## Prepare and build

First prepare the existing synthetic pipeline normally. Then stage the worker without starting containers or calling providers:

```sh
.venv/bin/python infra/portal/prepare_litellm.py \
  --bindings /absolute/private/worker-bindings.json \
  --pipeline infra/portal/runtime/pipeline.yaml \
  --output .runtime/multi-llm/worker \
  --smoke-directory .runtime/multi-llm
```

The command retains every original processor unchanged and adds dedicated `studio-<original-id>` completion processors. Existing unprofiled flows continue to use their original completion service. For each new profiled flow, copy its blueprint and rename only completion declaration IDs using `flow-markers.json`'s `completion_processor_mapping` (for example `text-completion:{id}` becomes `studio-text-completion:{id}`). Keep the declaration topics unchanged so the new processor serves that profiled flow's own request/response topics; add the profile/session marker parameter placeholders to the new declarations. Deploy only these dedicated profiled blueprints to the new flows. Never point legacy unprofiled flows at the new profile-only services. It leaves embeddings, graph embeddings, reranking and source/provenance processors unchanged. Inspect `pipeline.yaml`, `compose.yaml` and `pins.json` in the output directory. The generated `image/` contains only shared source modules and exact SDK dependency versions derived from `uv.lock`. Private bindings live outside the image build context. The pinned upstream worker uses Python 3.13; Studio uses Python 3.12. SDK versions match while binary wheels follow the interpreter ABI. There is no package installation at worker startup.

Build using the generated overlay alongside the existing base and pipeline compose files. Give Docker Compose a private environment file containing the required credential variable references and existing bus variables; avoid printing rendered environment values. The derived image tag is a hash of staged source/dependency pins. Record the resulting image digest after building if distributing the image. Staging alone does not deploy or start it.

For the bounded combined smoke, `--smoke-directory` mounts the entire host directory read/write at `/smoke-budget` and sets container budget/price paths to `smoke-budget.sqlite` and `verified-prices.json`. Studio must reference these same physical host files. SQLite journals and locking require the directory mount. The two processes share the [same attempt and full-price reservation ledger](multi-llm.md#shared-trustgraph-budget-and-preconfigured-flows). The option may be omitted for ordinary unmetered application operation; the authorized smoke always includes it.

## Frozen state and validation

Before enqueue, Studio authorizes the selected extraction profile and freezes its exact public server binding. Before submission it commits the original profile snapshot, session and public configuration with the existing prepared intention. Credentials are excluded. Recovery, registered chunk listing and selected imports reconstruct this recorded binding rather than using a new default. A changed or removed authorized historical binding fails closed; token rotation is permitted because tokens are resolved privately and excluded from binding identity. Existing exact upstream configuration/version, source/seed, processing and provenance checks remain in force.

The worker selects mappings from `flow.workspace` and `flow.name`; `flow.id` names the shared processor. A request-scoped context preserves the bus correlation ID and prevents concurrent flows from sharing a selected profile/session. Bus model and temperature parameters cannot override the frozen profile. Nonstreaming generation uses the shared timeout, response byte/output token limits, credential resolver, optional budget reservation and one-dispatch/no-retry behavior. Plain text remains plain text. A JSON request with no original schema is supported only by an explicitly configured `json_object` or `prompt_json` profile, and the resulting original generic object is validated without discarding its fields. A `json_schema` profile rejects such a request before HTTP because an unrestricted object cannot be truthfully represented by its strict object grammar; select a supported explicit profile mode rather than changing modes automatically. JSON arrays use an object envelope, validate that envelope, unwrap it, and validate the original array schema before returning the upstream wire response. Schemas admit local references only; array envelopes support references under `#/$defs/` or `#/definitions/` and reject root-dependent references such as `#` because wrapping changes their meaning.

Offline tests exercise the actual TrustGraph superclass and real LiteLLM SDK through a fake HTTP transport. Those tests establish wiring and validation behavior; they do not establish provider availability, extraction quality, embedding behavior or whole-pipeline completion. A queued TrustGraph response still does not prove upstream processing completion, and this integration does not approve or publish ontology artifacts.

## Narrow live probe

`infra/portal/check_profiled_extraction.py` operates only on an already provisioned disposable ordinary extraction flow. It requires the shared budget/price environment paths. Run with `PYTHONPATH=services/api/src .venv/bin/python`, the private `--server-config`, authorized `--project-id`, and a fresh `--output` directory. `--action prepare` also requires `--profile-snapshot` and freezes source registration plus preparation before submission. `--action submit` records its started intention before uploading/submitting; another submit reconciles the existing intention and never silently replays an uncertain submission. `--action chunks` lists verified registered chunk URIs. Inspect that output, then use `--action import --chunk-uri <explicit URI>` to freeze only that selection.

The fixed source is a short invented Atlas/Platform ownership statement. The probe makes no retrieval/RAG completion call and creates no approvals, publication, approved ontology fixture or main Studio state. Nested extraction completions still count against the same shared 20-attempt/USD 1 reservation cap, including failures. Use a currently verified free profile if the remaining full-price reservation cannot cover nested calls. A budget/schema/provider failure is a retained failed observation, never permission to retry with another model. Provisioning and submission are separate operator actions; staging and `--help` alone make no provider calls.
