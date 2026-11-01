# Ontology Studio execution plan

**Goal:** a runnable local web application that chats using source evidence and ontology results, and supports the plan's candidate → checks → human review → immutable publication loop.

**Spec:** `CODEX_DEVELOPMENT_PLAN.md` sections 1–16. The original specification remains authoritative. Decisions and exceptions live in `docs/implementation-ledger.md`.

**Architecture:** FastAPI with SQLAlchemy persistence, content-addressed artifacts and a sole Git publisher. React/TypeScript standalone local harness plus TrustGraph-compatible plugin entry. Isolated Jena process and pinned offline OntoCheck assessment. All generated content is untrusted; no automatic approval.

## Work packages and checks

1. Pin/probe upstream integrations; distinguish source inspection from exercised compatibility. Write real runner fixtures and verified host export notes.
2. Add artifact, RDF, auth and workflow tests before implementation. Verify tampering, unauthorized publication, stale/concurrent decisions, evidence failures and immutable successors.
3. Add chat tests for evidence citations, exact ontology bindings, follow-ups, unknown answers and read-only behavior. Implement local evidence retrieval and optional model configuration without requiring a key for the demo.
4. Implement versioned sources, proposal/revision APIs, validation, assessment, review, Git CAS/recovery, audit and durable job records. Freeze all inputs in bundle digests.
5. Build six-view Studio with prominent chat. Generate API types, verify build and meaningful UI interactions in browser.
6. Implement constrained test specifications, frozen demo A–D pilot and missingness-preserving exports. Keep real studies, held-out oracles and human data gated.
7. Run backend tests, frontend checks, runner tests, local end-to-end flow, backup/restore and fresh independent review. Document commands, remaining integration gates and limitations.

## Review focus

- A service credential, client-supplied actor or native editor must never publish.
- A changed bundle/source or stale head must invalidate eligibility.
- Timeout/parser/runner failures must never become successful checks.
- Chat must cite immutable evidence and avoid unsupported assertions.
- Experiments must retain failed runs and never leak held-out inputs into generation.
