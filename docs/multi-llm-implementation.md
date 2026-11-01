# Multi-LLM implementation ledger

Approved plan: LiteLLM SDK shared by Studio and TrustGraph; project-authorized server-owned profiles selected by API, immutable queued-job configuration, legacy Ollama/demo compatibility, no website picker. OpenAI/Claude/Ollama/compatible gateways/LiteLLM proxy/OpenCode Go. TrustGraph uses bounded LlmService extension and separate preconfigured flows, frozen original bindings, original array schema validation and existing drift guards. Embeddings/reranker unchanged.

Live test authorization: synthetic disposable data only, at most 20 outbound completion attempts including failures, maximum 4096 output tokens/call, conservative total full-price reservation at most USD 1. No retries, paid-provider fallback, account setting changes or automatic approval/publication. OPENCODE_API_KEY must be configured privately. Initially glm-5.3-flash/kimi-k2.7-code; optional advertised free models after current price/availability verification. Missing credential currently prevents live calls; continue all implementation/offline verification.

## Shared interfaces

- `oe_studio.llm_profiles.resolve_profile(settings, project_id, operation, profile_id=None)` returns a frozen JSON-compatible snapshot or None for unconfigured legacy demo. Operations: chat, proposal, repair, experiment, extraction. Registry profiles are project-allowlisted; explicit unknown/forbidden IDs fail before enqueue.
- Snapshot keys: `id`, `revision`, `provider`, `model`, `base_url`, `api_key_env` (reference only), `purposes`, `timeout`, `max_output_tokens`, `temperature` (nullable), `structured_output` (`json_schema`, `json_object`, `prompt_json`), `max_response_bytes`. Revision hashes complete non-secret descriptor. No credential value is stored.
- `oe_studio.llm_profiles.profile_settings(settings, snapshot, session_id=None)` returns a settings-compatible object carrying `resolved_llm_profile` and `llm_session_id`; preserves other settings. Root owns registry/settings/workflow/API/schema integration.
- `oe_studio.llm_profiles.secret_value(settings, env_name)` resolves process environment then project `.env` without printing values. Legacy Ollama may read settings.model_api_key directly; never persist it.
- Shared async SDK helper owned by transport implementer: `oe_studio.llm_runtime.complete(settings, system, context, output_schema, *, transport=None)` returns `(text, metadata)`. Uses resolved profile; ModelClient keeps generate(system,context,schema), validates original Pydantic schema and wraps errors as ModelGenerationError. Agree any changes with root/TG implementer before editing another owner's files.
- SDK helper invokes optional `oe_studio.llm_budget.reserve_from_settings(settings, profile, payload)` immediately before each HTTP completion dispatch. Budget helper owner defines optional runtime settings/price artifact format and communicates it; no configured budget means normal unmetered application operation, smoke always configures budget.
- TG extension supplies profile_settings and same helper; JSON array envelopes validate then unwrap and validate original schema. Registry/keys remain private. Main, worker packaging use the same pinned dependency lock.

## Progress

- Baseline: a4892ee; existing 405 backend / 59 UI verification recorded in prior release. Original ONTOCHECK_REVIEW.md remains untouched.
- Ruling: work in the user's existing folder on codex/multi-llm, preserving their earlier in-place preference. Parallel tasks own distinct files and agree interfaces; root performs integration and final independent review.
- Increment 1: profile registry, validated immutable revisions, permission catalog/configuration examples — committed as `9a2f286`.
- Increment 2: bounded shared SDK, Studio/API workflows, experiments, conversation IDs, dispatch budget and protocol tests — committed as `66b86f2`.
- Increment 3: dedicated TrustGraph worker processors, frozen bindings, array validation, recovery/import safeguards and pinned image — committed as `4e01908`.
- Increment 4: bounded real-workflow comparison runner, configuration/API examples, comparison report and verification evidence — complete, recorded in the documentation commit containing this ledger.
- Final verification: 528 backend tests passed / 7 existing skips; 60 frontend tests, TypeScript, both builds, Ruff, API contracts and diff checks passed. Three real loopback protocol endpoints and the actual local Ollama model passed. Final pinned TrustGraph image passed a network-disabled real-stack smoke with fake HTTP.
- Independent reviews found and resolved endpoint override, credential echo, strict schema, profile numeric normalization, dedicated legacy-compatible processors, generic JSON and remote flow-marker issues. All source owners completed their work before the final backend run.
- Running local Studio now serves the new sanitized profile catalog; Ollama stays configured. Main workspace remains unapproved. Original ONTOCHECK_REVIEW.md is untouched.
- Remaining live evidence: OPENCODE_API_KEY is still absent. Four comparison observations are credential-blocked; zero completion attempts and USD 0 reserved. User intends to configure the key locally in the ignored .env placeholder. No hosted model quality or live Go TrustGraph extraction/import result is claimed. See multi-llm-verification.md and model-comparison.md.
