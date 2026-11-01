# Implementation ledger — CODEX_DEVELOPMENT_PLAN.md

## Decisions (1 November 2026)

- Ruling: the requested `developPlan.md` is absent; use the supplied `CODEX_DEVELOPMENT_PLAN.md` as the specification.
- Initial ruling: implement in this folder as requested. At first inspection there was no Git repository or application; preserve supplied documents/backups. Source Git now exists with the real commits listed below.
- Ruling: the user delegates ambiguity and conflict decisions. Execute the full engineering goal, not the plan's example instruction to execute Task 1 only. Do not wait for design approvals for reversible local implementation.
- Ruling: build the standalone local web harness alongside the TrustGraph plugin export. A harness does not close TrustGraph host integration. Surface unavailable integrations explicitly and retain TODOs.
- Ruling: only synthetic demo scope is enabled. The user explicitly confirmed no real study is approved. Deloitte scope selection, real expert study/consent, shared deployment and confidential ingestion require external decisions and must never be fabricated.
- Ruling: use Python 3.12, FastAPI, SQLAlchemy, PostgreSQL for the deployment and a portable SQLite local demo/test option. Both use the same service and immutable artifact logic. SQLite is single-machine only.
- Ruling: use independent agents for frontend, validation and integration investigations; file ownership is disjoint. Root owns contracts, API, chat, workflow, persistence and integration verification.
- Ruling: local fixed demo generation and grounded retrieval work without an API key, with honest mode labels. Optional configured model calls must preserve evidence/ontology constraints and cannot publish.
- Ruling: preserve one reviewed initial source snapshot in the newly initialized local Git repository. Parallel implementation did not produce the plan's example per-task historical commits; no retrospective commit sequence or historical red/green evidence is fabricated. No remote publication is authorized or performed.
- Continuation: the initial snapshot is commit `a7cb630`. Continue in the explicitly requested folder on `codex/complete-engineering`; the existing runtime and large pinned caches stay in place. Commit `c7f1eab` subsequently records atomic workflow effects/job results. The user reiterated that no real study is approved. Synthetic tests and integration work remain authorized; no real participant or study outcome is inferred.

## Engineering execution status

These checkmarks mean the bounded implementation and cited focused evidence exist. They do not mark every full-plan checkbox complete; `requirements-audit.md` retains all 70 requirement traces and 56 named-test traces, including partial/external gates.

- [ ] 1. Integration: real pinned host/native/workspace and provider paths verified; seeded OntologyRAG known-answer failure, shared deployment and upstream guarantees remain explicit limits.
- [x] 2. Foundation, local identity, artifacts, synthetic scope, migrations and operational scripts.
- [x] 3. Immutable proposals and deterministic admitted RDF changes.
- [x] 4. Versioned local evidence and durable explicitly selected TrustGraph snapshot imports; no generic upstream completion claim.
- [x] 5. Grounded chat, optional actual-model generation and bounded fail-closed repair.
- [x] 6. Real Jena validation and pinned isolated OntoCheck within their admitted RDFS workload.
- [x] 7. Candidate-derived constrained development tests, real scenario matrix and human oracle control.
- [x] 8. Exact human review and recoverable Git publication under trusted local authority.
- [x] 9. Responsive six-view Studio and real plugin host subset; full shared-host/accessibility certification remains outside the proof.
- [x] 10. Demo/pilot plus registered synthetic A–D task infrastructure, immutable D linkage and exports.
- [ ] 11. Evaluator/protocol/allocation/analysis engineering exists; real study remains explicitly unapproved and absent.
- [ ] 12. Continuation backend 382/7 optional skips, frontend 50, TypeScript/both builds/lint/API checks and configured-import browser verification passed. Final manifest/source freeze is in progress; source identity is the final continuation commit containing release-manifest.json.

## Evidence

Initial workspace inspection: only plan/review documents and proposal outputs; no application, no Git repository. Java 21 and PostgreSQL 18 binaries are available; default Java is 8, so runner must choose Java explicitly. Python packages require network approval or cached packages. No credentials read.

### Implemented and exercised in this session

- Foundations: pinned Python environment; content-addressed verified artifacts; deterministic named RDF changes preserving typed/language lexical forms; strict request schemas; SQLAlchemy + Alembic; verified adoption of pre-migration SQLite schema.
- Local sources: distinct upload/ingest/freeze, immutable source bytes/chunks/corpora, exact span/hash verification, source withdrawal blocks new publication. The local adapter is explicitly labelled. The private configured provider now binds seed/config before enqueue, commits prepared intent/receipt in the existing ledger, recovers only exact observed submissions and copies explicitly selected verified sources into immutable local corpora. Run-specific remote parent IDs prevent old extraction lineage from satisfying a fresh intent.
- Chat: source citations, inspectable ontology triples, immutable context identity including follow-up history, unsupported-answer handling, optional schema-constrained Ollama client with strict reference validation. The actual local provider is installed under `.runtime`, pinned by `infra/model.lock.json`, and browser chat/follow-up checks succeeded. Proposal failures are retained separately; chat success does not prove modelling quality. Bounded model retrieval ranks the complete source snapshot and reports truncation.
- Workflow: immutable proposal successors, actual Jena and actual isolated OntoCheck reports, human scope/review/publication, Git CAS + reservation/receipt recovery, idempotency, concurrent publication gate, hash-chained audit.
- Development tests: deterministic candidate-aware generation uses frozen candidate/questions/changes/shapes/fixtures/evidence. Positive, negative, missing-data, boundary, incompatible-value and regression families preserve exact violation signatures and literal terms, surface unsupported coverage, and require human oracle acceptance/new bundle. 27 focused checks and a 12-case real-Jena fixture passed; mutant inference/shape changes fail. See docs/synthetic-test-generation.md.
- Repair: failed entailment feedback only, immutable successors, two-attempt budget, no automatic assessment feedback or publication.
- UI: six responsive tabs, chat and evidence, explicit review/publication, test-oracle review, review timer, version provenance, versioned scopes and reviewed mappings. Model/scripted experiment selection and explicit D staging/persisted-review linkage are implemented. Final browser and test evidence is recorded in `release-verification.md`.
- Reproduction/research: Make targets, lockfiles, scripted/actual-model A–D runners, strict immutable registration of multiple synthetic development tasks, missingness-preserving sealed outputs/exports, backup/restore, generated OpenAPI request contracts, external evaluator CLI, allocation/timing and optional task-level bootstrap analysis. Registration authenticates human scope/oracle decisions and resolved synthetic source identities; held-out and real-study activation fields are absent. The actual study remains unapproved; no expert data is fabricated.
- Historical initial verification: 280 backend tests passed with 9 explicit optional skips; 36 frontend tests passed. Later focused provider/application checks: 53 passed with 1 generic opt-in live probe skipped; actual isolated provider lifecycle separately passed. Registered model/protocol matrix: 43 passed; initial registration HTTP cases: 2 passed. **Final continuation verification: 382 backend passed, 7 optional checks skipped in 66.54 seconds; 50 frontend tests passed.** TypeScript, both production builds, lint and OpenAPI drift checks passed. XML/log are in `research/results/engineering-continuation/final-backend.*`; JUnit records 389 cases with zero failures/errors. The 7 skips comprise 1 opt-in TrustGraph read probe and 6 separately exercised PostgreSQL checks. These counts refer to different scopes and are not additive. Upstream Starlette/AnyIO/RDFLib dependencies emit deprecation warnings.

### Independent review corrections

`docs/backend-review.md` preserves the original findings. Regression tests now cover operator-only session bootstrap (including omitted service credentials), immutable report verification at publication, actual runner/JVM/lock hashes, recovery eligibility before CAS, no revisions during a publication reservation, per-project recovery failure isolation, history-sensitive context digests and unknown named-entity answers. All corresponding focused tests passed after observed failures. The local trust boundary excludes processes with access to the operator's private session key; shared deployment is still disabled.

### Verified integration boundaries and remaining gates

`docs/native-editor-boundary.md` proves an actual native ontology-editor mutation changed only candidate configuration while main and populated disposable Studio canonical files/refs stayed unchanged; a native JWT could not publish through Studio. `docs/workspace-denial-evidence.json` records a real non-administrator writer: own workspace read/write 200, foreign source read/write/config 403, unchanged foreign bytes, and cleanup limited to probe identities/workspaces.

`infra/portal/import-evidence.json` and `docs/trustgraph-import-contract.md` record the final isolated seeded provider lifecycle: real engines, explicitly simulated review, pre-enqueue approved seed/config version 48, a run-specific source URI, durable receipt recovery without resubmission, one exact 98-byte selected chunk, eight quoted extraction facts, explicit-corpus question read and unchanged approved Git refs. Historical frozen reads work without upstream access. Three early selection attempts failed closed before required extraction provenance existed. Generic processing completion, remote immutable storage and processor configuration attestation are not available. The earlier ordinary GraphRAG answer passed; seeded OntologyRAG still failed its known-answer check after a concrete seed projection defect was corrected. No model-quality conclusion is substituted for provenance proof.

`research/synthetic-task-protocol.json` and its schema now describe human-registered synthetic development packets with original query/literal semantics, reviewed additional oracles, exact source/seed/config identities and common A–D budgets. Two distinct authored tasks executed their own workloads through real Jena/OntoCheck with a scripted model double. These are mechanism tests, not live-model comparisons or real participant observations. Independent registration review reproduced and verified the correction of the D mapping/proposal source-scope regression below.

Independent evaluator OS identity/mount isolation, real domain agreement, source rights, approved tasks/oracles, consenting experts, shared Studio identity and publisher OS separation remain external. No real study is approved or conducted. Continuation suite/build checks passed; historical checks are not relabelled as fresh results. Final source identity is the **final continuation commit containing release-manifest.json**; the manifest records source and built artifact hashes.

### Interrupted job recovery continuation

Six fault-injection regressions first reproduced committed effects with abandoned job results and a late worker committing after lease expiry. Proposal, seed, test-suite, validation and assessment effects now commit their result in the same database transaction and reject expired leases. A seventh regression reproduced a repair successor committed without its attempt/result; repair completion now shares that transaction too. A crash after model generation but before revision materialization retains the model output linked to the failed job and never replays it on an idempotent retry. This is deliberate fail-closed recovery, not automatic model replay. Experiment batch storage and local ingestion use the same atomic completion helper. Focused recovery/workflow verification: **62 passed** in 11.45 seconds; these checks are included in the later 382-pass continuation suite, not added to it.

### Independent registration review continuation

`tests/integration/test_registration_review.py` reproduced D staging silently adding mapping-only evidence into a proposal's evidence IDs while retaining the original proposal corpus UUID. Registration must keep the complete source set for packet integrity while freezing proposal evidence separately for staging. The regression was observed failing. Root freezes proposal evidence separately and stages the exact evidence set from the immutable registered revision; independent rerun of the three review regressions and two registration cases passed **5 tests in 1.57 seconds**. Two independent negative cases passed: held-out request fields/cross-project registration references cannot reach the runner, and a withdrawn registered source stops generation before any model call. This review creates only isolated synthetic fixtures and no real approval or study observation.

### Final continuation verification

The current backend XML/log records **382 passed, 7 skipped in 66.54 seconds**, with zero failures/errors. Frontend **50 passed**, TypeScript, both production builds, lint and `make check-api-contracts` passed. The configured isolated 5173 browser selected one actual TrustGraph chunk, froze verified evidence, then read the exact Atlas passage through Chat’s current-corpus picker with a verified citation and explicit unchanged-ontology warning. Screenshots are `docs/screenshots/trustgraph-selected-import.jpg` and `docs/screenshots/trustgraph-source-chat.jpg`. The final main-model browser check returned the correct Payroll ownership/classification answer with two resolved citations and two ontology triples; main scope and ontology remain unapproved. See `docs/browser-continuation-evidence.json` and `docs/screenshots/ontology-chat-results.jpg`.

The source identity for this continuation is the **final continuation commit containing release-manifest.json**, with the actual commit hash resolved using `git log -1 -- docs/release-manifest.json`. Initial a7cb630/280-pass and c7f1eab recovery history remain unchanged. No real study, generic TrustGraph completion, remote immutability, model OntologyRAG known-answer success or shared deployment approval is claimed.
