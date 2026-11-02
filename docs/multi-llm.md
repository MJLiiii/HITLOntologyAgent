# OpenAI and Claude model configuration

Studio and the optional TrustGraph extraction worker support two model APIs: OpenAI (`openai`) and Claude (`anthropic`). Both use the same bounded HTTPX runtime. Operators own profiles and credentials; clients select only a project-authorized profile ID. With no configured registry, Studio uses the labelled deterministic demonstration. A configured-model failure never falls back to demo output. Readiness checks inspect configuration without making model calls.

## Configure the two APIs

Copy [the profile example](../config/llm-profiles.example.json) to a private operator-owned file. Replace both model placeholders with exact model IDs available to your account, and replace `REPLACE_WITH_PROJECT_ID` with the actual Studio project ID. Retain only profiles you intend to authorize. Set:

```sh
OE_LLM_CONFIG_FILE=/absolute/private/path/llm-profiles.json
OE_LLM_DEFAULT_PROFILE=openai-chat
```

Use `claude-chat` as the default to select Claude. Set `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY` privately in the process environment or project `.env`; never overwrite an existing `.env` with the example. The runtime checks process environment first, then the configured dotenv file. The checked example contains credential environment references, never keys.

| Provider | Default API base | Credential reference | Request |
| --- | --- | --- | --- |
| `openai` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | `/chat/completions` |
| `anthropic` (Claude) | `https://api.anthropic.com` | `ANTHROPIC_API_KEY` | `/v1/messages` |

An operator may override `base_url` for controlled endpoint tests and `api_key_env` for a private credential name. URLs cannot embed credentials, query parameters or fragments. Never put keys in browser bundles, tracked JSON, command arguments, queued jobs or reports.

## Profile contract

The registry has `profiles` and `projects` keys. `projects` maps project IDs to allowed profile IDs. Profiles define `id`, `provider`, exact provider `model`, `base_url`, `api_key_env`, `purposes`, `timeout`, `max_output_tokens`, nullable `temperature`, `structured_output`, and `max_response_bytes`. Supported operations are `chat`, `proposal`, `repair`, `test_generation`, `experiment` and `extraction`.

Both APIs support `json_schema` and `prompt_json`; OpenAI also supports `json_object`. Claude's native structured output uses `output_config.format`, without tool definitions. Native schema support depends on the selected model and the provider's supported JSON Schema subset. The example uses `prompt_json` for Claude so the application's full constrained schema stays in the prompt and is validated locally. Choose native schema mode explicitly only for a compatible model/schema. There is no automatic mode switch or second request. See [Claude structured-output documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

`temperature: null` omits that parameter, useful for models that do not support it. OpenAI sends `max_completion_tokens`; Claude sends `max_tokens`. The output ceiling is at most 4,096 tokens, the total deadline at most 120 seconds, and request/decoded response size at most 1 MiB (profiles can set smaller response limits). HTTP redirects, retries, streaming and model tools are disabled. Refusals, incomplete responses, malformed output, missing credentials and unsupported settings are explicit failures. Provider token counts remain unknown when absent; the runtime does not invent costs or usage.

The project API exposes permitted profiles through `GET /api/v1/projects/{id}/model-profiles`. Generation requests select an ID, for example:

```json
{"question":"Who owns Payroll Service?","model_profile_id":"openai-chat"}
```

Unknown, unauthorized or unconfigured selections fail before enqueue. A job retains its resolved non-secret descriptor and revision hash. Registry edits cannot silently replace its model, endpoint, output mode or bounds. Repair inherits the original descriptor and rechecks current authorization; queued work checks authorization before execution and result commit. Deterministic demo jobs remain frozen as demo. Historical model proposals without a frozen descriptor require an explicit permitted profile for repair. A snapshot naming a removed provider fails closed even if its ID is reused in the registry.

## Migration and preserved history

Ollama generation, OpenCode Go, generic compatible/proxy providers and LiteLLM dispatch have been removed from the active model layer. Legacy `OE_MODEL_URL`, `OE_MODEL_NAME`, `OE_MODEL_API_KEY` and `OE_MODEL_TIMEOUT` settings no longer configure generation; migrate to the private profile registry above. Old registries containing removed providers are rejected. Existing private files are preserved for the operator to migrate. Historical records and approved artifacts are not rewritten, and old queued work is never silently remapped to a different model.

Embeddings and reranking are separate integrations. The retired pinned TrustGraph host investigations and their evidence remain documented in [the portal guide](../infra/portal/README.md). Earlier provider observations in [multi-LLM verification](multi-llm-verification.md) and [model comparison](model-comparison.md) are historical, not current provider support or proof of OpenAI/Claude live compatibility.

## Optional bounded synthetic probes

Routine verification uses controlled transports and loopback endpoints. OpenAI/Claude paid calls require separate authorization; the historical OpenCode comparison authorization does not cover them. The comparison script requires explicit `--profiles`, a project-authorized registry, and a current revision-bound price artifact. It creates a disposable synthetic Studio and records chat/proposal outcomes without human decisions or publication.

The optional shared reservation helper retains hard ceilings of 20 total attempts, 4,096 output tokens per call and USD 1 conservatively reserved at full price. Both `OE_LLM_SMOKE_BUDGET_FILE` and `OE_LLM_SMOKE_PRICE_FILE` must be supplied, or neither. Partial configuration fails before dispatch. Reservations are append-only, include failures, and are never released after errors or crashes. Preserve existing ledgers; do not reset the historical allowance.

The price artifact has `verified_at`, `valid_until` (at most 24 hours later), and `profiles`. Each entry binds `id`, `revision`, `provider`, `model`, `base_url`, nonnegative `input_usd_per_million` and `output_usd_per_million` strings, an official HTTPS `source`, and `input_bound` with `method: "accepted_context_limit"`, exact `tokens`, and an official HTTPS `source`. Reservation covers that entire accepted input ceiling plus the configured output ceiling. Stale, missing or mismatched pricing blocks dispatch.

For combined Studio/TrustGraph probes, all callers must mount the same physical SQLite budget and price files, including the parent directory for journal files. The [TrustGraph worker guide](trustgraph-multi-llm.md) describes staging and frozen flow bindings. Staging and `--help` do not generate model calls. Successful text generation alone does not establish extraction quality, embedding behavior or whole-pipeline completion.
