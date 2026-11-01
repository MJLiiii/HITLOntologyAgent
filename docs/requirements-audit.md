# Full development-plan requirements audit

Authority: `CODEX_DEVELOPMENT_PLAN.md`, full scope and Tasks 1–12. Snapshot: 1 November 2026 after independent review fixes, clean cached reproduction, simulated browser release acceptance and the bounded live TrustGraph engineering smoke. A working demo does not redefine completion of the full plan.

The matrix maps all **70 checkbox requirements** in original order and all **56 distinct named test functions**. Equivalent behavior in consolidated modules counts; example filenames do not mandate empty folders. A test definition is evidence of coverage, not historical red/green. Root executed the clean application suite after the review corrections: **278 passed, 9 skipped** in 124.44 seconds, plus **36 frontend tests passed**; the JUnit record and browser report are identified below. This records that tested snapshot, not a blanket pass for later integration edits or a committed final source freeze.

Statuses: **I** implemented with relevant source/test evidence in the stated scope; **P** partial; **M** missing engineering; **V** final/runtime verification not established; **G** external data/access/decision gate; **N** contextual non-applicability. Combined statuses preserve the distinction between implemented controls and missing study/deployment outcomes.

Implemented engineering now includes bounded model generation/repair, versioned scope/seed/mappings, isolated PDF ingestion, real-model A–D with immutable D review linkage, evaluator/allocation/timing and paired-task bootstrap helpers, a ten-check Jena/OntoCheck RDFS benchmark bridge, actual host mount/read, simulated browser publication/history, and SQLite/PostgreSQL recovery. Clean cached installation/startup, full applicable application checks, byte-identical JAR builds and a staged-source secrets review have execution evidence. The live TrustGraph v4 smoke produced four ordinary-extraction statements and eight seed-guided ontology statements with exact source/chunk reconciliation. Ordinary GraphRAG answered the known ownership question correctly; the ontology-guided answer could not determine the owner and failed that known-answer check. The adapter remains review-ineligible and inactive: no generic terminal processing API, approved pre-ingestion seed binding or automatic external corpus activation is established. Remaining full-plan work includes durable application integration of that provider, general real-study task registration, independent evaluator deployment, approved real tasks/oracles/participants and observed study results. The user explicitly confirmed that **no real study is approved**. Source Git is initialized; the first consolidated engineering commit and final source freeze are pending, and no historical milestone commits are invented.

## Focused review findings

`tests/integration/test_backend_review.py` independently exercises mapping-only evidence withdrawal outside the proposal corpus, scope changes during model generation, overlapping active timers and time accrued after a linked human decision. The mapping case was reproduced red and then passed after root bound mapping evidence/corpus/decision references. The scope test explicitly asserts that its concurrent scope change committed; it reproduced a successful old-context proposal before the fix. Timing tests reproduced 201 instead of 409 for overlap and 30 instead of 10 seconds after a decision. Root fixed all four cases: mapping-only citation integrity, frozen context comparison, cross-revision/project active timer exclusion and decision-time ledger cutoff. All four focused regressions independently passed in 1.30 seconds; this does not certify the full suite. No backend fix was silently attributed to source inspection.

PDF source/derived-text/report references are immutable and hash-checked; page offsets are validated by the extractor before ingestion. Review found no additional demonstrated PDF lineage defect. Same-account direct filesystem mutation remains outside the application-auth boundary.

A later independent release review found three additional defects: first ingestion could reactivate a withdrawn source; inherited string trimming changed RDF literal lexical whitespace; and automatic repair selected competency questions by a `CQ-` name prefix instead of frozen identities. Root fixed all three. Independent focused verification passed **five cases in 1.88 seconds**, covering withdrawal before/after ingestion, literal add/delete round-trip, arbitrary frozen question IDs with unrelated diagnostics excluded, and the existing repair budget. Review used temporary stores and created no approvals. The current review found no further demonstrated blocker within trusted loopback scope; it does not certify shared identity, OS deployment separation, model semantic quality or real-study readiness.

## Checkbox trace


### Task 1 — Upstream integration and approval boundary

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 1.1 / 912 | Exact versions, digests, licenses and aligned engines | **I/P.** Exact engine/SDK/source pins, image digests and license records exist in infra/versions.lock.yaml, uv.lock and infra/portal/source-pins.json. Actual pinned host/control and bounded graph/ontology dataflows ran. Compatibility is evidenced for those synthetic configurations; generic external-provider application integration remains partial. |
| 1.2 / 913 | Resolve OntoCheck metric integration and delimit benchmark reuse | **I/P.** Pinned metric allowlist, reviewed correspondences and offline edge cases are verified. The executable benchmark bridge agrees with direct Jena on all ten frozen RDFS checks; TODO-ONTOCHECK-02 is satisfied only for that admitted development subset, not published OWL suites or independent held-out study. |
| 1.3 / 914 | Unchanged template, real host registration/mount/reload/theme/read | **I/P.** Unchanged official template and Studio mount/unmount/remount, theme, hard reload and authenticated grounded read are recorded in docs/portal-smoke.md and infra/portal/smoke-evidence.json. Separate standalone browser release/error/keyboard acceptance is recorded in docs/browser-acceptance.md; this is not complete shared-host identity or accessibility certification. |
| 1.4 / 915 | Ingestion/status/provenance/GraphRAG and seeded Ontology RAG smoke | **P.** Actual v4 processing produced four ordinary and eight seeded ontology statements with exact chunk/source reconciliation. Ordinary GraphRAG answered correctly; the ontology-guided known-answer check failed. No generic terminal success/error API, approved pre-ingestion seed binding or automatic corpus freeze exists; adapter review eligibility remains false. |
| 1.5 / 916 | Agent/native editor cannot alter approved state | **P.** Service HTTP publication is denied; candidate changes preserve canonical Git/artifact state. Native JWT is rejected by Studio. A genuine native-editor mutation/unchanged-canonical-store exercise and publisher OS isolation remain open. |
| 1.6 / 917 | Verified identity bridge or documented local mode | **I/G.** Loopback bootstrap/cookie local mode is implemented and actually exercised in browser; native TrustGraph JWT is not a Studio human session. Shared membership/identity approval remains externally gated. |
| 1.7 / 918 | Actual template build and recorded browser plugin smoke | **I/P.** Actual unchanged template/portal and Studio builds plus host mount/read/theme/reload smoke have retained evidence. Standalone full release/browser checks and 36 frontend tests passed. Full host acceptance for every mutation/view remains narrower than that standalone evidence. |
| 1.8 / 919 | Commit integration milestone | **P/V.** Source Git is initialized; this implementation is prepared for the first consolidated engineering commit. The original separate milestone commit history does not exist and is not fabricated. |

### Task 2 — Domain and foundation

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 2.1 / 929 | Accepted domain before activating Deloitte work | **I/G.** Synthetic scope decisions, versioned scope upload and unselected-domain publication gate exist. Signed Deloitte domain/task selection is genuinely external and has not been invented. |
| 2.2 / 930 | Four named foundation/scope tests | **I.** Foundation tests and test_unselected_domain_blocks_publication cover the four named behaviors under local identity. |
| 2.3 / 931 | Tested artifacts, models, auth/settings and migrations | **I.** Artifact/model/auth/schema/migration checks are included in the clean passing application suite. Six separately executed live PostgreSQL cases verify migration, concurrency and recovery. Historical red/green for every original checkbox is not claimed. |
| 2.4 / 932 | All requested Make targets with pinned setup | **I.** All requested Make targets and pinned Python/UI/engine setup exist. A fresh application copy installed locked dependencies from caches without copied environment, data or credentials; Java/browser builds, migrations and clean make demo startup passed. This is cached reproduction, not a cold-network install. |
| 2.5 / 933 | Migrate/lint/checks and dependency-aware readiness | **I.** Clean migration, lint and API drift checks passed. Clean make demo reported real Jena/OntoCheck/database available, optional model/TrustGraph/shared auth unconfigured, and an unapproved synthetic project. Missing mandatory dependencies still return 503; clean suite passed 278 with 9 explicit skips. |
| 2.6 / 934 | Commit foundation | **P/V.** Source Git is initialized; this implementation is prepared for the first consolidated engineering commit. The original separate milestone commit history does not exist and is not fabricated. |

### Task 3 — Deterministic proposals and revisions

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 3.1 / 944 | Named diff/literal/delete/blank-node/stale tests | **I.** Named-triple ordering, datatype/language, exact literal whitespace, missing deletes, blank-node rejection and stale revision tests passed in the application suite; the whitespace add/delete regression also passed independent focused review. |
| 3.2 / 945 | Normalization, operations, manifests and optimistic concurrency | **I/P.** rdf.materialize, canonical representation, immutable bundle manifests and If-Match revisions implement the admitted named-triple RDFS profile. General blank-node/OWL editing remains deliberately unsupported. |
| 3.3 / 946 | Candidate/revision cannot change approved artifact/ref | **I.** test_agent_candidate_edits_do_not_change_approved_ref_or_bytes checks service-created and revised candidates against exact approved bytes and Git ref. |
| 3.4 / 947 | Focused checks, API generation, readable diff/manifest | **I/P.** Readable revision diffs/manifests and reproducible generated OpenAPI request TypeScript exist. Response view models remain hand-owned; full generated response client contracts remain partial. |
| 3.5 / 948 | Commit deterministic proposals | **P/V.** Source Git is initialized; this implementation is prepared for the first consolidated engineering commit. The original separate milestone commit history does not exist and is not fabricated. |

### Task 4 — Ingestion, retrieval and evidence

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 4.1 / 958 | Fake gateway/contracts and evidence/scope tests | **I.** Real/fake TrustGraph contracts test server-selected workspace, upload versus processing, exact quotes/hashes, wrong scopes, unresolved sources and source/result bounds. |
| 4.2 / 959 | Distinct ingestion phases, leases, snapshots, evidence and caps | **I/P.** Durable local jobs/leases, separate upload/ingestion/corpus states, 20 MiB uploads, bounded isolated PDF extraction and page/chunk lineage are verified. Withdrawn sources cannot be reactivated by ingestion. Generic external completion and durable provider-receipt activation remain incomplete; leases do not imply general replay safety. |
| 4.3 / 960 | Real adapter using verified methods/raw provenance | **I/P.** PinnedTrustGraphGateway uses the actual 2.11.1 SDK, preserves raw graph/literal provenance and rejects unresolved mappings. The bounded live slice now reconciles exact registered source/chunk bytes, but its adapter remains review-ineligible. A generic terminal completion API and approved pre-ingestion seed/config binding remain unsupported; application corpus routing remains local. |
| 4.4 / 961 | Live contract tests for ingestion, GraphRAG, trace and denial | **P.** Controlled-wire contracts and a real bounded graph/ontology smoke establish retrieval and exact source/chunk reconciliation for the inspected synthetic pipeline. The complete generic upload→terminal-success/error→eligible-corpus lifecycle, restart durability and deployed multiuser denial matrix remain unverified. |
| 4.5 / 962 | Commit versioned TrustGraph evidence | **P/V.** Source Git is initialized; this implementation is prepared for the first consolidated engineering commit. The original separate milestone commit history does not exist and is not fabricated. |

### Task 5 — Proposal agent and bounded repair

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 5.1 / 972 | Evidence/tool/base/budget/read-only named tests | **I/P.** Evidence/operation/capability/base/read-only and repair-budget checks passed. Browser acceptance rendered malicious source markup literally without an injected script. That browser safety probe does not replace a full hostile-document-through-model behavioral fixture, which remains narrower than the schema authority rejection test. |
| 5.2 / 973 | Bounded model, provenance and feedback-driven successor repair | **I/P.** Actual Ollama generation has a total deadline, output bound, evidence-enum grammar, raw failure/usage audit and a two-attempt repair budget. Frozen context changes are rejected; repair reads the verified frozen question IDs rather than a naming convention. Actual IRI/materialization failures are retained. Scope remains synthetic named triples. |
| 5.3 / 974 | Failure diagnostics and retry-safe logical revisions | **P.** Immutable generation/failure/outcome records, job links and request idempotency exist; materialization is checked before a generation is recorded as completed. Expired worker leases fail rather than blindly retry. Crash-after-generation logical recovery/partial-result job linkage is not comprehensively proven. |
| 5.4 / 975 | Focused tests plus optional live proposal and manual inspection | **I/P.** Real Qwen3:1.7b grounded browser question/follow-up succeeded. A bounded A–D model smoke returned a duplicate triple and honestly retained four generation errors; this verifies failure handling, not model quality or a successful generated ontology. |
| 5.5 / 976 | Commit proposal/repair agent | **P/V.** Source Git is initialized; this implementation is prepared for the first consolidated engineering commit. The original separate milestone commit history does not exist and is not fabricated. |

### Task 6 — Jena and OntoCheck

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 6.1 / 986 | Required success/failure/unsafe-input engine tests | **I.** Real engine inference/SHACL/error/timeout/unsafe-query tests and real-engine HTTP unsupported-publication regression exist. |
| 6.2 / 987 | Integrity, closure, constraints, expectations and resource limits | **I/P.** Jena closure/constraints/expectations and OS-isolated workers enforce admitted profile, memory/time/output/network/file limits. macOS sandbox evidence exists; equivalent deployment isolation on another OS remains a platform gate. |
| 6.3 / 988 | OntoCheck edge cases, mapping identity and reproducibility | **I.** Pinned OntoCheck tests cover missingness, collisions, paths, raw reproducibility, mapping identity and approved nonempty correspondences without rewriting RDF. |
| 6.4 / 989 | Controlled export, mappings, raw/missing results and review gate | **I/P.** Frozen scope questions, reviewed mapping configuration/artifacts, raw/normalized scores, common base/candidate inputs and exact mandatory report gates are implemented. Withdrawn mapping-only citations are now a focused eligibility regression. General namespace/import/benchmark expansion remains gated. |
| 6.5 / 990 | Broken candidate → corrected successor with unchanged base | **I.** tests/integration/test_real_engine_workflow.py exercises failing candidate→corrected successor with reference bytes unchanged, plus unsupported construct publication denial using actual engines. |
| 6.6 / 991 | Maven/engine/raw-report verification, benchmark TODO boundary | **I/P.** Real Jena/OntoCheck/PDF and ten-check benchmark bridge tests passed in the clean suite. Three final JAR builds (main, repeat, clean) were byte-identical after fixed timestamps, forced unshaded-JAR recreation and notice appending. Broad OWL/published-suite equivalence and independent held-out deployment remain outside the verified bridge. |
| 6.7 / 992 | Commit engine integration | **P/V.** Source Git is initialized; this implementation is prepared for the first consolidated engineering commit. The original separate milestone commit history does not exist and is not fabricated. |

### Task 7 — Synthetic tests and oracle control

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 7.1 / 1002 | Constrained-code/split/negation/oracle/sentinel tests | **I.** Schema-only specs reject executable Python/held-out split, distinguish missing data from negation and require oracle review. An explicit adversarial attempt to replace mandatory tests is rejected. |
| 7.2 / 1003 | Schema-only generator, fixtures, Jena validation, provenance, new bundle | **P.** Four deterministic test suggestions, evidence provenance, human oracle decisions and successor bundles exist. They are bounded engineering fixtures, not a general candidate-aware model test generator or independent oracle author. |
| 7.3 / 1004 | Positive/negative/missing/boundary cases in trusted harness | **P.** Positive/negative/missing/boundary fixture specifications and controlled Jena harness exist. A full real-run matrix of all accepted generated fixtures and richer contradictory/regression cases is still incomplete. |
| 7.4 / 1005 | Commit synthetic/oracle implementation | **P/V.** Source Git is initialized; this implementation is prepared for the first consolidated engineering commit. The original separate milestone commit history does not exist and is not fabricated. |

### Task 8 — Human review and publication

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 8.1 / 1015 | Approval/digest/edit/stale/concurrent/idempotent tests | **I/P.** Exact approval/bundle/report binding, stale-base/revision, candidate-head preservation, concurrent publication and idempotency tests exist. Broader shared-user authorization is not supplied by local tests. |
| 8.2 / 1016 | Crash boundaries, no rewrites/doubles, unexpected ref blocks | **I.** All four crash checkpoints and repeat reconciliation are tested locally and on live PostgreSQL; independent Studio instances compete through PostgreSQL locking and Git CAS, with exactly one release. |
| 8.3 / 1017 | Native editor denial and source withdrawal/history | **P.** Public withdrawal/history, mapping-only citation integrity, withdrawn-source ingestion denial and service/native-token denial are verified. A live native editor mutation with unchanged canonical store and deployed publisher OS separation remain open. |
| 8.4 / 1018 | Assessment binding, mapping change and error gate | **I/P.** Assessment error/timeout/unsupported/not-run gates and changed mapping reassessment tests exist. The independent mapping-only withdrawal regression exposed a gap; root implemented explicit mapping evidence/corpus/decision binding and the focused regression passed. |
| 8.5 / 1019 | Review policy, exact digest, sole writer, durable recovery/outbox | **I/P.** Local explicit human decisions, exact bundle/report gates, sole API publisher and durable reservation/CAS/reconciliation exist. Optional mirror/outbox is absent; same-account filesystem access is not isolated publisher authority. |
| 8.6 / 1020 | Tests, immutable restore, mirror failures, complete trace | **I/P.** SQLite and six live PostgreSQL restore exercises preserve rows/artifacts/Git; the main-store restore matched 20 rows and zero approved refs, without inventing persistent approvals. A disposable actual-browser test created two expressly simulated releases and read the historical release with complete provenance. No mirror exists; real expert acceptance remains external. |
| 8.7 / 1021 | Commit publication milestone | **P/V.** Source Git is initialized; this implementation is prepared for the first consolidated engineering commit. The original separate milestone commit history does not exist and is not fabricated. |

### Task 9 — Six-view Studio plugin

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 9.1 / 1031 | UI processing/diff/error/stale/edit/auth tests | **I.** All 36 frontend tests across 12 files passed, covering processing/errors/stale revisions/diffs/auth and separate review/publication actions. Actual-browser checks additionally exercised loading/error states, stable failed-CQ IDs and mobile navigation focus. |
| 9.2 / 1032 | Connected features/generated contracts/pending and mirror lag | **I/P.** Six connected views, source/scope/seed/mapping flows and generated request contracts exist; response models are hand-owned. Real portal mount/read uses a split local proxy and separate Studio unlock; no shared host identity or mirror state is claimed. |
| 9.3 / 1033 | Distinct logical/fitness/mapping/unsupported displays | **I/P.** Strict/approximate/coverage/unsupported results are distinguished; mapping proposals and explicit human mapping decisions are implemented. Backend tests enforce reruns. Final actual-host UI acceptance across the complete mapping workflow remains verification work. |
| 9.4 / 1034 | Full browser ingest/fail/revise/accept/publish/history/accessibility | **I/P.** Actual Chrome acceptance in disposable data covered upload/process/freeze, deliberately failed real Jena CQ, repair/revalidation/assessment, separate simulated acceptance/publication twice, and historical approved-version read. Keyboard/mobile, literal malicious-source rendering and invalid-session recovery passed. These are engineering fixtures, not real expert decisions or a complete WCAG audit. |
| 9.5 / 1035 | Actual build/tests and pinned-portal smoke | **I/P.** TypeScript, both production Vite builds and 36 frontend tests passed; actual pinned-host template/Studio mount/read/theme/reload and separate standalone full workflow acceptance are retained. A complete mutation/accessibility matrix inside the native host is not inferred from separate surfaces. |
| 9.6 / 1036 | Commit unified Studio | **P/V.** Source Git is initialized; this implementation is prepared for the first consolidated engineering commit. The original separate milestone commit history does not exist and is not fabricated. |

### Task 10 — Baselines, records and dashboard

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 10.1 / 1046 | Ten named condition/isolation/missingness tests | **I.** Scripted and actual ModelClient A–D tests enforce common frozen initial/evidence packets, equal B/C budgets, no B diagnostics, failed-CQ-only C feedback, identical C/D physical calls and missingness. D post-review linking is tested through normal workflow. |
| 10.2 / 1047 | Held-out access, RQ3 controls and RQ4 timing/censoring | **I/P/G.** External evaluator CLI checks credentials/path separation/hash-bound common packets; RQ3 allocation fixes equal display digests and forbids repeated task exposure; RQ4 helpers account active time/censoring. Production evaluator OS identities/mounts and real independent oracles remain external. Decision-cutoff/overlap regressions now pass after root fixes. |
| 10.3 / 1048 | Frozen conditions, usage, scoring, pseudonyms and exports | **I/P.** Sealed model records, prompts/raw outputs/usage, frozen development suite, D lineage and flat/nested exports are implemented. Evaluator schemas/protocol and pseudonymous allocation helpers exist. Registered generation protocol remains one synthetic task; real study task/protocol registration and verified live model-weight identity remain incomplete. |
| 10.4 / 1049 | Known TP/FP/FN/missing toy outcomes and retained failures | **I.** Known TP=FP=FN=TN=1 table asserts precision/recall/F1/accuracy and exact denominators; missing engine/model cases remain scheduled. Provider-missing usage and unobserved human time stay null. |
| 10.5 / 1050 | A–D pilot, reproducible exports and matching dashboard | **I/P.** Scripted A–D and genuine bounded model smoke retain JSON/CSV/hash manifests, including rejected duplicate edits. Browser acceptance verified the configured-model selector and limitations but deliberately created no experiment observations. Full dashboard-to-export totals comparison remains verification work. |
| 10.6 / 1051 | Commit experiments/dashboard | **P/V.** Source Git is initialized; this implementation is prepared for the first consolidated engineering commit. The original separate milestone commit history does not exist and is not fabricated. |

### Task 11 — Real study and analysis

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 11.1 / 1061 | Pilot difficulty/oracles/budgets/review timing and amendments | **P/G.** Synthetic engineering pilot exercised model schema/failure boundaries. Real-domain task difficulty, expert timing, oracle clarity and pilot amendments require actual agreed tasks/participants; no such observations are invented. |
| 11.2 / 1062 | Freeze held-out/conditions/allocation/rubric/exclusions/analysis | **I/P/G.** Frozen evaluator Pydantic schemas, hash-bound outputs/packets, allocation seed and protocol artifacts are implemented. Real oracles/mappings/rubric/exclusions/order/consent and deployment-isolated mounts are not present or falsely marked frozen. |
| 11.3 / 1063 | Agreed tasks/replicates, retained failures/pre/post and timed sessions | **G.** No confirmatory study has run. Actual-model infrastructure and D review linkage exist, but agreed 6–10 task study, independent replicate protocol and genuine human observation collection remain external work. |
| 11.4 / 1064 | Known-answer paired analysis, task resampling, tables/plots | **I/P/G.** Task-level paired analysis and optional seeded percentile bootstrap are implemented with known-answer, replicate-nesting, missingness, minimum-task and no-variation checks (research/analysis/bootstrap-policy.md). The task remains the resampling unit; no interval was invented for the single synthetic pilot. Real pseudonymous observations, independence review and empirical study tables/plots remain gated. |
| 11.5 / 1065 | Commit permitted research artifacts | **P/G.** Engineering protocol/analysis code is prepared for the first consolidated source commit. There are no approved completed real-study artifacts to commit, and engineering fixtures are not a preregistered completed study. |

### Task 12 — Reproduction and handoff

| ID / plan line | Requirement | Status and current evidence / limit |
|---|---|---|
| 12.1 / 1075 | Clean locked setup and demo without hidden state | **I/P.** Fresh-copy locked Python/OntoCheck/npm installation, Java/browser builds, migration, lint/API checks and make demo startup passed without copied .env/.data/runtime credentials. Package caches were explicitly used. Three final JAR builds agree byte-for-byte; initial source commit and a final committed-source reproduction remain pending. |
| 12.2 / 1076 | One full applicable suite on frozen release, explicit skips | **I/P/V.** Clean application suite passed 278 with 9 explicit skips in 124.44 seconds; 36 frontend tests, TypeScript, builds, lint and API drift checks passed. Skips cover optional SDK/live TrustGraph and six PostgreSQL cases, the latter separately executed successfully. Later provider edits and the final committed source freeze require their own checked identity. CI is authored/pinned, not GitHub-executed. |
| 12.3 / 1077 | Backup/restore with hashes, approved head and audit links | **I.** Main SQLite/artifact/Git backup/restore passed with 20 workflow rows and no approved ref; no persistent main-store approval was fabricated. Six separate PostgreSQL 17.6 cases verified coordinated restoration of actual synthetic publication refs, records and bytes. Session keys were excluded and the owned test container removed. |
| 12.4 / 1078 | Secrets/private data/untracked artifacts and bypass checks | **I/P/V.** Independent audit of the then-staged 197 files found no private/runtime credentials, dependencies or real reviewer data; 12 known secret forms had zero matches and seven screenshots contained only synthetic UI. Runtime/results/original outputs remain excluded. Later additions need final scan/restaging; live native-editor bypass proof and deployed OS isolation remain open. |
| 12.5 / 1079 | Complete handoff with truthful unresolved TODOs | **I/P.** Handoff now includes cached reproduction, real startup, reproducible JAR, full application checks, simulated browser releases, benchmark subset and bootstrap policies, recovery evidence and truthful limits. Generic live provider activation, real-study results and the initial committed release identity remain unresolved. |
| 12.6 / 1080 | Commit final handoff | **P/V.** Source Git is initialized and a consolidated initial engineering commit is being prepared. No first commit/release tag/final frozen source identity is claimed yet; no twelve-step historical milestone sequence is fabricated. |

## Integration register and milestone gates

| Register | Current disposition |
|---|---|
| TODO-TG-01 | Pinned host/control, unchanged template and bounded graph/seeded-ontology dataflow compatibility executed. This is an inspected synthetic configuration, not unrestricted provider/application lifecycle support. |
| TODO-TG-02 | Default export/globals/manifest and actual mount/unmount/remount/theme/reload/read verified. Separate standalone release/keyboard/mobile acceptance passed. Local split proxy and separate Studio session remain explicit; shared identity and complete native-host workflow acceptance remain open. |
| TODO-TG-03 | Actual upload/processing and bounded output observation ran, but generic terminal success/error status is unavailable. Missing processing records still cannot imply success; durable application receipt/restart integration and automatic corpus activation remain open. |
| TODO-TG-04 | Contract tests preserve exact registered text/chunk/graph bytes and raw fields. Live bounded GraphRAG produced four statements and reconciled exact source/chunk provenance. General extraction URI/page/subgraph coverage and automatic provider activation remain partial. |
| TODO-TG-05 | Actual v4 seed-guided extraction produced eight statements with source/chunk lineage, but the ownership answer failed its known-answer check. The diagnostic seed hash was observed after ingestion, not approved beforehand. Generic terminal completion and automatic provider activation remain unsupported; provenance does not certify answer or ontology correctness. |
| TODO-TG-06 | Local canonical publisher/CAS and native-token denial verified. Native-editor mutation plus canonical-store invariance and deployed OS authority remain open. |
| TODO-JENA-01 | Verified for admitted named-triple RDFS/SHACL/ASK/SELECT profile and tested local OS sandbox. Not OWL 2 DL completeness or cross-platform sandbox proof. |
| TODO-ONTOCHECK-01 | Verified pinned offline metrics and reviewed correspondences within admitted workload grammar; unsupported inputs remain explicit. |
| TODO-ONTOCHECK-02 | Verified only for the pinned constrained_plan/Jena RDFS Simple development bridge: ten of ten frozen answers agree. Published XRD/MatProc OWL/import/hop semantics, other task types and independently deployed held-out evaluation remain unsupported/unverified. |
| TODO-DL-01 | Optional and explicitly deferred; unsupported constructs fail closed. |
| TODO-ORG-01 | External signed domain/rights/model-hosting/experts/consent and deployment agreement are absent; synthetic/public scope remains enforced. |

| Milestone | Full-plan exit status |
|---|---|
| M0 Scope and compatibility | Partial: actual host and bounded graph/seeded-ontology smoke work; generic ingestion lifecycle and an agreed real domain/protocol remain missing. |
| M1 Deterministic vertical slice | Implemented and tested locally, including clean application checks, real-engine failing/corrected successor, preserved base and simulated browser releases. Final source commit identity remains pending. |
| M2 Grounded agent loop | Partial: actual model chat/proposals/repair, local isolated PDF and bounded external source reconciliation work; durable live TrustGraph application corpus activation remains open. |
| M3 Human-controlled release | Verified for local synthetic scope, including live PostgreSQL recovery and two simulated disposable browser releases. Shared identity, native-editor and publisher OS boundaries remain open. |
| M4 Pilot/frozen experiment | Engineering infrastructure and retained model failures exist; optional paired-task bootstrap is implemented. Real-task protocol, independent evaluation and actual human pilot are not complete. |
| M5 Study/thesis handoff | Not met: real study and empirical analysis/acceptance remain unapproved and absent. Clean cached reproduction and release checks exist; final source commit/freeze remains pending. |

## Endpoint inventory against section 7.1

All paths below have `/api/v1` unless shown otherwise. Present means source implementation, not shared membership or real-domain acceptance. Local operators can access every project; per-project object lookup prevents cross-project reference confusion but is not a multi-user role model.

| Required endpoint/group | Current evidence and limit |
|---|---|
| POST/projects; GET/projects/{p} | Present; strict demo/unselected domain and current head/corpus/scope. |
| POST/projects/{p}/scope; scope-decisions | Present versioned purpose/questions/ASK oracles/shapes/fixtures; exact human acceptance; only synthetic scope activatable. |
| POST/projects/{p}/documents; ingestions; corpus-snapshots | Present PDF/UTF-8 upload up to 20 MiB; bounded isolated PDF page extraction; separate complete/unsupported/error states and evidence-verified corpus freeze. Application provider remains local. |
| POST/projects/{p}/seed-imports | Present bounded Turtle staging through ordinary validation/review/publication; import is not approval. |
| GET/projects/{p}/versions and /versions/{v} | Present immutable version summaries, triples and manifests. |
| POST/projects/{p}/proposal-jobs; repair-jobs | Present actual model or labelled local demo; two-attempt repair using frozen question identities, frozen contexts and retained failure/outcome audit. General selected-question subset handling should not be inferred merely from the request field. |
| GET/projects/{p}/proposals and /proposals/{id}/revisions/{r} | Present readable diff/evidence/checks/history/eligibility. |
| POST/projects/{p}/proposals/{id}/revisions | Present immutable successor with If-Match/base/scope/pending guards. |
| POST/projects/{p}/test-generation-jobs; test-oracle-decisions | Present bounded deterministic suggestions and explicit oracle decision/new bundle; no generated executable code or independent-study oracle claim. |
| POST/projects/{p}/validation-jobs; assessment-jobs | Present actual isolated Jena/OntoCheck with frozen questions/mappings/config and mandatory reports. No caller-selectable held-out split. |
| GET/projects/{p}/assessments/{id} | Present development reports. External evaluator reports are deliberately absent from API routes. |
| POST/projects/{p}/review-submissions; reviews | Present exact bundle/report/policy, explicit human actions and stale guards. Mapping-only citations now independently guarded. |
| POST/projects/{p}/question-jobs | Present grounded actual-model/read-only local chat, follow-up context, source/ontology indices and candidate/reference/approved labels. |
| POST/projects/{p}/publications; GET/projects/{p}/publications/{id} | Present HTTP 202 response with completed or pending publication state, idempotent reservation/CAS/recovery; PostgreSQL verified. |
| GET/projects/{p}/evidence/{id}; artifacts/{id} | Present scoped exact source/chunk/extraction/hash resolution and verified artifact download. |
| POST/projects/{p}/review-sessions | Present active-event ledger and D outcome integration; independent cutoff/overlap regressions now pass after review fixes. |
| POST/projects/{p}/experiment-jobs | Present demo-v1 and actual model-pilot-v1 on fixed synthetic scope. No real-study/held-out protocol endpoint. |
| GET/projects/{p}/experiments; /experiments/export | Present nested JSON/CSV records with explicit nulls and failures. Sealed original records are separate artifact references; enriched API envelopes are not evaluator seals. |
| POST/projects/{p}/experiments/{run}/proposal; /review-results | Present stage D through normal workflow and append a separate immutable post-review snapshot from a persisted review ID. |
| GET/jobs/{id} | Durable queued/running/succeeded/failed with idempotency/leases; cancellation and general crash-safe generation replay are not implemented. |
| GET/health/live; /health/ready | Root/API aliases, mandatory dependency probes and 503 when unavailable; optional unconfigured integrations are explicit. |

Additional mapping-set/decision/config, source withdrawal, audit, local session and list routes exist. Request types are generated reproducibly from actual OpenAPI; response dictionaries remain manual view models.

## Security and research claim limits

| Boundary | Implemented evidence | Remaining limit |
|---|---|---|
| Human identity | Loopback/private bootstrap, HttpOnly cookie, fragment removal, service/native-JWT denial; standalone and host browser use | Same OS account can read session.key; no approved shared identity/membership integration. |
| Canonical publication | API sole writer, exact bundles, immutable data, CAS/recovery and independent PostgreSQL contenders | Tool-capable same-user processes can write files directly; deployed publisher account/mount separation remains required. |
| Native editor | Separate host API route/proxy and native JWT rejected by Studio | Actual native mutation/unchanged Studio canonical ref test remains open. |
| Evidence/assessment | Artifact/quote/span checks, PDF derivation lineage, mapping citation binding, report/config hash gates | Bounded live source/chunk reconciliation is observed; generic provider lifecycle/automatic corpus activation and organization source governance remain incomplete. |
| Engine confinement | Actual macOS OS sandbox, disabled network, private writable workdir, memory/time/output limits, hostile-input tests | Another OS needs a verified equivalent implementation; grammar/audit hooks alone are not the claim. |
| Hidden evaluation | Separate offline evaluator, private external dirs/credential, file seals, no API held-out request, shared frozen per-task workload | Same-user directories are explicitly not OS isolation; provision separate evaluator identity and inaccessible mounts before study. |
| Study inference | Failure retention, exact denominators, allocation/exposure/time/task-pair helpers and seeded task bootstrap | Paired-task bootstrap code and known-answer tests exist; no real experts, independently approved held-out study, completed real-task schedule or empirical interval/effect claim exists. |
| Recovery | SQLite utility and actual pinned PostgreSQL six-case backup/restore with artifact/Git equality | Actual organization's deployment still needs its own protected backup/recovery rehearsal. |

## Named-test trace

The table preserves the 56 exact backticked function names in the plan, excluding nonfunction fields `test_id` and `test_suites`; source line references were refreshed from current Python AST definitions. Exact means the name exists; Equivalent means another assertion covers the behavior; Partial records narrower coverage. Execution is evidenced separately by the clean 278-pass/9-skip application run and focused/live reports; an exact name does not enlarge a test's scope.

| Required named test | Coverage | Current definition / practical limit |
|---|---|---|

| `test_agent_cannot_change_base_head` | Equivalent | `tests/integration/test_workflow.py:589` (`test_agent_candidate_edits_do_not_change_approved_ref_or_bytes`). Actual service candidate edits preserve exact approved bytes/ref; not an OS filesystem policy. |
| `test_agent_cannot_remove_required_sentinel` | Exact | `tests/integration/test_workflow.py:607`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_agent_cannot_write_approved_ref` | Exact | `tests/integration/test_workflow.py:177`. Service HTTP boundary; not same-user direct file access. |
| `test_artifact_hash_mismatch_rejected` | Exact | `tests/unit/test_foundation.py:13`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_assessment_error_blocks_required_report_gate` | Exact | `tests/integration/test_workflow.py:570`. Parameterized error/timeout/unsupported/not_run blocks review. |
| `test_b_c_share_initial_candidate_and_budgets` | Equivalent | `tests/unit/test_model_experiments.py:65` (`test_model_conditions_share_actual_generation_and_equal_repair_budgets`). Actual model-call contract uses a controlled model; live smoke is separately retained. |
| `test_baseline_a_has_no_repair_feedback` | Equivalent | `tests/unit/test_model_experiments.py:65` (`test_model_conditions_share_actual_generation_and_equal_repair_budgets`). A receives one shared initial generation and no repair. |
| `test_c_d_share_automated_feedback_policy` | Equivalent | `tests/unit/test_model_experiments.py:65` (`test_model_conditions_share_actual_generation_and_equal_repair_budgets`). Identical physical call IDs, histories and outputs. |
| `test_changed_bundle_invalidates_approval` | Exact | `tests/integration/test_workflow.py:212`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_changed_chunk_hash_is_unresolved` | Equivalent | `tests/contracts/test_trustgraph_gateway.py:113` (`test_fabricated_quote_changed_chunk_and_unknown_sources_block_review`). Gateway quote/chunk/source integrity test. |
| `test_conditions_share_frozen_inputs` | Equivalent | `tests/unit/test_model_experiments.py:65` (`test_model_conditions_share_actual_generation_and_equal_repair_budgets`). Frozen evidence/task/initial generation shared across actual model arms. |
| `test_d_pre_post_snapshots_separate` | Equivalent | `tests/integration/test_workflow.py:618` (`test_model_experiment_enters_real_review_and_preserves_pre_post`). Controlled HTTP workflow links persisted human fixture; not a real expert observation. |
| `test_delete_missing_triple_rejected` | Exact | `tests/unit/test_foundation.py:61`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_document_instruction_cannot_grant_tools` | Partial | `tests/unit/test_chat_agent.py:98` (`test_model_cannot_grant_tools_or_change_head`). Rejects schema authority fields; no full hostile-document behavioral model fixture. |
| `test_duplicate_key_returns_same_publication` | Exact | `tests/integration/test_workflow.py:189`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_error_counts_in_scheduled_denominator` | Exact | `tests/unit/test_experiments.py:63`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_evidence_id_outside_context_rejected` | Equivalent | `tests/unit/test_chat_agent.py:103` (`test_proposal_requires_evidence_for_every_change`). Fabricated citations fail; model grammar also restricts evidence enum. |
| `test_expected_shacl_violation_passes_case` | Exact | `tests/test_validation.py:44`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_external_import_is_not_fetched` | Equivalent | `tests/test_assessment.py:79` (`test_remote_imports_are_rejected_without_fetching`). Import admission plus separate OS sandbox network-denial tests. |
| `test_fabricated_quote_blocks_review` | Exact | `tests/integration/test_workflow.py:313`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_generated_python_is_rejected` | Exact | `tests/unit/test_synthetic_specs.py:7`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_grounded_question_is_read_only` | Exact | `tests/integration/test_workflow.py:114`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_held_out_not_in_agent_manifest` | Equivalent | `tests/unit/test_model_experiments.py:84` (`test_only_failed_cq_feedback_reaches_c_and_no_oracles_or_diagnostics_reach_b`). Model prompt boundary plus evaluator/API negative tests; deployed OS isolation remains external. |
| `test_human_edit_needs_new_validation` | Equivalent | `tests/integration/test_workflow.py:218` (`test_stale_revision_returns_409`). Successor has different bundle and no inherited reports/approvals; real-engine successor test is additional evidence. |
| `test_literals_preserve_datatype_and_language` | Exact | `tests/unit/test_foundation.py:41`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_malformed_rdf_is_input_error` | Equivalent | `tests/test_assessment.py:61`; `tests/test_validation.py:94` (`test_malformed_rdf_is_error`). Actual engine error outcomes retained. |
| `test_mapping_change_needs_reassessment_and_review` | Exact | `tests/integration/test_workflow.py:538`. Nonempty reviewed mapping configuration creates a new bundle/rerun requirement. |
| `test_missing_data_is_not_owl_negation` | Exact | `tests/unit/test_synthetic_specs.py:17`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_missing_report_is_engine_error` | Equivalent | `tests/test_validation.py:115` (`test_missing_report_is_error`). Missing subprocess report never passes. |
| `test_named_triple_diff_is_deterministic` | Exact | `tests/unit/test_foundation.py:33`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_native_editor_cannot_modify_canonical_release` | Exact | `tests/integration/test_workflow.py:184`. Local nonexistent mutation route; actual native editor mutation remains untested. |
| `test_new_domain_oracle_needs_review` | Exact | `tests/integration/test_workflow.py:324`. Human fixture decision preserves sentinels; no fabricated independent study oracle. |
| `test_ontocheck_diagnostics_withheld_from_automated_repair` | Equivalent | `tests/unit/test_model_experiments.py:84` (`test_only_failed_cq_feedback_reaches_c_and_no_oracles_or_diagnostics_reach_b`). Controlled model inspects actual contexts; only frozen failed-CQ whitelist reaches C. |
| `test_operation_limit_enforced` | Equivalent | `tests/unit/test_foundation.py:74` (`test_unknown_fields_and_operation_limit_rejected`). Rejects 101 operations at schema boundary. |
| `test_publication_recovers_after_crash` | Exact | `tests/integration/test_workflow.py:273`. Four checkpoints; separate live PostgreSQL fresh-instance recovery also passed. |
| `test_publish_without_human_approval_forbidden` | Exact | `tests/integration/test_workflow.py:170`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_query_service_and_update_rejected` | Equivalent | `tests/test_validation.py:79` (`test_unsafe_queries_are_rejected`). Actual parsed query admission and sandbox confinement. |
| `test_repair_stops_after_two_attempts` | Exact | `tests/integration/test_workflow.py:479`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_required_assessment_matches_approval_bundle` | Exact | `tests/integration/test_workflow.py:304`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_self_revision_b_has_no_automated_feedback` | Equivalent | `tests/unit/test_model_experiments.py:84` (`test_only_failed_cq_feedback_reaches_c_and_no_oracles_or_diagnostics_reach_b`). B context contains neither engine nor answer oracle feedback. |
| `test_shared_mode_rejects_dev_identity` | Exact | `tests/unit/test_foundation.py:28`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_source_withdrawal_blocks_new_publication` | Exact | `tests/integration/test_workflow.py:293`. Direct-status fixture, public mapping-source withdrawal and before/after-ingestion withdrawal regressions preserve source ineligibility. |
| `test_stale_base_returns_409` | Exact | `tests/integration/test_workflow.py:580`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_stale_revision_returns_409` | Exact | `tests/integration/test_workflow.py:218`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_storage_key_cannot_escape_root` | Exact | `tests/unit/test_foundation.py:22`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_subclass_inference_answers_cq` | Exact | `tests/test_validation.py:27`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_synthetic_tests_cannot_target_held_out_split` | Exact | `tests/unit/test_synthetic_specs.py:12`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_timeout_never_passes` | Exact | `tests/test_validation.py:103`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_two_publishers_only_one_advances_head` | Exact | `tests/integration/test_workflow.py:203`. Local concurrent calls; independent Studio instances additionally passed on PostgreSQL. |
| `test_undefined_precision_is_missing` | Equivalent | `tests/unit/test_experiments.py:73` (`test_undefined_precision_is_missing_and_distinct_from_vocabulary`). Zero denominator null; separate known TP/FP/FN/TN table tests nonzero counts. |
| `test_unselected_domain_blocks_publication` | Exact | `tests/integration/test_workflow.py:163`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_unsupported_blank_node_edit_rejected` | Exact | `tests/unit/test_foundation.py:67`. Definition present; clean-suite execution is recorded in the release evidence below. |
| `test_unsupported_construct_blocks_publication` | Exact | `tests/integration/test_real_engine_workflow.py:53`. Actual-engine HTTP regression now present. |
| `test_upload_is_not_processing_complete` | Exact | `tests/contracts/test_trustgraph_gateway.py:53`; `tests/integration/test_workflow.py:242`. Explicit fake/real gateway contract; real completion remains unsupported. |
| `test_workspace_binding_is_server_selected` | Equivalent | `tests/contracts/test_trustgraph_gateway.py:66` (`test_workspace_binding_is_server_selected_and_wrong_scope_rejected`). Bound gateway forbids caller workspace/collection/flow overrides; live multiuser isolation is separate. |
| `test_wrong_inference_fails_case` | Exact | `tests/test_validation.py:37`. Definition present; clean-suite execution is recorded in the release evidence below. |

## Evidence and remaining release work

- `research/results/release-check/clean-backend.xml`: clean-copy application suite **278 passed, 9 skipped**, root-observed wall time 124.44 seconds (JUnit 124.426). Explicit skips require the optional SDK, configured live TrustGraph probe or isolated PostgreSQL server; PostgreSQL's six cases passed separately. `docs/browser-acceptance.md` records **36 frontend tests across 12 files**, TypeScript and both production builds. Clean lint and API drift checks passed. CI is pinned/authored but has not executed on GitHub.
- `research/results/release-check/clean-start.json`: fresh locked installation from caches, with no copied `.env`, `.data`, model runtime or credentials, started via `make demo`; Jena, OntoCheck and database reported available. The synthetic project had three sources, no approved version and no accepted scope. Caches were preparation inputs; no cold-network installation is claimed.
- `research/results/release-check/reproducible-build.json`: main, repeated-main and clean final JAR builds each contain 15,345,914 bytes and SHA-256 `572fd5730cea46f9bab467b61684c4675dfc15f6cccf041076864ef21c013bf3`. Fixed archive timestamps and forced unshaded-JAR recreation made shading reproducible; license/notice resources are appended. This does not settle every upstream redistribution obligation.
- `research/results/release-check/backup-restore.json`: main SQLite/artifact/Git restoration passed with 20 workflow rows and zero approved refs. `research/results/postgres-check/run-20261101/report.json` separately records six real PostgreSQL 17.6 migration/concurrency/recovery cases and six matching coordinated restores, including synthetic publication refs. Session keys were excluded and the owned container removed.
- `docs/browser-acceptance.md`, `docs/browser-acceptance-evidence.json` and screenshots record actual Chrome upload/process/freeze, failed real CQ, repair, validation/assessment, two separate simulated review/publication actions and historical version inspection. Mobile/keyboard, escaped hostile source markup and invalid-session recovery were exercised. All mutations used disposable data; records explicitly say simulated engineering test, and there were zero review-timer or experiment observations. This is not real expert-study data or a complete WCAG audit. Reports retain the engine hash used during that browser run; they are not relabelled as the later reproducible JAR build.
- `docs/browser-smoke.md` records actual local-model grounded chat/follow-up. `research/results/model-smoke/run-20261101/` and `research/results/model-proposal-smoke/` retain failed abbreviated-IRI, duplicate or unsupported edits. The A–D smoke kept all four generation-error observations and their denominators. Chat/citation validity is not proof of successful ontology generation or model quality.
- `docs/portal-smoke.md`, `infra/portal/smoke-evidence.json` and source/config pins retain actual official-template and Studio host mount/theme/reload/read. The v4 report in `docs/trustgraph-pipeline-smoke.md` and `infra/portal/pipeline-evidence.json` records four ordinary and eight seed-guided ontology statements with exact source/chunk reconciliation. Ordinary GraphRAG answered correctly; ontology-guided retrieval cited the source but failed the known-answer check. The real adapter remains review-ineligible and inactive. The diagnostic seed hash was observed after ingestion; approved pre-ingestion binding, generic terminal processing status, durable application receipts and automatic eligible corpus activation remain open. Focused gateway/reconciliation/provider checks passed 23 with one optional live probe skipped; real adapter script execution is separate evidence.
- `docs/ontocheck-benchmark-compatibility.md` and `research/development-assessment/jena-rdfs-compat-v1/verification.json` retain ten of ten matching direct-Jena/upstream known answers. This is one synthetic development graph; unchanged published OWL suites and an independent held-out study remain outside the bridge.
- `research/evaluator-protocol.json`, evaluator schemas and `research/EVALUATOR.md` define external evaluation. `research/study.py` and `research/analysis/bootstrap-policy.md` implement allocation/timing/paired analysis and optional seeded task bootstrap. Thirty-three focused analysis checks and the full application suite passed. These are mathematical/engineering fixtures; no approved real study, participants, private oracles or empirical findings were created.
- Independent release review verified the three additional fixes in five focused cases; the earlier four mapping/scope/timer regressions also passed independently. The staged-source audit covered its then-current **197 files**, compared **12 known local secret forms** with zero matches, and inspected seven matching screenshots with no visible secrets or EXIF/XMP. Only a descriptive test token matched the token pattern. Later source/docs/screenshots must be included in the final scan; runtime/data/dependencies/results and original user outputs remain excluded.

Source layout is intentionally consolidated. Source Git is now initialized and the first consolidated engineering commit is pending; ontology Git is not source-code provenance, and the original milestone history is not fabricated. The final source identity and any later integration edits require explicit verification/restaging before the release is frozen. Signed domain selection, expert consent/access, independent oracles, final acceptance standards and actual study outcomes cannot be supplied by application tests. Conversely, generic live provider activation, complete native-host mutation coverage and final source packaging remain engineering/verification work. Optional Modified Delphi and complete OWL 2 DL remain deferred. The user has explicitly confirmed that no real study is approved.

Latest bounded TrustGraph engineering evidence: docs/trustgraph-pipeline-smoke.md and infra/portal/pipeline-evidence.json retain successful exact-byte/stage plumbing, the ontology known-answer failure, and earlier diagnostic failures. Final focused gateway/reconciliation/provider contracts:23 passed,1 optional generic live probe skipped; actual live adapter script separately resolved both sources and remained review-ineligible. No real study was approved or run.

## Final source-freeze addendum

After the clean-copy run, the completed bounded-provider tests joined the final main-source suite: **280 passed, 9 optional checks skipped in 53.71 seconds** (`research/results/release-check/final-backend.xml`). The final packaged JAR passed three focused real-engine workflow checks. Main frontend verification remained **36 passed**. All source edits were frozen for the reviewed initial local commit; the actual final commit is discoverable with `git log -1`. This consolidated snapshot replaces no claimed historical task commits and does not close the explicit integration/study gates above.
