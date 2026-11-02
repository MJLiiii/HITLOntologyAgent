# Multi-LLM implementation verification — 1 November 2026

This increment adds server-owned profiles and a shared LiteLLM 1.106.6 runtime to Studio and the optional TrustGraph extraction worker. It does not authorize a real study or publish an ontology. Implementation is on `codex/multi-llm` in four local increments: profile registry; Studio/API/shared runtime; TrustGraph worker; comparison tooling and documentation.

## Verification

**528 backend tests passed, 7 skipped, zero failures/errors**, in 90.80 seconds on the final stable source. The skips are the existing optional live TrustGraph probe and six PostgreSQL cases. The retained command is `.venv/bin/pytest -q --disable-warnings --junitxml=.runtime/multi-llm/backend-final.xml`; its complete output is `.runtime/multi-llm/backend-final.log`. Tests requiring the application's own macOS engine sandbox run outside the enclosing desktop sandbox. An earlier restricted run failed to start those isolated engines; that was not reported as a successful run.

- Frontend: **60 tests across 14 files passed**; TypeScript and both production builds passed. Logs: `.runtime/multi-llm/frontend-final.log` and `frontend-build-final.log`.
- API contract regeneration/drift check, Ruff and `git diff --check` passed. The pinned dependency lock also passed offline verification.
- Real LiteLLM/OpenAI SDK requests exercised three real loopback HTTP servers for OpenAI, Anthropic and Ollama. Controlled transport tests additionally cover all provider routes, native formatting/authentication, schemas, refusal/truncation, rate limits, deadlines, response/input limits, redirects, unsupported settings, concurrent profiles/sessions and credential redaction. These are protocol tests, not paid-provider availability or model-quality results.
- Studio tests cover project authorization before enqueueing, immutable queued configuration and idempotency, repair inheritance/explicit override, common A–D settings, original citation/triple/schema rules, retained failures, immutable seals/exports, and unchanged approved state. The browser keeps one UUID per conversation. Health checks inspect model configuration without generating requests.
- TrustGraph tests cover separate flows, remotely inspected profile/session markers, immutable recovery/discovery/import bindings, configuration drift, explicit selected chunks, original array validation after envelope unwrapping, missing usage, and atomic one-run Go sessions. Dedicated completion processors preserve the existing processors and flows.

## Actual local execution

The shared SDK successfully called the existing local `qwen3:1.7b` Ollama model with a synthetic ownership question. The original answer/citation validator passed; the answer was `OperationsTeam`, with 89 reported input tokens, 32 output tokens and 3.522 seconds elapsed. This is a narrow local functional check, not a general quality evaluation. Evidence: `.runtime/multi-llm/local-ollama-check.json`.

The derived pinned TrustGraph image was built and executed with Docker networking disabled. Its actual Python 3.13 / TrustGraph 2.11.1 / LiteLLM 1.106.6 stack handled three fake HTTP completions, with zero external calls. The check verified the real superclass and SDK path, array envelope/original validation, invalid output, plain text, usage/correlation, the frozen Go session header and denied-flow rejection. Image: `oe-trustgraph-litellm@sha256:9d33a8f34dc72799cda48f879322c0c4f88f546bfe33e18446dd33cc81542667`. Source/dependency hashes and executable local evidence are under `.runtime/multi-llm/worker/` and `worker-offline-evidence.json`. Studio uses Python 3.12; worker wheels use Python 3.13 while dependency versions match.

The existing local Studio was restarted with the updated implementation and the same Ollama configuration. Its model catalog and readiness endpoints returned HTTP 200. Jena, OntoCheck and the database were available; the model correctly reported `configured_unverified` because routine health makes no model request. The persistent workspace still had zero approved versions and an unaccepted scope. Evidence: `.runtime/multi-llm/running-api-check.json`.

## Hosted comparison and remaining evidence

The comparison runner stages identical synthetic chat/proposal inputs and calls the actual Studio workflows. It reports schema validity, citation validity, expected facts, returned model, latency, normalized usage, cost provenance and failures separately. Its shared SQLite ledger reserves full-price ceilings before dispatch, including ambiguous failures, and enforces 20 attempts / 4096 output tokens per call / USD 1 total across Studio and TrustGraph.

**Historical pre-credential status (superseded by the live follow-up below):** the key has not been configured. The current report has four credential-blocked observations, **zero reserved completion attempts and USD 0 reserved**. A private, ignored `.env` placeholder is ready for `OPENCODE_API_KEY`; no key is requested in chat. The price artifact is tied to exact profile revisions, expires within 24 hours and must be refreshed from official evidence before a later run. No OpenAI or Anthropic paid API was called. Live Go response quality and live profile-bound TrustGraph extraction/import are not claimed.

See [configuration/API examples](multi-llm.md), [comparison evidence](model-comparison.md), and [TrustGraph setup and probe](trustgraph-multi-llm.md). The source change does not rewrite historical records, change embedding/reranking configuration or remove the original local demo path. The original [ONTOCHECK_REVIEW.md](archive/ONTOCHECK_REVIEW.md) remains untouched.

## Live OpenCode Go follow-up — 1 November 2026

The privately configured credential enabled four actual Studio workflow calls using fresh official price/context evidence and the original shared ledger. Both grounded chats and the Kimi proposal passed. GLM produced schema-valid, cited JSON with the correct ownership triple, but Studio rejected its unresolved modelling questions; the runner reports `expected_facts_failed` for that condition. Overall exit status was 2. See [the live comparison follow-up](model-comparison.md#live-follow-up--1-november-2026-1854-utc) and `.runtime/multi-llm/live-go-report.md` for timing, usage and the metric interpretation.

All four attempts remain reserved: USD 0.834937600 of the USD 1 ceiling, with no retries or reset. Provider-reported cost was zero; reported list cost was USD 0.014945400 in total. No approval, publication, engine execution or live TrustGraph extraction/import was included. The earlier credential-blocked observations remain historical evidence.

A subsequent requested DeepSeek V4.1 Flash chat passed schema, citation and known-answer checks in 7.879 seconds. Its proposal was budget-blocked before dispatch. The shared ledger now retains 5 attempts and USD 0.987395200 reserved; no reset or increase occurred. Argon was not called: its advertised Google transport is unsupported and its conservative reservation exceeds the existing ceiling. See the DeepSeek/Argon follow-up in [comparison evidence](model-comparison.md) and `.runtime/multi-llm/deepseek-live-report.md`.


### Two-agent contract and local test-generation check — 2 November 2026

The Proposal Agent and Test Generation Agent share ModelClient transport but use separate input schemas, prompts, profile purposes and persisted generation records. Controlled cases verify malformed references/queries/fixtures, authority-field rejection, frozen profile settings and revocation before result commit. A bounded installed Qwen3 1.7B attempt returned an ASK draft without its query; it was rejected with output and daemon usage retained, without fallback. No hosted-provider call or budget reservation occurred, and existing comparison ledgers were not reset. [The dated report](evidence/two-agent-team-2026-11-02.md) distinguishes controlled detection results from the unsuccessful actual local response.


The user subsequently selected API-backed generation only. Bundled Qwen setup/launch commands and the local test-agent benchmark option were removed; observations above remain historical. Current verification uses controlled API responses, without invoking a local or paid model.

### Two-provider cleanup — 2 November 2026

The current generation layer supports only OpenAI and Claude through native bounded HTTPX requests. LiteLLM and the other active provider paths were removed; the earlier observations in this document remain dated evidence, not current provider support. See [current setup](multi-llm.md) and [cleanup verification](evidence/llm-api-cleanup-2026-11-02.md): 617 backend tests passed with eight optional skips, 64 frontend tests passed, and lint/TypeScript/API-contract checks passed. No paid provider call was made during this cleanup.

### User-authorized OpenAI key check — 2 November 2026

After the user supplied `.env` credentials and requested a live test, the official OpenAI model-list endpoint returned HTTP 200. One `gpt-4.1-mini` completion then passed through the real Studio profile resolver, `ModelClient`, native runtime, `GroundedAnswer` schema and citation validator using a temporary project-authorized profile and an invented Atlas/Platform ownership source. The request was capped at 128 output tokens and 30 seconds, without retries. HTTP 200 returned `gpt-4.1-mini-2025-04-14`; schema, citation and the narrow expected-fact check passed. Provider-reported usage was 207 input / 32 output tokens, with 2.408 seconds elapsed. Cost was not reported or inferred.

Credential-free evidence is `.runtime/llm-api-key-test-2026-11-02.json`. No `.env`, working ontology, approval, publication, historical budget or project data was changed. No Anthropic credential was present, so Claude was not called. The application registry remains unconfigured; this temporary-profile test proves the OpenAI credential and request path, not persistent application setup or general model quality.
