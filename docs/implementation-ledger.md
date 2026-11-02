# Implementation ledger

This historical ledger follows [CODEX_DEVELOPMENT_PLAN.md](archive/CODEX_DEVELOPMENT_PLAN.md). See the [planning archive](archive/README.md) for the later arrival of `developPlan.md` and the preserved original paths. Later model-layer evidence is recorded in [multi-LLM verification](multi-llm-verification.md).

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
- Continuation: the initial snapshot is commit `a7cb630`. Continue in the explicitly requested folder on `codex/complete-engineering`; the existing runtime and large pinned caches stay in place. Commit `c7f1eab` subsequently records atomic workflow effects/job results; `ae9b5c7` records verified source imports and registered synthetic tasks. The user reiterated that no real study is approved. Synthetic tests and integration work remain authorized; no real participant or study outcome is inferred.

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
- [x] 9. Responsive six-view Studio, generated request/response operations, standalone workflow acceptance and the required pinned-host smoke. Exhaustive shared-host/accessibility certification is not an additional local MVP requirement.
- [x] 10. Demo/pilot and registered synthetic A–D tasks, immutable D linkage and nine-record dashboard/export parity across six browser task/phase scopes. Export v2 preserves sealed records and separate provenance.
- [ ] 11. Evaluator/protocol/allocation/analysis engineering exists; real study remains explicitly unapproved and absent.
- [ ] 12. Historical ae9b5c7 passed backend 382/7 optional skips and frontend 50. Current backend 405 passed/7 skipped in 75.87 seconds, frontend 59, TypeScript/both builds/lint/OpenAPI checks passed; source identity is the commit containing docs/release-manifest.json. Current source identity is the commit containing docs/release-manifest.json.

## Evidence

Initial workspace inspection: only plan/review documents and proposal outputs; no application, no Git repository. Java 21 and PostgreSQL 18 binaries are available; default Java is 8, so runner must choose Java explicitly. Python packages require network approval or cached packages. No credentials read.

### Implemented and exercised in this session

- Foundations: pinned Python environment; content-addressed verified artifacts; deterministic named RDF changes preserving typed/language lexical forms; strict request schemas; SQLAlchemy + Alembic; verified adoption of pre-migration SQLite schema.
- Local sources: distinct upload/ingest/freeze, immutable source bytes/chunks/corpora, exact span/hash verification, source withdrawal blocks new publication. The local adapter is explicitly labelled. The private configured provider now binds seed/config before enqueue, commits prepared intent/receipt in the existing ledger, recovers only exact observed submissions and copies explicitly selected verified sources into immutable local corpora. Run-specific remote parent IDs prevent old extraction lineage from satisfying a fresh intent.
- Chat: source citations, inspectable ontology triples, immutable context identity including follow-up history, unsupported-answer handling, optional schema-constrained Ollama client with strict reference validation. The actual local provider is installed under `.runtime`, pinned by `infra/model.lock.json`, and browser chat/follow-up checks succeeded. Proposal failures are retained separately; chat success does not prove modelling quality. Bounded model retrieval ranks the complete source snapshot and reports truncation.
- Workflow: immutable proposal successors, actual Jena and actual isolated OntoCheck reports, human scope/review/publication, Git CAS + reservation/receipt recovery, idempotency, concurrent publication gate, hash-chained audit.
- Development tests: deterministic candidate-aware generation uses frozen candidate/questions/changes/shapes/fixtures/evidence. Positive, negative, missing-data, boundary, incompatible-value and regression families preserve exact violation signatures and literal terms, surface unsupported coverage, and require human oracle acceptance/new bundle. 27 focused checks and a 12-case real-Jena fixture passed; mutant inference/shape changes fail. See docs/synthetic-test-generation.md.
- Repair: failed entailment feedback only, immutable successors, two-attempt budget, no automatic assessment feedback or publication.
- UI: six responsive tabs, chat and evidence, explicit review/publication, test-oracle review, review timer, version provenance, versioned scopes and reviewed mappings. Model/scripted experiment selection and explicit D staging/persisted-review linkage are implemented. Final browser and test evidence is recorded in `evidence/release-verification.md`.
- Reproduction/research: Make targets, lockfiles, scripted/actual-model A–D runners, strict immutable registration of multiple synthetic development tasks, missingness-preserving sealed outputs/exports, backup/restore, generated OpenAPI request/response aliases and operation contracts with inferred results for all 13 job routes, external evaluator CLI, allocation/timing and optional task-level bootstrap analysis. Registration authenticates human scope/oracle decisions and resolved synthetic source identities; held-out and real-study activation fields are absent. The actual study remains unapproved; no expert data is fabricated.
- Historical initial verification: 280 backend tests passed with 9 explicit optional skips; 36 frontend tests passed. Later focused provider/application checks: 53 passed with 1 generic opt-in live probe skipped; actual isolated provider lifecycle separately passed. Registered model/protocol matrix: 43 passed; initial registration HTTP cases: 2 passed. **Historical ae9b5c7 verification: 382 backend passed, 7 optional checks skipped in 66.54 seconds; 50 frontend tests passed.** TypeScript, both production builds, lint and OpenAPI drift checks passed. XML/log are in `research/results/engineering-continuation/final-backend.*`; JUnit records 389 cases with zero failures/errors. The 7 skips comprise 1 opt-in TrustGraph read probe and 6 separately exercised PostgreSQL checks. These counts refer to different scopes and are not additive. Upstream Starlette/AnyIO/RDFLib dependencies emit deprecation warnings.

### Independent review corrections

`docs/evidence/backend-review.md` preserves the original findings. Regression tests now cover operator-only session bootstrap (including omitted service credentials), immutable report verification at publication, actual runner/JVM/lock hashes, recovery eligibility before CAS, no revisions during a publication reservation, per-project recovery failure isolation, history-sensitive context digests and unknown named-entity answers. All corresponding focused tests passed after observed failures. The local trust boundary excludes processes with access to the operator's private session key; shared deployment is still disabled.

### Verified integration boundaries and remaining gates

`docs/evidence/native-editor-boundary.md` proves an actual native ontology-editor mutation changed only candidate configuration while main and populated disposable Studio canonical files/refs stayed unchanged; a native JWT could not publish through Studio. `docs/workspace-denial-evidence.json` records a real non-administrator writer: own workspace read/write 200, foreign source read/write/config 403, unchanged foreign bytes, and cleanup limited to probe identities/workspaces.

`infra/portal/import-evidence.json` and `docs/trustgraph-import-contract.md` record the final isolated seeded provider lifecycle: real engines, explicitly simulated review, pre-enqueue approved seed/config version 48, a run-specific source URI, durable receipt recovery without resubmission, one exact 98-byte selected chunk, eight quoted extraction facts, explicit-corpus question read and unchanged approved Git refs. Historical frozen reads work without upstream access. Three early selection attempts failed closed before required extraction provenance existed. Generic processing completion, remote immutable storage and processor configuration attestation are not available. The earlier ordinary GraphRAG answer passed; seeded OntologyRAG still failed its known-answer check after a concrete seed projection defect was corrected. No model-quality conclusion is substituted for provenance proof.

`research/synthetic-task-protocol.json` and its schema now describe human-registered synthetic development packets with original query/literal semantics, reviewed additional oracles, exact source/seed/config identities and common A–D budgets. Two distinct authored tasks executed their own workloads through real Jena/OntoCheck with a scripted model double. These are mechanism tests, not live-model comparisons or real participant observations. Independent registration review reproduced and verified the correction of the D mapping/proposal source-scope regression below.

Independent evaluator OS identity/mount isolation, real domain agreement, source rights, approved tasks/oracles, consenting experts, shared Studio identity and publisher OS separation remain external. No real study is approved or conducted. Continuation suite/build checks passed; historical checks are not relabelled as fresh results. Source commit ae9b5c7 records that continuation. The current contract/parity/security pass awaits the commit containing docs/release-manifest.json.

### Interrupted job recovery continuation

Six fault-injection regressions first reproduced committed effects with abandoned job results and a late worker committing after lease expiry. Proposal, seed, test-suite, validation and assessment effects now commit their result in the same database transaction and reject expired leases. A seventh regression reproduced a repair successor committed without its attempt/result; repair completion now shares that transaction too. A crash after model generation but before revision materialization retains the model output linked to the failed job and never replays it on an idempotent retry. This is deliberate fail-closed recovery, not automatic model replay. Experiment batch storage and local ingestion use the same atomic completion helper. Focused recovery/workflow verification: **62 passed** in 11.45 seconds; these checks are included in the later 382-pass continuation suite, not added to it.

### Independent registration review continuation

`tests/integration/test_registration_review.py` reproduced D staging silently adding mapping-only evidence into a proposal's evidence IDs while retaining the original proposal corpus UUID. Registration must keep the complete source set for packet integrity while freezing proposal evidence separately for staging. The regression was observed failing. Root freezes proposal evidence separately and stages the exact evidence set from the immutable registered revision; independent rerun of the three review regressions and two registration cases passed **5 tests in 1.57 seconds**. Two independent negative cases passed: held-out request fields/cross-project registration references cannot reach the runner, and a withdrawn registered source stops generation before any model call. This review creates only isolated synthetic fixtures and no real approval or study observation.

### Historical ae9b5c7 verification

The ae9b5c7 backend XML/log recorded **382 passed, 7 skipped in 66.54 seconds**, with zero failures/errors. Frontend **50 passed**, TypeScript, both production builds, lint and `make check-api-contracts` passed. The configured isolated 5173 browser selected one actual TrustGraph chunk, froze verified evidence, then read the exact Atlas passage through Chat’s current-corpus picker with a verified citation and explicit unchanged-ontology warning. Screenshots are `docs/screenshots/trustgraph-selected-import.jpg` and `docs/screenshots/trustgraph-source-chat.jpg`. The final main-model browser check returned the correct Payroll ownership/classification answer with two resolved citations and two ontology triples; main scope and ontology remain unapproved. See `docs/browser-continuation-evidence.json` and `docs/screenshots/ontology-chat-results.jpg`.

The source identity for that continuation is **ae9b5c7**. The current pass belongs to the commit containing docs/release-manifest.json; resolve its actual hash after commit using `git log -1 -- docs/release-manifest.json`. Initial a7cb630/280-pass and c7f1eab recovery history remain unchanged. No real study, generic TrustGraph completion, remote immutability, model OntologyRAG known-answer success or shared deployment approval is claimed.

### Contract, parity and hostile-source verification pass

All JSON routes now declare typed response contracts. The exporter generates request/response aliases, endpoint operation keys and endpoint-specific results for 13 job routes from their server-declared job kinds. The client no longer accepts an arbitrary result generic. Stable DTOs reject undeclared fields; extensible engine diagnostics retain JSON-valued extensions. Exact report/job/revision comparisons caught boolean coercion and now preserve booleans, integers/floats, explicit nulls, omitted fields and raw diagnostics. This closes the request-only generation gap.

`docs/dashboard-export-evidence.json` records nine persisted registered-task outcomes, paginated API/CSV/JSON identity parity and six actual-browser task/phase comparisons. The fixture retains four generation errors and separate D pre/post records; its only review is expressly simulated request-changes, with no publication. Full sealed-payload checks exposed a pre-existing export timestamp/metadata mismatch. Export schema v2 preserves exact original records in `items`, with project context, source artifact and `stored_at` in a separate `provenance` map. Model/registered inline seals remain valid. Original scripted `demo-v1` records authenticate through their existing artifact SHA-256; no inline digest is backfilled and no immutable artifact is rewritten. Independent HTTP regressions first reproduced new demo job/export failures, then **2 passed in 0.78 seconds** after compatible artifact verification was restored.

`tests/integration/test_prompt_boundary.py` uploads hostile instructions, processes/freezes the source and submits a service proposal through the actual ModelClient wire. Only external provider transport and unrelated validation engines are doubles. It verifies system/user separation, absence of tool capability and prompt credential leakage, rejection of five forged authority fields, retained raw output/diagnostics/usage/job linkage and unchanged populated approved refs, records and artifact bytes. The focused fixture **passed in 1.17 seconds**. Its initial failure exposed the concurrent Job error-response type mismatch, not an authorization bypass. This is authority-boundary evidence, not universal model instruction-following or real expert-study evidence.

Current verification is **405 backend tests passed, 7 skipped in 75.87 seconds, and 59 frontend tests passed**. TypeScript, both production builds, lint and OpenAPI drift checks passed. Evidence: research/results/response-contracts/backend-final.xml and .log; JUnit records 412 cases, zero failures/errors and 7 skips (one opt-in TrustGraph read and six separately exercised PostgreSQL checks). The run emitted 3168 warnings. This result is separate from the historical ae9b5c7 count above. The plan's standalone full workflow acceptance and pinned-host smoke are both met; another complete mutation/accessibility matrix inside the native host is not a required extension. Strong shared identity, publisher/evaluator OS separation, organizational permissions and all real study observations remain gated. **No real study is approved.**

The last collection-contract audit found four unbounded discovery responses. Task registrations, TrustGraph preparations/receipts, review timers and chunk hints now page at default 50/max 200. The TrustGraph inventory shares one cursor across both arrays; chunk cursors bind the complete provenance snapshot and reject drift with 409. The UI combines pages before exposing recovery/selection actions. Four backend regressions were observed failing, then passed; 20 focused compatibility cases passed. Generated contracts and all 59 frontend tests/builds include the new pagination behavior.

The same audit found that competency-question IDs were silently ignored. The proposal service now honors unique current IDs as generation/retrieval focus, treats empty selection as all, and rejects duplicate/unknown IDs before a model call or candidate write in both modes. All frozen mandatory questions/tests remain in the review bundle. Six regressions (five initially failing) passed after the fix; the combined selection/backend-review check passed 10 cases. Neither correction changes study authorization.

Final local completion audit rechecked all 70 requirements. No additional necessary local implementation was identified after these fixes. Seeded OntologyRAG remains a recorded quality limitation, not an external approval gate or a claimed successful answer: corrected seed terms were selected but the pinned small model emitted no ownership relationship. No remaining software defect was demonstrated by that trace; model tuning/replacement is not an added software acceptance threshold (plan lines 852 and 864). Required shared deployment/OS identities and real domain/evaluator/participant work remain gated. The source identity is the commit containing docs/release-manifest.json. The final post-pagination scan checked 276 files against 18 known secret forms with zero findings (research/results/response-contracts/source-scan.json).

### DORA domain and public-source preparation - 1 November 2026

The user selected financial regulatory compliance and contractual obligations between financial entities and ICT third-party service providers, chose obligation modelling as the first test, and explicitly approved the source-preparation plan. [Domain scope](domain-scope.md) now records that selection separately from institutional sign-off and application activation. [The modelling specification](dora-modelling.md) defines the concepts/relations, requirement coverage, six development question families, source-fidelity checks and unresolved interpretation.

[The public packet](../research/corpora/dora-v1/README.md) retains five official English documents in nine original representations and 44 complete article/template/context extracts, with classification, edition, date bases, retrieval URLs/timestamps, SHA-256 and exact selectors. Ruling: use official structured XHTML for regulation extracts because register PDF layout extraction omitted rotated text; retain original PDFs where obtained and the complete official XHTML for 2025/532, whose Publications Office PDF request returned no representation. This preserves source content without manufacturing a PDF. The exact successful HTTPS retrieval endpoints are retained. Ruling: this is a frozen source/design packet, not a candidate or runtime adaptation; preserve synthetic-only admission and label all legal documents public.

Fresh verification: the offline checker passed for 5 documents, 9 representations, 44 source-matched extracts and 56 file hashes. Three disposable negative controls rejected an altered original, an altered extract, and an altered extract with a correspondingly changed manifest hash. An initial negative-control command accidentally resolved the virtual-environment symlink to the base interpreter and failed on missing `pypdf`; that result was discarded, the command corrected, and the specific expected integrity errors verified. Local Markdown link/path checks, Ruff for the packet verifier, and `git diff --check` passed. DORA Article 30 pages 52-53, the register's rotated table page 24 and ESMA's answer page 2 were visually inspected. Poppler emitted font-cache permission warnings on two renders, but produced readable inspected output. Detailed evidence is in [DORA source verification](dora-source-verification.json).

The independent read-only review found no actionable findings and separately checked all 43 XHTML extracts against source XML text, including nested lists, conditions, exceptions and table cells. This is source-preparation evidence, not legal endorsement or Jena/OntoCheck execution. No full application suite, model call, database mutation, approval, publication, experiment or participant study ran. The existing model-comparison and multi-LLM verification edits were preserved; no credentials or account billing were changed.

### Repository organization cleanup - 1 November 2026

The user requested a tidier project and removal of unnecessary files. The root README now provides setup, the publication workflow and a repository map; its detailed instructions are retained in `docs/workflow.md`. `docs/README.md` indexes current guides, domain/research material and verification. Nine dated reports moved to `docs/evidence/`, and two completed implementation records joined `docs/archive/`; links and contributor placement guidance were updated. No application modules, contracts, feature controls or source documents were deleted.

The artifact audit found no byte-identical tracked-file duplicates. Removed exactly 17 ignored cache/Finder metadata paths containing 153 files: 2,381,588 logical bytes / 2,768,896 allocated bytes (2.64 MiB). Existing application data, model runtimes/budgets, dependencies, serving build outputs, backups, user outputs and sealed research results were retained.

Fresh verification passed: 242 local Markdown links and 11 heading anchors across 45 current Markdown files; 326 protected files matched the pre-cleanup SHA-256 baseline, including application code/configuration, evidence JSON/screenshots, the DORA packet, the original three archived documents and the preexisting model-comparison/verification edits. The DORA checker again passed 5 documents, 9 representations, 44 source-matched extracts and 56 file hashes. Independent review found no actionable issue and confirmed retained workflow text and path-only changes in relocated reports. Patch whitespace checks passed. Original historical archive instructions and release-manifest paths/hashes remain historical rather than being rewritten.

This was documentation organization and disposable-cache cleanup. No full application tests, model calls, migrations, study runs, approvals or publication were performed; existing runtime behavior and history were not changed.

Pre-commit verification repeated the packet integrity check, Ruff for its verifier, and local documentation links/anchors. The staged whitespace check detected trailing whitespace in the original downloaded ESMA HTML; those source bytes remain unchanged to preserve provenance and hashes. Authored files passed `git diff --cached --check -- . ':!research/corpora/dora-v1/originals/'`; this exception is confined to retained official originals.


### Two-agent team development — 2 November 2026

Implemented independent versioned Proposal/Test Generation agents, model-backed declarative test suggestions with frozen configuration and human oracle successor gates, operator-provisioned Argon2 team accounts with revocable sessions/CSRF/project roles, additive migrations and independent API/worker/frontend startup. PostgreSQL and real Mac browser verification passed; local demo, DORA packet and A–D controls remain preserved. The full backend run passed 593 cases with eight optional skips; the final contract/access/migration checks passed 75 focused cases, with two additional repair regressions. Configuration errors suppress credential-bearing input dictionaries. Frontend 64 tests/builds passed. PostgreSQL passed seven cases and seven exact restores. One actual small local-model test-generation attempt was invalid and retained as a failure; controlled comparison detected four mutants without false positives among three valid variants. See [dated verification](evidence/two-agent-team-2026-11-02.md) for commands, evidence, fixes and limits. No paid/remote provider or participant study was used; Ubuntu/repository split/DORA activation remain deferred.


### API-backed generation; retired Qwen setup — 2 November 2026

At the user's request, removed the Qwen installer, launch Make targets and local-daemon benchmark path. The model pin moved unchanged to the archive; existing historical observations, private settings, downloaded files and integration evidence remain preserved. Current setup guides and example profiles use model APIs, including the `test_generation` purpose for the second agent. The controlled benchmark now exercises the OpenAI-compatible API wire with no network/provider calls. Existing generic transport compatibility and the labelled deterministic demo remain available. No new hosted-provider call or budget reset was made.

Verification after API-only cleanup: **608 backend tests passed, eight optional checks skipped in 93.53 seconds** (`/tmp/oe-api-only-backend.log`); focused benchmark/agent tests passed 39 cases. Ruff, TypeScript, OpenAPI reproducibility, Markdown paths and `git diff --check` passed. The archived model pin is byte-identical to the original. No model or paid-provider call was made; generic API compatibility and prior team/approval behavior passed the regression suite.


### Architecture cleanup — 2 November 2026

Separated HTTP transport from application setup into seven cohesive routers, with
shared request envelopes, pagination and request-scoped Studio/authorization
resolution. The existing entry points and generated API contracts remain unchanged.
Job dispatch is separate from lifecycle handling, and dispatch/completion share
one frozen-profile authorization check. Removed the verified-unused TrustGraph
environment-binding helper; the server-owned configuration-file path is retained.
No migrations, new dependencies, data rewrites or publication changes were made.

The [architecture guide](architecture.md) records responsibilities and dependency
direction; the [completed plan](archive/2026-11-02-architecture-refactor.md) records
the incremental scope. New two-app isolation coverage passed before and after
route extraction. Final verification: **609 backend passed, 8 skipped; 64 frontend
passed**. Both UI builds, lint, TypeScript, unchanged OpenAPI contracts, documentation
links and patch hygiene passed. Independent read-only review found no actionable
issues. [Detailed evidence](evidence/architecture-refactor-2026-11-02.md) records
the initial sandbox-related engine failures and their successful rerun with the
required execution permission, dependency warnings, and optional PostgreSQL/live
TrustGraph skips. No paid calls or real study activity were performed.

### OpenAI and Claude API cleanup — 2 November 2026

Reduced active generation to OpenAI and Claude using native bounded HTTPX requests; removed LiteLLM, legacy Ollama settings, OpenCode-specific branches and redundant provider examples. The lockfile drops 21 dependencies. Server-owned authorization, immutable snapshots, explicit failures, generic optional budget reservations and publication gates remain intact; historical evidence and private state are preserved. [Verification](evidence/llm-api-cleanup-2026-11-02.md): 617 backend passed, 8 optional skips; 64 frontend passed; lint, TypeScript, API drift and patch checks passed. Independent review's Claude finish-reason finding was reproduced and fixed. No paid calls; local model configuration remains unconfigured/demo.

### User-authorized OpenAI API test — 2 November 2026

The new `.env` OpenAI credential authenticated successfully and one bounded synthetic `gpt-4.1-mini` request passed through Studio's actual profile/runtime/schema/citation path (HTTP 200; 207 input and 32 output tokens). No retry, publication or private configuration edit occurred. Claude was not tested because no Anthropic key was present; persistent profile configuration remains unset. See [the live verification entry](multi-llm-verification.md#user-authorized-openai-key-check--2-november-2026) and credential-free `.runtime/llm-api-key-test-2026-11-02.json`.
