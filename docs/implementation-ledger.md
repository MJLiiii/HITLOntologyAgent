# Implementation ledger — CODEX_DEVELOPMENT_PLAN.md

## Decisions (1 November 2026)

- Ruling: the requested `developPlan.md` is absent; use the supplied `CODEX_DEVELOPMENT_PLAN.md` as the specification.
- Ruling: implement in this folder as requested. There is no existing Git repository or code to isolate; preserve all supplied documents and backups.
- Ruling: the user delegates ambiguity and conflict decisions. Execute the full engineering goal, not the plan's example instruction to execute Task 1 only. Do not wait for design approvals for reversible local implementation.
- Ruling: build the standalone local web harness alongside the TrustGraph plugin export. A harness does not close TrustGraph host integration. Surface unavailable integrations explicitly and retain TODOs.
- Ruling: only synthetic demo scope is enabled. The user explicitly confirmed no real study is approved. Deloitte scope selection, real expert study/consent, shared deployment and confidential ingestion require external decisions and must never be fabricated.
- Ruling: use Python 3.12, FastAPI, SQLAlchemy, PostgreSQL for the deployment and a portable SQLite local demo/test option. Both use the same service and immutable artifact logic. SQLite is single-machine only.
- Ruling: use independent agents for frontend, validation and integration investigations; file ownership is disjoint. Root owns contracts, API, chat, workflow, persistence and integration verification.
- Ruling: local fixed demo generation and grounded retrieval work without an API key, with honest mode labels. Optional configured model calls must preserve evidence/ontology constraints and cannot publish.
- Ruling: preserve one reviewed initial source snapshot in the newly initialized local Git repository. Parallel implementation did not produce the plan's example per-task historical commits; no retrospective commit sequence or historical red/green evidence is fabricated. No remote publication is authorized or performed.

## Execution checklist

- [ ] 1. Integration pins and verified boundaries (live external TODOs explicitly retained)
- [ ] 2. Foundation, auth, artifacts, demo scope, migrations and operations
- [ ] 3. Immutable proposals and deterministic RDF changes
- [ ] 4. Versioned local evidence; TrustGraph adapter status
- [ ] 5. Grounded chat, proposal generation and bounded repair
- [ ] 6. Jena validation and pinned offline OntoCheck assessment
- [ ] 7. Constrained development tests and oracle control
- [ ] 8. Exact human review and recoverable Git publication
- [ ] 9. Responsive Studio web and plugin bundle
- [ ] 10. A–D demo experiment records and exports
- [ ] 11. Research protocol ready; real study explicitly gated on people/data
- [ ] 12. Reproduction, backup/restore, full tests and independent review

## Evidence

Initial workspace inspection: only plan/review documents and proposal outputs; no application, no Git repository. Java 21 and PostgreSQL 18 binaries are available; default Java is 8, so runner must choose Java explicitly. Python packages require network approval or cached packages. No credentials read.

### Implemented and exercised in this session

- Foundations: pinned Python environment; content-addressed verified artifacts; deterministic named RDF changes preserving typed/language lexical forms; strict request schemas; SQLAlchemy + Alembic; verified adoption of pre-migration SQLite schema.
- Local sources: distinct upload/ingest/freeze, immutable source bytes/chunks/corpora, exact span/hash verification, source withdrawal blocks new publication. Local adapter is explicitly labelled; live TrustGraph remains open.
- Chat: source citations, inspectable ontology triples, immutable context identity including follow-up history, unsupported-answer handling, optional schema-constrained Ollama client with strict reference validation. The actual local provider is installed under `.runtime`, pinned by `infra/model.lock.json`, and browser chat/follow-up checks succeeded. Proposal failures are retained separately; chat success does not prove modelling quality. Bounded model retrieval ranks the complete source snapshot and reports truncation.
- Workflow: immutable proposal successors, actual Jena and actual isolated OntoCheck reports, human scope/review/publication, Git CAS + reservation/receipt recovery, idempotency, concurrent publication gate, hash-chained audit.
- Development tests: four synthetic positive/negative/missing/boundary scenarios; human oracle acceptance creates a successor and preserves required sentinels. Actual Jena executed all six fixed+generated cases successfully.
- Repair: failed entailment feedback only, immutable successors, two-attempt budget, no automatic assessment feedback or publication.
- UI: six responsive tabs, chat and evidence, explicit review/publication, test-oracle review, review timer, version provenance, versioned scopes and reviewed mappings. Model/scripted experiment selection and explicit D staging/persisted-review linkage are implemented. Final browser and test evidence is recorded in `release-verification.md`.
- Reproduction/research: Make targets, lockfiles, scripted and actual model A–D runners, immutable outcomes, missingness-preserving exports, backup/restore, generated OpenAPI request contracts, external evaluator CLI, allocation/timing helpers and optional task-level bootstrap analysis. The actual study remains unapproved; no expert data is fabricated.
- Verification milestone: 114 backend tests passed before the latest repair/artifact additions; their focused regressions passed separately. Full suite is being rerun after integration. Upstream Starlette/AnyIO emits a deprecation warning.

### Independent review corrections

`docs/backend-review.md` preserves the original findings. Regression tests now cover operator-only session bootstrap (including omitted service credentials), immutable report verification at publication, actual runner/JVM/lock hashes, recovery eligibility before CAS, no revisions during a publication reservation, per-project recovery failure isolation, history-sensitive context digests and unknown named-entity answers. All corresponding focused tests passed after observed failures. The local trust boundary excludes processes with access to the operator's private session key; shared deployment is still disabled.

### Remaining gates (do not infer completion)

The actual host mount/read boundary, configurable scopes/mappings and model-backed condition runners are implemented. The complete TrustGraph processing boundary, final clean setup/backup/browser checks and release provenance remain tracked in `release-verification.md` and `requirements-audit.md`. Independent evaluator deployment and research execution with permitted data and consenting experts remain external. The original full-plan checkboxes above stay open where any required integration, verification or external study requirement remains; the audit maps all 70 task checkboxes and 56 named tests.
