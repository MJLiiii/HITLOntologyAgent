# OpenAI and Claude API cleanup — 2 November 2026

The active Studio and profile-bound TrustGraph model layer now supports only OpenAI (`openai`) and Claude (`anthropic`). Native bounded HTTPX requests replace LiteLLM. The lockfile removes LiteLLM and 20 other unneeded dependencies; existing pinned OpenAI schema conversion, JSON Schema validation and YAML tooling are direct dependencies. One example registry replaces the previous provider examples.

Removed active paths include Ollama legacy settings, OpenCode Go headers/accounting/session branches, generic compatible/proxy provider identifiers and the obsolete TrustGraph LiteLLM wrapper. Frozen profile authorization, no-retry/no-redirect transport, total deadlines, byte/token bounds, original schema/citation checks, secret redaction, generic optional budget reservations and human publication authority remain. Historical provider snapshots cannot dispatch or inherit a reused registry ID. Private configuration, existing ledgers, approved artifacts and recorded evidence were preserved. Retired host-investigation scripts and embedding processors remain explicitly historical/separate.

## Verification

- Full backend suite with the Makefile's pinned Java executable: **617 passed, 8 skipped**, 91.07 seconds. The skips are seven opt-in PostgreSQL cases and one opt-in live TrustGraph read probe. Existing dependency deprecation warnings remain (3,415 warnings).
- Frontend: **64 tests passed** across 14 files.
- `make lint`: Python Ruff and TypeScript passed. Additional Ruff coverage of `infra/portal` passed.
- `make check-api-contracts`: OpenAPI, TypeScript contracts, operation map and aliases match; no contract regeneration was needed.
- Controlled real loopback endpoints verify native OpenAI and Claude paths, authentication, payloads and usage. Runtime checks also cover refusals, tool blocks, malformed/incomplete envelopes, compressed decoded-byte limits, credentials, total deadlines, budget locking and removed-provider snapshots.
- Independent review found a malformed Claude `stop_reason: "stop"` could pass after normalization. A failing regression demonstrated it; the fix requires native `end_turn`. Re-review found no remaining actionable issues.
- Changed guide links and `git diff --check` passed.

Initial sandbox runs could not bind loopback ports or exercise real-engine processes; those failures were not counted as passes. The final full suite ran outside that restriction with controlled local services and disposable synthetic stores. The separate `.venv-trustgraph` lacks `jsonschema`; worker contracts ran through the main pinned environment, which has the optional TrustGraph runtime. The worker image was staged/tested but not rebuilt or deployed in Docker during this cleanup.

No live OpenAI/Claude requests, charges, new research observations, human decisions or ontology publication occurred. Provider availability and model quality remain unverified. Local configuration inspection returned `not_configured`; the labelled demo remains active until an operator configures the [two-provider registry](../multi-llm.md). The [completed cleanup plan](../archive/llm-api-cleanup-plan.md) records scope and review focus.
