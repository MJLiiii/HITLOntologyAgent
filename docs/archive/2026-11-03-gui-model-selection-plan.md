# GUI model selection implementation plan

> **For agentic workers:** Use Superpowers execution/TDD for architecture and shared runtime; use Ponytail for the frontend. Keep work in this checkout as required by AGENTS.md.

**Goal:** Let users choose among project-authorized GPT and Claude models before generation.

**Architecture:** Reuse the existing server-owned profile registry, sanitized paginated catalog, request profile IDs and immutable job snapshots. Add a native, operation-filtered selector to existing forms. No new API, dependencies, client credentials or model discovery service.

**Tech stack:** Existing Python 3.12/FastAPI/HTTPX backend and React/TypeScript frontend.

## Design and approaches

The request extends the existing two-provider architecture. A shared GUI selector is sufficient: a global selection would incorrectly conflate operations and repair inheritance, while a new provider catalog service would duplicate the authorized registry. The implementation choice is per-action selection for chat, proposals, repair, model test generation, model-pilot and registered-task experiments. Deterministic demo experiments remain independent of model selection. TrustGraph extraction stays tied to its separately provisioned frozen flow.

The selector groups OpenAI and Claude options and identifies their exact model/profile. Missing-key choices stay visible but disabled. Choose the authorized configured server default initially; never silently choose another model if it is unavailable. Loading, errors and a configured catalog with no eligible models block new generation. Retry reloads the catalog. The explicit unconfigured demo mode remains usable. Repair initially omits the override to inherit its original snapshot, with current authorization checked by the server. Switching chat model starts a fresh conversation. Selection is scoped to the project and stale requests cannot overwrite the new project's catalog.

Populate the example and existing private local registry with multiple currently documented models, preserving existing profiles, the Terra default, dotenv values and project history. Model availability is configuration-only; it does not claim successful paid-provider access. Modern Claude passive thinking blocks may be ignored when extracting final text, but tool/refusal/unknown blocks and incomplete responses must still fail. Thinking bodies must not be persisted as final output.

## Constraints and review focus

- Only OpenAI and Claude; server-owned credentials and project/purpose authorization remain unchanged.
- Preserve exact queued descriptors, repair inheritance, revision checks, conversation boundaries and human publication authority.
- Preserve existing private configuration and unrelated edits. No paid calls, historical budget changes or working ontology mutations.
- No automatic fallback on catalog/provider failure; no arbitrary model-ID text input in the browser.
- Keep the existing 4,096-token and 120-second limits; configuration and readiness do not generate requests.
- Verify unavailable/default/empty catalogs, fetch races and project switching, submitted IDs for every model operation, deterministic payload omissions and repair inheritance.

## Tasks

- [x] Frontend: add focused failing selector and action-payload tests; implement shared native selector and integrate existing forms; run frontend tests and both builds. Owned by the Ponytail frontend agent.
- [x] Runtime: check official Claude thinking format, reproduce incompatibility with a controlled response, implement only the needed passive-block handling, retain fail-closed cases and run runtime tests. Owned by the Superpowers runtime agent.
- [x] Configuration: extend example and private local profiles using documented exact IDs, preserve existing profiles/default/credentials, and verify sanitized catalogs without calls. Owned by the primary agent.
- [x] Backend boundary: exercise multiple models per provider through actual catalog and queued HTTP requests, verify explicit snapshots and missing-key rejection; run existing authorization/inheritance tests.
- [x] Verification: run affected backend checks, complete frontend checks, lint and contract drift; independent review; update current guides and existing ledgers with actual evidence, then archive this completed plan.

Completed verification: [dated evidence](../evidence/gui-model-selection-2026-11-03.md). No source commit or deployment was performed.
