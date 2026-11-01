# Server-owned model profiles

Studio and the optional TrustGraph extraction worker use the same pinned LiteLLM SDK runtime. Operators configure profiles; clients select only a project-authorized profile ID. The website retains its existing workflow. Empty legacy settings continue to use the deterministic demonstration, and the existing Ollama configuration remains supported. Embeddings and reranking are unchanged.

Copy `config/llm-profiles.example.json` to a private operator-owned file. Replace `REPLACE_WITH_PROJECT_ID` with the actual Studio project ID, retain only intended profiles, and set:

```sh
OE_LLM_CONFIG_FILE=/absolute/private/path/llm-profiles.json
OE_LLM_DEFAULT_PROFILE=go-glm-flash
```

Set `OPENCODE_API_KEY` privately in the process environment or project `.env`. The same approach supports `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and an operator-chosen environment name. Profiles contain environment variable references, never credential values. The runtime reads process environment before the project dotenv file. Do not configure keys in browser bundles, checked-in JSON, command arguments, exported reports or queued job payloads.

The registry has `profiles` and `projects` keys. `projects` maps a project ID to allowed profile IDs. A profile defines `id`, `provider`, exact provider `model`, `base_url`, `api_key_env`, `purposes`, `timeout`, `max_output_tokens`, nullable `temperature`, `structured_output`, and `max_response_bytes`. Supported providers are `openai`, `anthropic`, `ollama`, `openai_compatible`, `litellm_proxy` and `opencode_go`. Supported operations are `chat`, `proposal`, `repair`, `experiment` and `extraction`. Structured output can use `json_schema`, `json_object` or `prompt_json`; every mode validates the original application schema after generation. No failed mode falls back to another paid request.

The project API exposes its permitted profiles and accepts `model_profile_id` on supported generation requests. Unknown, unauthorized or unconfigured selections fail before a job is queued. A queued job retains the full resolved non-secret descriptor and its revision hash; later registry edits cannot silently replace that job's model, endpoint, structured-output mode or output limit. Repair inherits the original descriptor and rechecks current authorization. For historical model-generated proposals that predate frozen profiles, repair requires an explicit permitted `model_profile_id`; the server cannot reconstruct the original endpoint safely. A deterministic demo proposal continues to use demo repair unless a profile is explicitly selected.

## OpenCode Go

The checked example uses `https://opencode.ai/inference/go/openai/v1` with bare model IDs `glm-5.3-flash` and `kimi-k2.7-code`. The runtime supplies an application user agent and stable `x-opencode-session` header. Kimi's example omits temperature because current model metadata reports it unsupported. Optional Beam and Iceman profiles are explicitly selected; they are never automatic fallbacks. Current free availability is temporary and may be region-restricted. The documented Go service is intended for coding-agent traffic; synthetic ontology engineering here produces code/structured ontology changes, and this is a narrow functional smoke, not general account validation. [Official Go documentation](https://opencode.ai/v2/docs/console/go/), [official current model metadata](https://opencode.ai/inference/go/v1/models).

Observed on 1 November 2026, the official Go model endpoint reported full-price USD per million input/output tokens of 0.15/0.50 for GLM-5.3-Flash and 0.95/4.00 for Kimi K2.7 Code. It reported accepted context limits of 1,000,000 and 262,144 tokens respectively. These are configuration evidence, not successful generation results. The evidence copy and exact revision-bound price artifact live under `.runtime/multi-llm/` and expire within 24 hours. Go allowance consumption is not a USD charge; the smoke reservation deliberately ignores included allowance and cache discounts. [Official rates and endpoints](https://opencode.ai/v2/docs/console/go/), [official context and capability metadata](https://opencode.ai/inference/go/v1/models).

## Bounded synthetic comparison

Run only against synthetic disposable data with a privately configured key:

```sh
PYTHONPATH=services/api/src .venv/bin/python scripts/check_llm_profiles.py \
  --profile-config config/llm-profiles.example.json \
  --project-id synthetic-smoke \
  --profiles go-glm-flash go-kimi-code
```

The runner compares the same staged synthetic chat and proposal fixtures across both profiles, records failures and blocked observations, and writes `.runtime/multi-llm/smoke-report.md`. A missing key produces blocked rows and zero dispatches. Schema validity, citation validity and a narrow known-answer sentinel are reported independently of provider usage. They do not establish model quality or engine validity. No human decision or publication is created. A nonzero exit code means at least one observation failed or was blocked.

Every actual outbound HTTP completion dispatch, including failed or ambiguous attempts, first atomically reserves one attempt and an upper-bound full-price cost in a shared append-only SQLite ledger. Hard ceilings are **20 attempts total**, **4096 output tokens per call**, and **USD 1 total**. The SDK and transport do not retry or fall back. No reservation is released after an error, timeout or crash. Re-running the runner uses the same ledger; never delete or replace it to evade the authorized ceiling.

The cost basis is an operator-reviewed JSON artifact with `verified_at`, `valid_until` (at most 24 hours after verification) and `profiles`. Each entry binds the exact profile ID, revision, provider, model and base URL to nonnegative `input_usd_per_million` and `output_usd_per_million` strings, an official HTTPS `source`, and `input_bound` containing `method: "accepted_context_limit"`, the official `tokens` context ceiling, and its HTTPS `source`. The budget reserves that **entire context ceiling**, including all tokenizer/envelope overhead, plus the configured output ceiling. It makes no byte/token heuristic assumption. If the exact accepted-input bound or price cannot be verified, dispatch fails closed. Cached-input discounts and included allowance are ignored. Four primary comparison calls reserve at most USD 0.834937600 with the verified 1 November descriptor/rates. Changed profiles require new exact revision-bound price entries.

Refresh the artifact from the official metadata before its validity expires; do not extend timestamps without rechecking the exact models, endpoint, accepted context limits and full-price rates. Public metadata reads are not completion attempts. The `.runtime` evidence files contain no key. The helper does not meter ordinary application operation when neither smoke path is set; partial smoke configuration is an error.

## Shared TrustGraph budget and preconfigured flows

When performing a combined Studio/TrustGraph smoke, stop ordinary generation workloads and supply both settings to every caller:

```sh
OE_LLM_SMOKE_BUDGET_FILE=/absolute/host/path/.runtime/multi-llm/smoke-budget.sqlite
OE_LLM_SMOKE_PRICE_FILE=/absolute/host/path/.runtime/multi-llm/verified-prices.json
```

Bind mount their parent directory into the extraction container, for example host `.runtime/multi-llm` to `/smoke`, and set the container paths to `/smoke/smoke-budget.sqlite` and `/smoke/verified-prices.json`. These must reference the **same physical files**, with SQLite locks supported on the local filesystem. A similarly named file inside a container or copied ledger does not share the allowance. Mount the whole directory because SQLite may create journal files. Keep the private registry and credential environment available to the worker separately. Never run unmetered completion services during the authorized combined smoke.

TrustGraph uses separate operator-preconfigured flows for profile selection, leaving the original flow bindings frozen. See the exact [worker staging and flow configuration](trustgraph-multi-llm.md); its staging command mounts the shared directory at `/smoke-budget` and sets the container paths automatically. Configure extraction profiles explicitly in the worker registry/flow configuration described in the TrustGraph extension documentation. Both the main application and extraction worker call the same runtime dispatch/budget helper. Workers validate the original array schema after unwrapping any provider-required JSON object envelope; existing workspace and configuration-drift guards still apply. A successful text-model call does not establish that a TrustGraph flow, embedding service or whole-corpus answer succeeded.

## Other providers and API requests

`config/llm-profiles.providers.example.json` supplies editable OpenAI, Anthropic, local Ollama, compatible gateway and LiteLLM proxy descriptors. Replace every model placeholder with an installed or provider-supported exact ID. Gateway URLs and environment variable references are operator-owned. The runtime sends provider-native requests through LiteLLM; Ollama still receives `/api/chat`. Use the least demanding structured-output mode your endpoint supports; `prompt_json` still validates the original schema. A profile's availability status describes configuration, not a successful provider call.

With your existing local authenticated session cookie, list permitted profiles:

```http
GET /api/v1/projects/PROJECT_ID/model-profiles
```

Select a configured profile in the existing job requests (use actual project/base/corpus IDs):

```http
POST /api/v1/projects/PROJECT_ID/question-jobs
Content-Type: application/json
Idempotency-Key: synthetic-chat-unique-id

{"question":"Who owns Payroll Service?","model_profile_id":"go-glm-flash"}
```

```http
POST /api/v1/projects/PROJECT_ID/proposal-jobs
Content-Type: application/json
Idempotency-Key: synthetic-proposal-unique-id

{"instruction":"Add only the ownership relation supported by the synthetic source.","base_version_id":null,"model_profile_id":"go-kimi-code"}
```

Use the returned job/result IDs through the normal workflow. These requests create no review or publication. Do not place credentials in either payload. The examples do not authorize additional paid calls beyond the shared smoke ceiling.

The 4096-token cap covers generated reasoning as well as the visible answer. Kimi explicitly documents that `reasoning_content` plus `content` cannot exceed `max_tokens`. GLM documents `max_tokens` as the maximum tokens generated in one call; interpreting that as the total generation cap is consistent with OpenCode's definition of billed output including reasoning. This GLM conclusion is an inference from those two official API definitions. No separate reasoning budget or tool calls are enabled. A truncated reasoning-only response remains a failed observation; the runner does not increase its cap or retry. [Kimi thinking-token limit](https://platform.kimi.ai/docs/guide/use-thinking-models#read-reasoning-content-from-the-response), [GLM token parameter](https://docs.z.ai/guides/overview/concept-param#max-tokens), [Go inference billing fields](https://opencode.ai/v2/docs/console/api/inference/).
