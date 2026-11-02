# OpenAI and Claude API cleanup

**Goal:** Support only OpenAI (`openai`) and Claude (`anthropic`) for model generation and remove obsolete provider paths.

**Design:** Keep the existing server-owned profile registry and immutable snapshots. Replace the broad LiteLLM adapter with two native HTTP request/response mappings over the existing bounded HTTPX transport. Keep the pinned OpenAI schema converter, local output validation, credential isolation, optional shared budget, and no-retry policy. No registry means the labelled demo; invalid or removed profiles fail explicitly. Historical records, private configuration, approved state, and embedding services are preserved.

**Approach:** Narrowing LiteLLM would retain unnecessary adapters and dependencies. Direct API mappings remove that layer while preserving the application contract; this is the implementation choice for the requested cleanup. No new product workflow or paid call is needed.

## Tasks

- [x] Add regression checks for unsupported provider rejection (including frozen jobs), two native wire formats, and failed/unsafe responses. Run the new checks before implementation.
- [x] Restrict profiles, remove legacy model settings and provider branches, replace LiteLLM dispatch, and migrate controlled test fixtures to authorized OpenAI/Claude profiles.
- [x] Update TrustGraph worker packaging, smoke tooling, dependencies, examples, and current documentation. Preserve dated evidence and private files.
- [x] Run affected unit/integration/contract tests, lint, API drift and frontend checks as relevant. Review the diff and append actual results to the existing ledgers.

## Review focus

- Removed providers in queued snapshots must not bypass current selection validation.
- Missing configuration means demo; broken configuration or missing credentials must never silently select demo.
- Claude uses native structured output without granting formatting tools; refusal, truncation and tool blocks fail explicitly.
- Request/response bytes, total deadlines and shared budget reservation remain enforced before any retry or redirect could occur.
- Secrets stay out of metadata, outputs and errors, including malformed provider responses.

Work stays in the current checkout as required by AGENTS.md. No paid requests, deployment, publication or changes to local credentials are authorized by this cleanup.

Completed in the current checkout. See [verification](../evidence/llm-api-cleanup-2026-11-02.md). Review corrected Claude finish-reason validation; no outstanding findings.
