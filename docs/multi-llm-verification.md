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

**OpenCode Go live testing remains pending:** the key has not been configured. The current report has four credential-blocked observations, **zero reserved completion attempts and USD 0 reserved**. A private, ignored `.env` placeholder is ready for `OPENCODE_API_KEY`; no key is requested in chat. The price artifact is tied to exact profile revisions, expires within 24 hours and must be refreshed from official evidence before a later run. No OpenAI or Anthropic paid API was called. Live Go response quality and live profile-bound TrustGraph extraction/import are not claimed.

See [configuration/API examples](multi-llm.md), [comparison evidence](model-comparison.md), and [TrustGraph setup and probe](trustgraph-multi-llm.md). The source change does not rewrite historical records, change embedding/reranking configuration or remove the original local demo path. The original `ONTOCHECK_REVIEW.md` remains untouched.
