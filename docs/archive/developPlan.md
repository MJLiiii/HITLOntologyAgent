# Ontology Engineering Web Product — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task by task; use `superpowers:subagent-driven-development` only if the user chooses delegated execution. Track execution with the unchecked boxes below. This document authorizes planning and describes future implementation; it does not claim that the product, integrations, tests, or research results already exist.

**Goal:** Build a useful web workspace where domain experts turn source documents into traceable OWL ontology extensions through AI proposals, executable checks, OntoCheck assessment, and explicit human approval, with a reproducible A–D research evaluation.

**Architecture:** One modular Python application exposes an API to a TypeScript web client and runs durable background workflows. Adapters retain the proposal's TrustGraph, two agent roles, Apache Jena + pytest, and OntoCheck components. Immutable artifacts and transactional metadata bind evidence, candidate revisions, assessments, reviews, and approved releases together; a separately permissioned evaluator handles held-out material.

**Tech Stack:** Proposed defaults: Python 3.12, FastAPI/Pydantic, SQLAlchemy/Alembic, PostgreSQL, RDFLib for RDF manipulation, React/TypeScript/Vite, a small Java/Jena bridge, pytest, Vitest, Playwright, Docker Compose, and a reverse proxy. Pin tested package/runtime/image versions in T00–T01. OntoCheck starts from the proposal's reviewed commit `69d42e38979f381fe531ae547fcc49b8ad58ef15` / stated v0.1.3, subject to explicit compatibility verification. TrustGraph runs in its documented deployment, behind an adapter.

**Spec:** The embedded product and technical specification in §§1–12 is the implementation spec. Source hierarchy and original references are in §1. Keep this file named **`developPlan.md`** at the repository root so it can travel as one handoff; do not require access to this ChatGPT conversation.

**Prepared:** 2026-11-01, Europe/Amsterdam. **Status:** Source-grounded planning baseline for user review; implementation choices marked **proposed default** are not prior user/supervisor approvals. Scientific choices explicitly left open must be resolved before the affected study starts, not guessed from this plan.

## Global Constraints

- Preserve **TrustGraph, Ontology Proposal Agent, Test Generation Agent, Apache Jena + pytest, OntoCheck, change tracking, and expert review** as named components.
- Build **one configurable system with four conditions A, B, C, D**. RQ3 is a nested review experiment, not a fifth end-to-end condition.
- Main C/D automated repair receives **failed entailment-test diagnostics only**; B receives **no automated assessment/test results or expert feedback**.
- Held-out questions, answers, source-fidelity references, and scores remain unavailable to development agents and normal reviewer sessions.
- Only a real authorized human's approval of the **exact checked revision and configuration** can authorize an accepted ontology release.
- Expert edits, mapping changes, selected patch subsets, changed imports, or rebasing create a successor revision and invalidate prior checks and approvals.
- Keep OWL entailment, SHACL conformance, executable CQ answer correctness, OntoCheck fitness, and source fidelity distinct in storage, UI, and reporting.
- DORA, Article 30(2)–(3)/Article 3, FIBO, modified Delphi, 20–30 pilot cases, final provider/model, final OWL profile, final sample size, and acceptance thresholds are **not confirmed commitments**.
- Real integrations and deterministic fakes must have visibly different status. Missing/failed/unsupported tooling must never become a green pass or invented score.
- Keep synthetic test ABoxes separate from ontology schema/release artifacts. Treat source documents and model responses as untrusted data.
- Secrets, confidential documents, held-out references, and private review data must not enter public repositories or public exports.
- No SFT project, finance-agent evaluation product, general autonomous agent platform, billing system, or unrelated personal project is part of this product.

## Review Focus

These five high-impact failure classes have explicit tests in the owning tasks:

1. A reviewer approves revision r1 while r2, a new mapping, or a new base exists: refuse publication and preserve both histories — T03/T10/T12.
2. A missing value, unsupported OWL construct, or crashed tool looks like a successful logical check: show its actual status and block required-check acceptance — T04/T05/T11.
3. Matching local names in different namespaces inflate semantic support: preserve full IRIs and leave mappings unapproved — T05/T10.
4. B/C prompts or researcher exports reveal held-out answers or OntoCheck feedback: enforce capability restrictions on backend data access, not UI hiding — T07/T09/T15/T16.
5. A worker crashes or receives duplicate requests after an external call or Git commit: recover without duplicate model charges where avoidable, duplicate approval, or duplicate release — T06/T08/T12/T19.

---

## 1. Source audit and decision authority

### 1.1 Sources inspected for this plan

| ID | Source | What it contributes / precedence |
|---|---|---|
| S1 | Attached `Proposal.pdf`, 12 pages, title *Human-in-the-Loop Ontology Engineering with Agentic AI and Automated Reasoning* | Primary current methodology: §§1.1–1.6, §§2.1–2.3, §§3–3.1, expected outputs. Its workflow figure was also inspected. |
| S2 | Attached `Deloitte Internship Topics 2026-2027.docx`, Topic 1 | Official project scope, expert questions and inferred results, source traceability, deliverables. Topics 2/3 are separate projects. |
| S3 | [Projects and companies descriptions 2026](https://docs.google.com/spreadsheets/d/1omkyawrM6AamvHKgGbKsOrVcnBQYrxMw), Deloitte Topic 1 detailed material | Six activities: requirements/CQs, grounding, construction/reuse, four scenario categories, expert interaction loop, evaluation. Retrieved through the connected source's readable Office-workbook representation. |
| S4 | `AGENTS_web_verified.md` | Most complete earlier guide, including source inventory, project memory, integration cautions, and external documentation review. |
| S5 | `AGENTS_audited.md` | Earlier completeness audit. Its additions are retained by S4. |
| S6 | `AGENTS.md`, current stored version 2 | Core architecture, assessment contracts, invariants, and staged implementation gates. |
| S7 | `ontology_engineering_proposal_brief.md` | Earlier RQ/control rationale; provisional DORA slice, pilot suggestions, and independent assessment caveats. S1 supersedes older differences. |
| S8 | `Pasted text.txt` | Historical methods draft; does not supersede S1's explicit OntoCheck and four-condition treatment. |
| S9 | Project `image.png` | Source-extracted screenshot text and workflow context. A draft message says a demo was developed; this does not establish an available repository or working implementation. |
| S10 | Retrieved relevant project conversation history, including proposal/loop discussions and AGENTS audit discussions | Context: this is Deloitte Topic 1, one platform, requested Codex-maintained `PROJECT_MEMORY.md`, and earlier development-plan intent. Suggestions are not automatically decisions. |
| S11 | Official upstream pages listed in §1.3, checked 2026-11-01 | Technical documentation evidence; does not prove local installation, exact pinned-code compatibility, or deployed integrations. |

S4–S9 were the six items returned by the project-folder inventory at planning time. S1/S2 were available as attached source copies. Relevant project history was searched in two focused passes. There is no product repository in the supplied workspace; only source documents were found. This audit covers accessible project sources and retrieved relevant history, not every private historical message or an unseen demo repository.

**Authority:** Current explicit user/supervisor decisions > S1 research method > S2 formal topic > S3 detailed activities > project guides > historical drafts/suggestions. For implementation, also read the target repository's applicable `AGENTS.md` instructions. Record conflicts instead of silently resolving them by dropping components.

### 1.2 Decisions, defaults, and unresolved scientific choices

| Kind | Decision | Development consequence |
|---|---|---|
| Source requirement | Unified web platform with human control and evidence-linked OWL extension | Implement real end-to-end workflows, not a chatbot-only UI. |
| Source requirement | TrustGraph, two agents, Jena/pytest, OntoCheck | Separate adapters and explicit integration evidence are mandatory. |
| Source requirement | Four conditions; independent held-out assessment | Protocol and backend data boundaries are part of the product. |
| Proposed default | Modular application + worker + React client | Small enough for one student; permits a practical review workspace. |
| Proposed default | PostgreSQL metadata/job queue + filesystem artifact volume | Avoid an additional broker initially; durable jobs and snapshots remain mandatory. Object storage can replace the artifact backend later. |
| Proposed default | Private, single-organization deployment with project membership | Useful for a small expert team; no enterprise multi-tenant SaaS build. Project-level isolation is still required. |
| Proposed default | Synthetic fictional contract-obligation example before a real domain | Exercises the pipeline without asserting DORA interpretation or needing confidential data. |
| Scientific decision open | Final domain/corpus, approved CQs/answers, seed ontology/imports, mappings | Configure data packs; do not bake financial terminology into core logic. |
| Scientific decision open | OWL constructs/profile and exact engines | Capability-tested in T00/T04; no generic claim of complete OWL 2 DL support. |
| Scientific decision open | Experts, sample size, allocation, budgets, acceptance rubric | Pilot first; freeze main-study protocol before collecting results. |
| Compatibility decision open | Pinned OntoCheck metric availability and TrustGraph API/version | Real smoke tests and explicit capability ledger; never fabricate missing capabilities. |

An empty ontology is permitted as an initial base, but the primary study is **ontology extension**. Reused ontology imports must be pinned and reviewed. First reuse candidate may be FIBO; it is not an MVP dependency.

### 1.3 Technical references and verification limits

- [OntoCheck repository](https://github.com/cwru-sdle/OntoCheck), [usage](https://ontocheck.readthedocs.io/en/latest/usage.html), [API](https://ontocheck.readthedocs.io/en/latest/api.html), [v0.1.3 distribution](https://pypi.org/project/OntoCheck/0.1.3/). Public examples expose CLI/Python entry points, but documented result names vary (`recall`/`precision` versus `relevance`/`accuracy`). Inspect installed pinned source and normalize tested output, retaining raw labels. The exact proposal commit could not be re-fetched through the web reader in this planning session; no exact-commit execution is claimed.
- [TrustGraph quickstart](https://docs.trustgraph.ai/quickstart/), [repository](https://github.com/trustgraph-ai/trustgraph). The quickstart documents Compose deployment, document processing, retrieval, ontology guidance, and explainability. It currently asks for 12 GB+ RAM and 8 CPUs for TrustGraph itself; reserve additional resources for this application and benchmark the actual stack. No real ingestion/provenance round-trip was run here.
- [Jena inference](https://jena.apache.org/documentation/inference/), [SHACL](https://jena.apache.org/documentation/shacl/). Built-in OWL rule inference is incomplete. SHACL has its own validation interfaces. T00/T04 must establish actual supported constructs and contradiction diagnostics.
- [OWL 2 Primer](https://www.w3.org/TR/2012/REC-owl2-primer-20121211/), [SHACL recommendation](https://www.w3.org/TR/shacl/), [PROV-O](https://www.w3.org/TR/prov-o/). PROV-O is an optional export representation; the traceability data itself is mandatory.
- [OntoChat](https://arxiv.org/abs/2403.05921) is related work, not a replacement runtime architecture.

Do not upgrade a floating `main`, container `latest`, or tool API silently. Record resolved commits, package hashes, image digests, license/attribution obligations, Java/Python compatibility, and capability-test results in `docs/integrations.md` and lockfiles. Unverified docs are leads, not evidence that integration works.

## 2. Product purpose, scope, and acceptance

### 2.1 Research questions preserved from the proposal

1. **RQ1 — Reasoner Feedback:** To what extent does feedback from failed OWL entailment tests improve the correct repair rate of LLM-generated ontology extensions compared with LLM self-revision without feedback?
2. **RQ2 — Expert Review:** To what extent does expert review identify and correct source-inconsistent axioms in LLM-generated ontology extensions that have passed automated OWL entailment tests?
3. **RQ3 — Source-Grounded Explanations:** Does providing experts with source-grounded explanations improve their accuracy in accepting or rejecting AI-proposed ontology axioms compared with reviewing the axioms without explanations?
4. **RQ4 — Workflow Effectiveness:** Does a workflow combining automated reasoning, iterative AI repair, and expert review reduce the expert review time required to produce an acceptable OWL ontology extension compared with one-shot LLM generation?

### 2.2 Who it serves

- **Domain expert/reviewer:** Understand a proposed model change, inspect its documentary basis and inferred consequences, ask a focused question, and accept, edit, or reject it without needing a local ontology toolchain.
- **Ontology engineer/researcher:** Prepare a bounded project, source corpus, seed ontology, namespaces/imports, reviewed CQs, SHACL shapes, and scenarios; inspect regressions and reproduce a run.
- **Independent evaluator:** Access sealed held-out questions and references after outputs are frozen; score all conditions without feeding results back to generation.
- **Project administrator:** Configure memberships, operational limits, provider connection, external-service health, backups, and reproducible deployment.

One person may hold several roles during development, but every action records the active role. Independence of scientific reference judgments requires a documented study procedure; permissions alone do not create independent ground truth.

### 2.3 The useful user journey

1. Create a workspace with a bounded goal and choose the clearly labeled synthetic demo or an empty project.
2. Upload documents and an optional seed ontology; see ingestion status, document versions, extraction limitations, and retrievable evidence.
3. Define and review competency questions, SPARQL, expected answers, ontology scope, and mappings. Freeze a development pack.
4. Select a task and start a bounded proposal run. See progress, costs/budget, stop controls, and a recoverable error state.
5. Review proposed **changes** against the accepted base. Open the supporting passage at its page/section, inspect inferred results, and compare Jena and OntoCheck reports separately.
6. Ask a question such as “Why is this property proposed?” or “Which fixture supports this inference?” Receive source/report links or a clear lack-of-support answer.
7. Accept, edit/request changes, or reject individual proposed changes. Resolve dependencies into a final candidate, revalidate it, and approve its exact revision.
8. Publish an immutable approved ontology release; download Turtle plus evidence, review, assessment, and reproducibility records. Continue from that release without losing history.
9. Researchers run A–D on frozen inputs, inspect authorized development results, then independently assess frozen outputs using sealed evaluation material.

### 2.4 Release levels

| Level | Required outcome | What may still be limited |
|---|---|---|
| M1 deterministic kernel | Base/candidate versioning; real Jena checks; pinned OntoCheck smoke test; explicit capability report | No LLM or polished UI required. A documented integration blocker prevents claiming a completed kernel. |
| M2 usable private demo | Authenticated web review journey with durable state, evidence, checked publication, exports, and visible fake/live connection modes | Synthetic data and deterministic model/retrieval fakes allowed, clearly labeled. Not a completed real-integration product. |
| M3 integrated pilot product | Real TrustGraph evidence round-trip; real configured provider; both agents; practical recovery, security, backup and restore; all core workflows | Final Deloitte corpus and study sample may still be pending. |
| M4 research-ready | Frozen protocol, A–D isolation, RQ1–4 instrumentation, held-out evaluator, reproducible exports and pilot review | Main-study findings require actual participants/data; synthetic runs are not findings. |

**Product completion** for the full request means M3 plus the M4 evaluation capability. A missing upstream metric must be explicitly visible and resolved through the documented capability/protocol decision; it cannot be hidden by a replacement score. Do not equate a dependency list, route skeleton, static dashboard, or fixture-only demo with completed integration.

**Out of scope initially:** Fully autonomous publication; general agent/plugin marketplace; training/fine-tuning; broad legal advice; a full Protégé replacement; unrestricted remote SPARQL; a new ontology-quality metric; public registration/billing; Kubernetes; real-time co-editing; mandatory multi-expert Delphi. Preserve extension points only where a current requirement needs them.

### 2.5 Requirement-to-task map

| ID | Required capability | Owning tasks | Evidence for acceptance |
|---|---|---|---|
| R01 | Source hierarchy, protocol/capability decisions, persistent project memory | T00, T20 | Decision ledger, source manifest, honest progress record |
| R02 | Durable project state, membership and authorization | T01, T02 | Restart and cross-project access tests |
| R03 | Immutable source documents and evidence locators | T06 | Original version reopens after replacement |
| R04 | TrustGraph ingestion/retrieval with provenance | T06 | Real round-trip artifact with exact source passage |
| R05 | Seed/import/namespace management and staged OWL patches | T03 | Parse, diff, import snapshot and base-conflict tests |
| R06 | CQs, approved expected answers, four scenario categories | T07 | Reviewed immutable development pack |
| R07 | Ontology Proposal Agent with structured proposals/repairs | T08, T09 | Schema/evidence checks and bounded run artifacts |
| R08 | Test Generation Agent, independently approved expectations | T08, T07 | Draft cannot become a reference without review |
| R09 | Jena inference, SHACL, CQ answer and regression reports | T04 | Real engine capability fixtures |
| R10 | OntoCheck base/candidate assessment and metric caveats | T05, T11 | Pinned smoke test; scope-aware diff; unavailable states |
| R11 | Mapping approval, source fidelity, human review | T10, T11 | Exact-revision decisions; mapping-change recheck |
| R12 | Safe questions/explanations and ontology visualization | T13, T14 | Evidence-linked answers; asserted/inferred graph distinction |
| R13 | Atomic approved releases, version history and audit | T12 | Duplicate/stale/crash publication tests |
| R14 | A–D budget/feedback control and frozen runs | T09, T15 | Sentinel leakage tests and matched-run manifests |
| R15 | Independent held-out scoring and RQ1–4 reporting | T16, T17 | All assigned cases retained, counters/reference provenance |
| R16 | RQ3 allocation/blinding and review-effort timing | T10, T17 | Same source access; no repeated proposal exposure |
| R17 | Resumable jobs, progress, cancellation, retries/costs | T01, T09, T19 | Worker restart and external-call ambiguity behavior |
| R18 | Exports and reproducibility/restore | T12, T18, T19 | Release bundle verified and backup restored |
| R19 | Security, accessibility, full user journey and real integration gate | T02, T11–T14, T19, T20 | Browser acceptance plus private deployment smoke |

## 3. UX specification

### 3.1 Screens and routes

All product routes are under `/projects/:projectId`; every screen preserves project, base/candidate revision and study context in the URL. Browser refresh/deep links work through the reverse proxy.

| Route/screen | Required content and actions |
|---|---|
| `/login`, `/projects` | Administrator-created accounts; sign in/out; memberships; choose project; no public signup by default. |
| `/projects/new` and project `/overview` | Bounded goal, editable domain metadata, demo/import choice, setup checklist, service capability status, next useful action. |
| `/documents` and `/documents/:versionId` | Upload PDF/DOCX/TXT/Markdown; original preview/download; extracted text; source URI/version/hash; page/section locators; ingest/retry status; corpus selection. Scanned PDFs show extraction-needed status unless OCR is actually configured. |
| `/requirements` | CQ natural-language text, reviewed SPARQL, answer expectation and query semantics; dev pack versions; namespace/import settings; draft/approved status. Held-out data is absent from the normal endpoint. |
| `/ontology` | Accepted base version; import closure; searchable class/property tree and graph; entity details and definitions; asserted/inferred toggle with profile label; import/export. |
| `/runs` and `/runs/:runId` | Start configured task/condition, frozen inputs, bounded progress events, costs/tokens, phase, cancel, failure reason, resume/retry rules, outputs even on failure. |
| `/proposals/:revisionId` | Central workbench described below; exact revision, base, state, per-change decisions, dependencies, recheck and final approval. |
| `/tests` | Draft/reviewed scenarios; all four categories; fixture graph separated from schema; approved expected outcomes; regression history. |
| `/releases` and `/releases/:id` | Approved version, comparison to prior release, exact checks and signer, evidence/review trace, export. Revert creates a checked successor, never rewrites history. |
| `/experiments` and `/experiments/:id` | Researcher-only protocol versions, task/pilot/main split, A–D runs and authorized aggregate status; evaluator-only sealed-data operations. |
| `/settings` | Membership, provider connection test without exposing secrets, quotas/budgets, integration/capability ledger, retention and backup status. |

### 3.2 Central review workbench

Desktop layout: left change/entity list; middle readable diff and entity/axiom editor; right evidence and explanation panel; lower tabs for **Jena checks**, **OntoCheck comparison**, **CQ answers**, and history. On narrow screens use ordered tabs, never hide acceptance blockers. A graph is supplementary; every entity/change is accessible in a table/tree.

- Summaries use readable labels with expandable full IRIs and Turtle. Show additions, deletions, definition changes, affected entities, and dependent changes.
- Every proposed axiom links to exact document version and passage, plus generator rationale. Distinguish **source-supported claim** from **modelling choice** requiring rationale; a citation alone is not proof of correctness.
- Show status text/icons, not color alone. Separate `pass`, `fail`, `unknown`, `unsupported`, `unavailable`, `execution_error`, `not_run`, and `running`.
- OntoCheck displays base/candidate values, numerators/denominators, unsupported terms, conceptual/structural capability status, mapping suggestions and approvals. Never label term overlap “answer accuracy.”
- “Accept this change” records a provisional per-change review disposition. It does **not** publish immediately. Selection/edits form a successor candidate, the complete assembled candidate is rechecked, then the reviewer gives final exact-revision approval.
- Reject records a reason; request changes creates a recorded feedback item; edit produces a successor revision and preserves the original. Approve is disabled with a precise reason when required checks, evidence, fidelity attestation, permissions, or current-base checks are missing.
- Bulk acceptance requires inspecting a summary and dependency resolution; no “approve all” bypass of validation.
- Unsaved editor changes warn before navigation. Failed save keeps the draft locally for recovery without treating it as persisted or approved. Concurrency conflicts show a rebase/refresh action.
- Research RQ3 mode keeps source access and development-assessment displays identical, varying only the evidence-linked explanation. Disable other explanation/chat routes for assigned sessions to preserve the manipulation; enforce it server-side.

### 3.3 General usability

Keyboard-accessible navigation and review actions; visible focus; form labels; readable errors; accessible dialog behavior; screen-reader announcements for job status; no graphs as the only navigation. Provide onboarding using the fictional demo, an empty state with one next action, loading states, retryable failure states, and source/viewer fallbacks. Paginate large lists; filter graph neighborhoods rather than rendering every triple. Display recorded UTC timestamps in the user's timezone with the timezone shown on exports.

Proposed performance targets for the pilot: paginated metadata API p95 under 500 ms on the declared pilot machine, excluding external tools; first workbench content under 2 s for a 200-change fixture; interactive neighborhood graph capped at 200 nodes by default. Benchmark and record actual results in T20; these are engineering targets, not research findings.

## 4. Architecture and deployment boundaries

### 4.1 Chosen proposed default and alternatives

1. **Recommended: modular FastAPI application + durable worker + React review UI.** Keeps Python tooling convenient, supports careful review interactions, and avoids distributed business logic. More frontend work than a rapid Python dashboard, justified by the requested usable web product.
2. **Python-only rapid UI.** Fastest throwaway feasibility demo, but more difficult to make complex diff editing, fine-grained review, and controlled RQ3 sessions robust. May be used for a spike, not silently substituted for this agreed product target.
3. **Distributed agent services/microservices.** Independent scaling is unnecessary for the expected pilot and adds deployment/recovery work. Keep external tool boundaries and one evaluator boundary; avoid splitting core business logic into many services.

These are planning recommendations, not a recorded user selection. T00 may adapt to an existing repository while preserving required behavior and scientific controls.

### 4.2 Runtime responsibilities

| Unit | Responsibility / authority |
|---|---|
| Web client | Navigation, forms, diffs, evidence/graph views, status updates. Holds no provider keys and makes no direct reasoning/provider/TrustGraph calls. |
| API application | Authentication, project authorization, schemas, workflow transitions, review and release commands, artifact access, job submission and SSE. |
| Development worker | Ingestion, retrieval, model calls, draft scenarios, Jena and OntoCheck development jobs. Receives only capability-scoped inputs; no held-out/reference credentials or filesystem mounts. |
| PostgreSQL | Transactional metadata, append-only domain events, job leases/attempts, review records, current release pointer and permissions. |
| Artifact store | Immutable document bytes, extraction outputs, ontology snapshots/import closure, model requests/responses, tool reports, exports. Local volume initially, behind a content-addressed interface. |
| Jena bridge | Small Java executable with a JSON request/response contract for approved queries, inference and SHACL. Pinned Java/Jena versions; no HTTP fetches or external query services. |
| OntoCheck process | Isolated working directory/environment; pinned dependency; raw report capture and tested normalization. Disable URL-access checks and network-bearing metrics unless explicitly allowed. |
| TrustGraph deployment | Version-pinned external ingestion/retrieval infrastructure. Project/corpus isolation and service credentials verified before live use. |
| Evaluation worker | Separately permissioned process and storage/DB role; reads frozen outputs and sealed packs, writes evaluation-only reports; has no route to agent feedback. |
| Reverse proxy | TLS in private deployment, request/body limits, same-origin routing to UI/API; only intentional application ports exposed. |

No Redis/Celery is required initially: PostgreSQL jobs use leases and `FOR UPDATE SKIP LOCKED`, heartbeat, attempt records, and idempotent outputs. If an existing repo already has a broker, preserve it and document equivalent guarantees. No distributed transaction across Git and PostgreSQL is assumed (§7.4).

### 4.3 Modes

- `APP_MODE=demo`: synthetic corpus, deterministic fake retrieval/provider, conspicuous banner; no external keys required. Real semantic tooling may be tested separately. A fake engine report is always marked fixture-only.
- `APP_MODE=pilot`: real Jena and OntoCheck, real TrustGraph and configured model/provider; project data policy and required-check policy active.
- `APP_MODE=study`: protocol frozen; feedback policy, study allocations and evaluation separation enforced. Changing model/profile/config creates a new protocol version.

A diagnostic failure in pilot/study must not automatically switch to a fake backend. Demo mode never creates real expert approvals or actual study findings.

## 5. Repository map and shared contracts

Paths below are **target paths**, not existing files. Adapt them to a verified repository once, record the mapping, and use it consistently. `tests/` below refers to software tests; runtime agent scenarios are declarative data, never generated Python executed by the server.

```text
AGENTS.md
PROJECT_MEMORY.md
developPlan.md
README.md
pyproject.toml
uv.lock
.env.example
Makefile
compose.yaml
configs/{app,reasoning,ontocheck,conditions,acceptance}.yaml
docs/{sources,decisions,integrations,protocol,operations,privacy}.md
src/ontology_engineering/
  app.py
  api/{auth,projects,documents,requirements,proposals,runs,reviews,releases,queries,experiments,exports}.py
  domain/{common,artifacts,documents,requirements,ontology,reports,review,runs,experiments}.py
  db/{models,session,migrations/}
  auth/{service,permissions}.py
  storage/{artifacts,ontology_repository,release_repository}.py
  jobs/{queue,worker,events}.py
  documents/{ingestion,extraction,evidence}.py
  adapters/{trustgraph,jena,ontocheck,llm}.py
  requirements/{service,packs,scenarios}.py
  agents/{proposal_agent,test_generation_agent,feedback_policy}.py
  workflow/{controller,budgets,transitions}.py
  review/{service,mappings,timing}.py
  queries/{service,explanations,policy}.py
  evaluation/{protocol,runner,scorer,metrics,allocations,exports}.py
  exports/{release_bundle,reproducibility}.py
services/jena-bridge/{pom.xml,src/main/java/org/ontology/JenaBridge.java,src/test/}
web/{package.json,package-lock.json,vite.config.ts,src/,tests/}
web/src/{app,api,features,components,styles}/
fixtures/demo/{documents,ontology,questions,scenarios,manifest.json}
tests/{unit,integration,security,acceptance,fixtures}/
tests/integration/{test_jena,test_ontocheck,test_trustgraph}.py
scripts/{smoke_kernel,seed_demo,export_run,verify_bundle,backup,restore}.py
infra/{Dockerfile.api,Dockerfile.web,Dockerfile.jena,proxy.conf}
.github/workflows/ci.yml
```

`AGENTS.md` is repository guidance, `PROJECT_MEMORY.md` is verified progress/decisions, and `developPlan.md` is the execution backlog. Do not overwrite an existing AGENTS file with a different historical variant. No auto-synchronization with ChatGPT memory is assumed.

### 5.1 Identifier and envelope conventions

- IDs: UUID strings. Timestamps: timezone-aware UTC ISO 8601. Hashes: SHA-256 of immutable bytes, prefixed `sha256:`.
- Every project-owned record carries `project_id`. Every versioned value carries immutable ID/digest and creation metadata. Request/response DTOs have `schema_version: 1`.
- `ArtifactRef = {id, digest, media_type, size_bytes}`; never expose filesystem paths to normal clients. Download URLs require current authorization.
- All mutation requests use an idempotency key; requests against a mutable pointer also send an expected version/ETag. Reusing a key with a different body returns 409.
- Common API error: `{code, message, request_id, details}`. Codes include `BASE_CONFLICT`, `STALE_APPROVAL`, `CHECKS_REQUIRED`, `UNSUPPORTED_PROFILE`, `BUDGET_EXHAUSTED`, `DEPENDENCY_UNAVAILABLE`, `FORBIDDEN`.
- Long operations return HTTP 202 `{job_id, run_id?, status_url}`. SSE event shape: `{event_id, job_id, stage, status, completed?, total?, message, created_at}`; reconnect uses Last-Event-ID. Stage counts are honest; do not fabricate progress percentages for model calls.

### 5.2 Persisted records

| Record | Mandatory fields beyond ID/project/timestamps |
|---|---|
| `DocumentVersion` | document_id, original artifact, source URI/title, declared version/date, byte hash, supersedes ID, extraction status and tool/config |
| `EvidenceSpan` | document_version_id, extraction artifact/hash, page/section or paragraph locator, character offsets in extracted text, quote/hash, retrieval_run_id, original-view locator if known |
| `CorpusVersion` | selected document versions, extraction/retrieval index version, exclusions, digest |
| `QuestionVersion` | text, SPARQL, query semantics, scope, status, reviewer; expected answers stored in role/partition-controlled pack |
| `DatasetPack` | version, partition `demo/pilot/development/held_out`, question/scenario IDs, expectations/reference location, approvals, namespace/mapping/import scope, digest |
| `OntologyVersion` | immutable artifact, base/parent IDs, ontology byte digest, imports manifest/digest, schema namespace, release status |
| `CandidateRevision` | base_version_id, parent_revision_id, patch and assembled snapshot refs, evidence links per change, rationale, author/model/run, mapping/config/test-pack refs, state |
| `MappingVersion` | source/target full IRIs, relation, rationale/evidence, suggestion/approved/rejected status, reviewer; scope and version |
| `ScenarioVersion` | declarative RDF fixture, category, check type/expected result, independent approval, partition, source/CQ links |
| `CheckReport` | candidate/snapshot digest, profile/tool/version, imports/pack/config digests, separate entailment/SHACL/query outcomes, diagnostics, raw artifacts, capability limits |
| `AssessmentReport` | ontology digest, OntoCheck commit/package hash, CQ/config/mapping/import digests, raw and normalized metrics/denominators, per-term/question diagnostics, per-metric capability and execution status |
| `ReviewSession/Decision` | actor/role, exact revision/context, per-change decision, rationale, source-fidelity attestation, assignment/explanation condition, timing events, successor ID |
| `Approval` | exact candidate digest + complete validation-context digest, checked report IDs, authorized reviewer, final decision/time; cannot be transferred to a successor |
| `Release` | approved artifact/digest, parent release, approval/report IDs, Git commit/tag, publication job/state, manifest, current-pointer transaction |
| `AgentRun/Attempt` | inputs/allowed feedback digest, prompt/version, provider/model/settings, usage/cost status, budget, external-call state, request/response artifacts, stopping reason |
| `ExperimentProtocol/Run` | frozen shared inputs, condition, paired-candidate/replicate IDs, budgets, feedback policy, tool/model versions, pilot/main flag, output freezes, failure/censoring states |
| `Job/Event` | type, idempotency key, owner/scope, lease/heartbeat, status, attempts, checkpoint/output refs, append-only event sequence |

Store credentials separately from these records. Audit events are append-only through application permissions; this is not a claim of cryptographic tamper-proofing against a database administrator.

### 5.3 Adapter/service interfaces

These are **application contracts to implement**, not claims about upstream APIs. Place DTOs in the named domain files and keep their spelling consistent across tasks. `SessionContext` contains actor, project, role and capability-scoped data access; never pass it as an unrestricted DB session to an agent.

```python
class ArtifactStore(Protocol):
    def put(self, data: bytes, media_type: str) -> ArtifactRef: ...
    def read(self, ref: ArtifactRef) -> bytes: ...

class RetrievalAdapter(Protocol):
    def ingest(self, corpus: CorpusVersion) -> IngestionReceipt: ...
    def retrieve(self, request: RetrievalRequest) -> EvidenceBundle: ...

class JenaAdapter(Protocol):
    def check(self, request: CheckRequest) -> CheckReport: ...
    def query(self, request: QueryRequest) -> QueryResult: ...

class OntoCheckAdapter(Protocol):
    def assess(self, request: AssessmentRequest) -> AssessmentReport: ...
    def compare(self, base: AssessmentReport, candidate: AssessmentReport) -> AssessmentDiff: ...

class LLMProvider(Protocol):
    def generate(self, request: ModelRequest, budget: BudgetReservation) -> ModelResponse: ...

class ProposalAgent(Protocol):
    def propose(self, context: ProposalContext) -> ProposalDraft: ...
    def revise(self, context: RevisionContext) -> ProposalDraft: ...

class TestGenerationAgent(Protocol):
    def draft(self, context: ScenarioContext) -> ScenarioDraftBatch: ...

class FeedbackPolicy(Protocol):
    def build(self, request: FeedbackRequest) -> FeedbackEnvelope: ...

class WorkflowController(Protocol):
    def start(self, request: StartRun, actor: SessionContext) -> RunRef: ...
    def advance(self, run_id: str) -> RunStatus: ...
    def cancel(self, run_id: str, actor: SessionContext) -> RunStatus: ...

class ReviewService(Protocol):
    def decide(self, request: ReviewCommand, actor: SessionContext) -> ReviewResult: ...
    def approve(self, request: ApprovalCommand, actor: SessionContext) -> Approval: ...

class PublicationService(Protocol):
    def publish(self, request: PublishCommand, actor: SessionContext) -> ReleaseRef: ...

class EvaluationService(Protocol):
    def freeze(self, request: FreezeCommand, actor: SessionContext) -> FrozenOutput: ...
    def score(self, request: ScoreRequest, actor: SessionContext) -> EvaluationReport: ...
```

Define each DTO in the task introducing it. `CheckRequest`/`AssessmentRequest` contain immutable refs, not paths accepted from a browser. Requests name graph semantics and dataset partition explicitly. Comparisons require identical CQ set, mappings, scope, imports policy, and metric config; ontology content itself is expected to differ.

## 6. Semantic, evidence, and assessment behavior

### 6.1 Ontology patches and versions

- Import legal Turtle initially; optionally export RDF/XML only after a tested conversion. Parse before staging. Reject malformed or oversized input with location/error.
- Snapshot the full `owl:imports` closure from reviewed local artifacts. Do not dereference arbitrary remote imports during runs. Report unresolved imports; no silent omission.
- Proposals contain typed operations for classes, object/datatype properties, labels/definitions, hierarchy/axioms and proposed mappings. Deletions require a reason and impact display.
- Apply to a candidate copy with an explicit base ID. Keep accepted graph immutable. Preserve schema versus synthetic instances.
- OWL restrictions and RDF lists may contain blank nodes. Do not compare raw blank-node labels or delete a single list triple as if it were an independent axiom. T03 chooses and verifies canonical subgraph/axiom identity, retaining exact bytes as authoritative artifacts. Unsupported complex edits fall back to full candidate replacement plus reviewable semantic diff, never silent graph corruption.
- Allow only constructs covered by the chosen capability manifest for checked publication. Unsupported constructs may be imported for inspection but are prominently flagged and cannot satisfy required logical checks.
- Name/IRI policy is per project, with collision detection and full-IRI display. Prefix labels and lexical similarity do not authorize equivalence.

### 6.2 Evidence and document lifecycle

Persist original bytes and extraction output separately. Character offsets refer to a specific extraction artifact, not arbitrary original PDF byte offsets. OCR or a new extractor creates a new extraction version. Every passage remains resolvable after a document is superseded. Mark deleted/unavailable evidence and block new publication if required supporting evidence cannot be resolved under the declared retention policy.

TrustGraph retrieval must return or be reconciled to local immutable document/passage IDs. Reject or quarantine candidate evidence without a reproducible locator; do not invent citations from model text. Record ranking/retrieval configuration and corpus version. TrustGraph's extracted graph remains **candidate knowledge**, not accepted ontology truth.

### 6.3 Executable checks and four scenario categories

| Category | Example expected behavior in fictional fixture | Report semantics |
|---|---|---|
| Expected inference | `ManagedService` subclass of `Service`; instance of former is inferred as latter | `entailed` within the specified engine regime |
| Unwanted inference | A `Person` must not be inferred as `Service` in the bounded task | `not_entailed` for the specified query; not proof of its logical negation |
| Incomplete information | Missing contract contact does not by itself entail an explicit negative fact | OWL result remains indeterminate/not entailed; separate SHACL minCount may fail |
| Contradictory assertions | Fixture contains incompatible assertions covered by an actual tested engine capability | Report a supported contradiction diagnostic; otherwise `unsupported/unknown`, never “consistent” by default |

Support declared SPARQL ASK and SELECT checks first; compare SELECT results by normalized RDF terms with explicit set/multiset and order policy. Distinguish asserted/inferred graph choices, datatypes/language tags, expected empty answers and unavailable execution. Runtime pytest can coordinate the **reviewed declarative pack** through trusted adapter code; the LLM never writes arbitrary executable test code for execution.

### 6.4 OntoCheck

Assess base and candidate with the same versioned development CQs, namespace/import policy, approved mapping set, and metric configuration. Persist raw output and normalized values:

- **Task-vocabulary coverage:** required query terms represented / required query terms.
- **Ontology-vocabulary utilisation:** queried ontology terms / scoped ontology terms. Lower utilisation may reflect legitimate wider ontology scope.
- **Conceptual fitness:** validated identity/equivalence support separated from approximate suggestions, only if implemented and tested in the selected tool version.
- **Structural fitness:** support for required schema paths, distinct from correct instance-level answers, only if actually supported.
- Selected annotation/structural diagnostics as justified and available. Do not confuse generic structural diagnostics with the specific structural-fitness requirement.

Per metric: `capability = supported_and_tested | supported_but_unverified | unavailable | extension_needed`; `execution = ok | error | not_run`. Scores are nullable. Zero denominator is “not applicable” with denominator 0, not a fabricated 0%/100%. Preserve raw tool labels and operational definitions. If raw local-name overlap conflates IRIs, show raw behavior plus an ambiguity warning; do not silently relabel a custom corrected metric as upstream OntoCheck.

Missing required conceptual/structural capabilities trigger an explicit integration/protocol decision in T00/T05. A separately named, approved extension may later implement a research requirement; it must not pretend to be native OntoCheck. Any changed metric or tool config creates a new assessment protocol.

### 6.5 Questions and explanations

Questions target a selected revision/release. The service may retrieve approved development evidence, explain a proposed change using its recorded rationale, or propose a read-only query. Query execution requires parsed allowlisted ASK/SELECT, restricted graph scope, result/time limits, and no `SERVICE`, update, load, remote FROM or file/network access. Validate ASTs rather than substring scanning.

Answers label provenance: source-backed statement, observed query result under a named profile, or modelling suggestion. “No support found” and “not entailed” are valid responses. Do not invent reasoning proofs when the engine supplies no derivation. Show source/report links and exact ontology context; user chat never directly modifies ontology. This feature supports ontology engineering, not a compliance-certification service.

## 7. Workflow, review, jobs, and publication invariants

### 7.1 State transitions

Candidate revisions are immutable; status events may advance their lifecycle:

`draft → staged → checking → review_ready → approved → published`

Alternative outcomes: `validation_failed`, `rejected`, `superseded`, `blocked`. A failed/unsupported candidate remains inspectable and can receive comments, but cannot become approved unless required checks are satisfied. Repairs and edits create successor revisions. Production output freezing is a separate event and does **not** require publication.

Run/job states: `queued`, `running`, `waiting_for_review`, `succeeded`, `failed`, `cancelled`, `budget_exhausted`, `blocked`, `interrupted_unknown`. Record stopping causes, partial output, attempt number, and any unresolved external-call charge. Cancel stops at a safe boundary, requests subprocess termination, and never publishes as a side effect.

### 7.2 Context binding

Compute a validation-context digest over candidate bytes, base ID, imports closure, development pack, reasoning profile/tool versions, shapes, OntoCheck config/version, namespace/mapping versions and acceptance-policy version. A report is current only for that digest. Approval binds that digest and the report IDs. Changes anywhere require a successor/recheck and final approval.

Operational publication policy explicitly distinguishes blocking logical/CQ/regression requirements, source-fidelity attestation by the producing reviewer, evidence requirements, and diagnostic metrics. **Operational approval is not independent study acceptance.** RQ4 study acceptance also requires the separate independent common-rubric assessment in §8.3; a published release can still fail that assessment. Missing required checks block approval. Nonblocking unavailable diagnostics remain visible with an acknowledged limitation; they do not become passes. Only a prospectively configured policy can define what is nonblocking—never weaken it to accept a failing candidate after the fact.

### 7.3 Durable jobs, budgets and recovery

Reserve budget before each model call; enforce revision, output-token, total-token, elapsed-time and monetary caps where pricing is configured. Token counting semantics must include retrieval/test-generation calls consistently across compared conditions and be frozen in the protocol. Unknown cost is labeled unknown. Equal limits mean equal allowed budget, not guaranteed equal actual token consumption.

Persist a request artifact and attempt record before external invocation and persist the response immediately after. Use provider idempotency where supported. A crash in the gap may have charged a call without a saved response: mark `interrupted_unknown`, count/reserve its possible spend, and require an explicit authorized retry policy; do not promise exactly-once LLM calls. Schema-correction retries consume the same budget. Do not secretly provide test feedback during a “format-only” retry.

Checkpoints reference immutable outputs. Resume from completed stages, not from an unrecorded in-memory agent conversation. Jobs use leases/heartbeats; duplicate delivery is expected and must be harmless. Provider failures and tool timeouts surface actionable errors and preserve prior revisions.

### 7.4 Approval and Git publication

Use a transactional publication intent/outbox. Under a lock on the project's current accepted pointer, verify the base and exact approval/context. Build a release bundle and deterministic Git commit in a server-owned **per-project** ontology repository; no caller-controlled Git path or commit arguments. Then finalize the database release/pointer, audit event, and outbox state. A reconciler completes an interrupted publish using the intent ID and existing commit, without creating another release.

Readers see only finalized releases. If another candidate was published first, return 409 `BASE_CONFLICT`; rebase requires a new candidate/recheck/approval. Rollback means a new successor release, preserving lineage. Publication must not import synthetic fixtures, prompt logs, secrets, or held-out data into ontology Git history. Back up that Git repository as well as PostgreSQL and artifacts.

## 8. Research protocol as an executable product feature

### 8.1 Conditions and information access

| Condition | Production | Permitted revision feedback | Human production role |
|---|---|---|---|
| A | One generation, no revision | None | None before production freeze |
| B | Self-revision under the matched B/C budget | Sources/CQs and prior candidate; no automated results, scores or expert feedback | None before production freeze |
| C | Reasoner-guided repair | Only approved failed entailment-test diagnostics | None before production freeze |
| D | Same automated stage as C, followed by expert review/refinement | Same entailment diagnostics during automated stage; explicit expert feedback during review stage | Reviews sources, changes, development Jena and OntoCheck reports; edits/rechecks |

All conditions use the same frozen corpus, base ontology, development questions, base model/settings and initial generation prompt. For RQ1, generate/select the same eligible missing-entailment candidate once and fork it into B and C; store paired IDs. For D, reuse the C-stage checkpoint/trace in the comparison, or document equivalent paired execution fixed beforehand. D expert edits occur after the shared automated stage and are logged separately.

Stopping decisions are also information channels. B must never stop early because an unseen test/assessment passed or failed. Proposed conservative pilot default: the same fixed number of revision opportunities for B/C, subject to the same predeclared resource/technical limits; C may explicitly return an unchanged candidate when no repair is warranted. Freeze the final stopping rule before the main study and record every opportunity/no-op.

Test-generation outputs and development expectations are prepared/reviewed and frozen **before** comparative repair tasks; do not generate different reference tests for each arm. Capture development OntoCheck reports for every arm offline; do not expose them to B/C agents or their tool outputs. Structural/SHACL diagnostics and rich reasoning justifications are also excluded from the main C feedback unless the protocol explicitly defines a separate experiment. Safety/format errors are logged under the same handling policy across arms.

### 8.2 Frozen packs and permissions

Development and held-out material live in different storage roots and database schemas/roles. Development worker mounts no held-out root. The evaluator has no model API key and cannot enqueue agent repairs from scored output. Normal application DTOs omit answer keys/reference judgments; no browser download, search, SSE/log stream, or generic artifact endpoint bypasses these restrictions.

Split related fixtures by task/source family when necessary to reduce near-duplicate leakage. Version the split and audit retrieval indexes so sealed references are never ingested into TrustGraph. The development agent receives source evidence that genuinely belongs to the task; it does not receive held-out questions or labels.

Freeze: corpus and extractors, ontology/imports, CQs/scenarios/mappings, source-grounded independent reference, OWL profile, Jena/OntoCheck config, model/prompt, feedback policy, budgets, sample/allocation rules, acceptance criteria and stopping rules. Main-study protocol changes create a new protocol/version/cohort; no retroactive edits to the old one.

### 8.3 RQ implementation and metrics

| RQ | Product instrumentation | Primary scoring / safeguards |
|---|---|---|
| RQ1: reasoner feedback | B/C paired candidate IDs, repair attempts, permitted feedback digests, protected/unwanted checks | Correct repair requires target restored, protected entailments retained, no disallowed new inferences, and independent source fidelity. Denominator includes all assigned repair cases; distinguish infrastructure failures while retaining the accounting. |
| RQ2: expert value | D pre-review frozen snapshot, expert-marked errors/corrections, post-review frozen snapshot | Independent source-grounded reference; detection/correction counts, precision/recall where defined, remaining/new errors. Experts' own corrections are not their own reference. It is assessment-assisted expert review. |
| RQ3: explanations | Controlled review assignments with/without explanation, balanced validity, reviewer/case IDs and exposure ledger | Same axiom/source access/assessment UI; vary only explanation; no reviewer sees same proposal twice. Record decision accuracy, false acceptance/rejection and time; counterbalance across reviewers/cases. One reviewer is exploratory. |
| RQ4: workflow | Preserve A–D production snapshots, then freeze final corrected A–C and post-review D outputs separately; counterbalance presentation/task order for the common correction procedure | **Independent** acceptance under the same logical/CQ/regression and source-fidelity rubric, not producing-reviewer attestation alone. Count **all** expert review/correction work, including D's expert stage. Report acceptance with time; over-budget cases are unsuccessful and right-censored, not omitted. |

**RQ4 acceptance procedure:** The common correction stage uses the same source access, development-check displays and OntoCheck display policy across A–D; D's earlier in-workflow review remains part of its treatment and its time is included. This stage never receives held-out results or independent reference labels. On ready-for-final-assessment submission or the common effort limit, freeze the final correction snapshot for every arm. An independent authorized assessor/evaluator applies the same pre-specified acceptance rubric, including independently judged source fidelity, to these frozen snapshots. Record this verdict separately from operational release approval. A failed final independent assessment is retained as an unsuccessful outcome; do not resume the run from sealed feedback or silently count human self-approval as acceptance. Preserve production and final-correction snapshot IDs, submission time, all expert work, final verdict, terminal reason and observed effort. Over-budget observations are right-censored at the common effort limit; other early/terminal failures need a pre-specified analysis rule and are not assigned an invented time-to-acceptance. Final submission/stopping and censoring rules require protocol approval before the main study. Additional acceptance checkpoints, if desired, require an explicitly approved leakage-safe protocol rather than ad hoc evaluator feedback.

Store both elapsed and active review time. Active time uses explicit start/pause/resume/finish plus browser visibility/heartbeat intervals and a prospectively declared idle policy; pause/idle is auditable, and short reading periods must not disappear silently. Keep wall time, active time and expert-submitted corrections distinct. Timing implementation is not automatically a validated workload measure.

Use task-grouped paired summaries and uncertainty estimates that respect repeated runs/reviewers; final statistical model and sample-size rationale are a frozen study decision. Handle undefined precision/recall or no eligible cases explicitly. OntoCheck term-overlap measures remain secondary, with per-question diagnostics and denominators. Never publish simulated expert behavior as real participation or infer causal findings from a demo.

### 8.4 Pilot and optional deliberation

Pilot cases are marked and excluded from main comparisons. “20–30 cases” was a historical suggestion only. Use pilot difficulty and reviewer burden to justify task/reviewer/run counts. Final corpus/domain/CQs, independent reference, participant procedure and sample sizes must be agreed before main study. If several experts are available, optional independent rounds and disagreement summaries may support modified Delphi; with one expert use ordinary iterative review.

## 9. API surface and authorization

Base path `/api/v1`; JSON unless downloading an artifact. Below are product contracts, not upstream endpoint names. Every resource is membership-checked against its owning project even when accessed by raw ID.

| Endpoint | Behavior |
|---|---|
| `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | Server sessions, secure HttpOnly cookie, CSRF protection for mutations, login rate limiting. Admin creates accounts via management CLI. |
| `GET/POST /projects`, `GET/PATCH /projects/{p}` | Membership-scoped project setup and versioned configuration. |
| `GET/POST /projects/{p}/members`, `PATCH/DELETE /projects/{p}/members/{id}` | Administrator-only membership/role management with audit and immediate authorization effect. |
| `GET/PATCH /projects/{p}/settings`, `POST /projects/{p}/settings/provider-test` | Authorized limits/privacy/integration configuration and connection test; secrets are write-only and responses expose only presence/status. Frozen study settings cannot be edited in place. |
| `POST /projects/{p}/documents`, `GET /projects/{p}/documents` | Bounded multipart upload and version inventory; returns ingestion job. |
| `GET /projects/{p}/documents/{v}/evidence` | Authorized passages and original-view locators; immutable version. |
| `GET/POST /projects/{p}/requirements`, `POST /requirements/{id}/approvals`, `POST /projects/{p}/packs` | Draft/review/freeze development requirements and scenario packs; no held-out answers. |
| `GET/POST /projects/{p}/scenarios`, `POST /scenarios/{id}/reviews` | Draft RDF fixtures and reviewed expected outcomes for all four categories; schema/partition-validated and versioned. |
| `POST /projects/{p}/ontology/imports`, `GET /projects/{p}/ontology` | Seed/import snapshot management; entity neighborhood/tree query; no arbitrary remote fetch. |
| `GET/POST /projects/{p}/runs`, `GET /runs/{id}`, `POST /runs/{id}/cancel` | Capability-scoped run creation, progress/cost/outcome, safe cancellation. |
| `GET /jobs/{id}/events` | Authorized resumable SSE stream; no raw prompts or sealed reference data. |
| `GET /projects/{p}/proposals`, `GET /proposals/{id}`, `POST /proposals/{id}/revisions`, `POST /proposals/{id}/checks` | Exact-revision workbench, immutable edits, asynchronous checks/assessments. |
| `POST /proposals/{id}/decisions`, `POST /proposals/{id}/approvals` | Per-change disposition and final approval; server validates digest/permission/checks. |
| `POST /projects/{p}/mappings` | Review suggestion/approve mapping; creates a new configuration and candidate context. |
| `POST /projects/{p}/releases`, `GET /projects/{p}/releases` | Idempotent publication intent and accepted history. |
| `POST /projects/{p}/questions` | Evidence/report-grounded question; no hidden write side effects; session restrictions apply. |
| `POST /projects/{p}/queries` | Restricted read-only SPARQL, explicit selected graph/profile, bounded results. |
| `POST /projects/{p}/experiments`, `POST /experiments/{id}/freeze` | Versioned protocol/task execution and production freezes. |
| `POST /evaluation/experiments/{id}/score` | Evaluator-only action in separately credentialed process after freeze. |
| `POST /projects/{p}/exports`, `GET /artifacts/{id}` | Manifested export job and permission/partition-aware download. |
| `GET /health/live`, `GET /health/ready` | Minimal public health; authenticated integration/capability details in settings. |

Role defaults: viewer reads accepted releases; reviewer reads development proposals/evidence and reviews; engineer prepares draft requirements/corpus and runs workflows; researcher controls protocols/development reports; evaluator accesses sealed scoring; admin manages membership/operations. Role permissions are explicit, testable rules. Approval needs reviewer permission in that project. Admin status alone is not an unrecorded expert approval.

## 10. Security, privacy, operations, and release policy

- Authenticate every nonpublic route; validate project membership on object/artifact/job access. Test ID enumeration and cross-project access. Do not rely on UUID secrecy.
- Use maintained password hashing/session libraries, secure cookies in deployment, expiration/revocation, CSRF protection, CORS same-origin default and rate limits. No custom cryptography or browser-stored provider keys.
- Enforce upload byte/page/extraction-time limits and MIME validation; prevent path traversal/zip bombs; isolate parsing. Render extracted/model text as text or sanitized Markdown; never inject raw HTML. SVG/document previews must not execute untrusted scripts.
- Egress is restricted by component: model worker to configured provider/TrustGraph endpoints; Jena/OntoCheck normally network-disabled; evaluator no model calls. No unrestricted shell, Python eval, generated plugins, arbitrary file read, SPARQL SERVICE or remote OWL imports.
- Source content can contain prompt injection. Retrieval text is delimited evidence; model tools receive narrow capabilities and cannot read secrets, change policy, approve, or publish.
- Before live uploads, administrators configure whether a corpus may be sent to a cloud provider; confidential material is blocked when that policy does not permit it. Provider and retention metadata are recorded. Use synthetic/public data for demo and CI.
- Logs contain request/run/job IDs and safe error summaries. Raw source/model artifacts remain access-controlled, not printed to general logs. Redact keys, credentials and sealed answers from telemetry. Exports follow partition/redaction policy.
- Retention/deletion is an explicit admin workflow: document dependencies and evidence consequences, purge permitted private bytes and external retrieval indexes, retain only required audit metadata, and include backup retention in the policy. Do not promise hard deletion while immutable backups still retain data.
- Deployment: separate Compose services for API/worker/UI/proxy/PostgreSQL and real integration profiles. Database/artifact/Git volumes persist. An optional TrustGraph compose deployment connects over a private network; do not expose its admin endpoints publicly.
- Readiness covers migrations, DB and artifact access; service capability health is explicit. External outages degrade the relevant feature instead of corrupting accepted state.
- Back up PostgreSQL, artifacts, release Git repos, protocol/configs and required TrustGraph state. Manifest a consistent checkpoint and hashes; encrypt backups using deployment facilities; run a documented restore test. LLM prompts can be reproducible inputs without guaranteeing identical nondeterministic model output.
- CI runs offline/unit/browser tests plus real-tool integration jobs on pinned containers. Real provider/TrustGraph smoke tests use explicit opt-in credentials and public fixtures; they are required for the integrated-release gate, not run on every developer save.
- Operational defaults: non-root containers, explicit resource limits/timeouts, healthchecks, pinned images, secrets via environment/file injection, graceful termination and migration/rollback runbook. Hardware capacity is measured before committing to a host size.

## 11. Implementation tasks

Execute in dependency order. Each task produces a reviewable deliverable with its own test cycle. Create only files needed by the current task. Commit coherent increments; do not rewrite this plan as if unchecked tasks had already passed. Test snippets below describe contract assertions to implement using task-owned fixtures; they are not existing tests.

### T00 — Reconcile the repository, sources, tools and protocol decisions

**Depends on:** None. **Files:** Create/update `docs/sources.md`, `docs/decisions.md`, `docs/integrations.md`, `docs/protocol.md`, `PROJECT_MEMORY.md`; inspect existing `AGENTS.md`, repository and lockfiles. **Interfaces:** Produces a source manifest, target-path mapping and capability ledger consumed by every later task.

- [ ] Inspect actual repository, branch/worktree state and any existing demo; list working components versus absent code. Preserve existing stack conventions where compatible.
- [ ] Record S1–S11 source precedence, all named components, R01–R19, unresolved scientific decisions and proposed defaults. Make the full plan/spec available in the repo.
- [ ] In isolated feasibility environments, verify Java/Jena execution, OntoCheck pinned artifact/API/metrics and one TrustGraph ingestion/retrieval route. Capture versions, raw outputs, licenses, deployment resources and blockers. Do not claim full integration from documentation.
- [ ] Freeze the synthetic fixture semantics and provisional supported constructs. Select exact compatible runtime/tool versions in a decision record; any unsupported conceptual/structural assessment remains explicitly tracked.
- [ ] Review the ledger against §1 and commit with `docs: record ontology product sources and integration decisions`.

**Verification:** Each core component has `supported_and_tested`, `supported_but_unverified`, `unavailable` or `extension_needed`, with evidence/path and next step. Main-study-only decisions may remain pending; core integration blockers prevent a false M1/M3 completion claim.

### T01 — Durable application foundation, artifacts and jobs

**Depends on:** T00. **Files:** `pyproject.toml`, `uv.lock`, `.env.example`, `Makefile`, `src/ontology_engineering/app.py`, `domain/common.py`, `domain/artifacts.py`, `db/`, `storage/artifacts.py`, `jobs/`, `tests/integration/test_foundation.py`. **Interfaces:** Produces `ArtifactRef`, `SessionContext`, `ArtifactStore.put/read`, `JobQueue.enqueue/claim/heartbeat/complete`, ordered job events and migrations.

- [ ] Write a failing integration test for immutable artifact storage, duplicate job submission, lease recovery and persistent event sequence:

```python
assert store.put(b"same", "text/plain").digest == store.put(b"same", "text/plain").digest
assert queue.enqueue(command, key="k1").id == queue.enqueue(command, key="k1").id
assert recover_expired_lease(job_id).attempt == 2
```

- [ ] Run `uv run pytest tests/integration/test_foundation.py -q`; require failure for missing behavior.
- [ ] Implement DB schema/migrations, transactional job claims, bounded leases/checkpoints, authorized artifact indirection and API health. Store files atomically before marking DB references available; clean orphan temporary bytes safely.
- [ ] Run the test again plus `uv run ruff check .` and `uv run mypy src`; verify a worker restart does not lose the queued job/artifact.
- [ ] Commit `feat: add durable project artifacts and background jobs`.

### T02 — Accounts, project membership and access control

**Depends on:** T01. **Files:** `auth/`, `api/auth.py`, `api/projects.py`, `domain/common.py`, `db/migrations/`, `tests/security/test_access.py`. **Interfaces:** Produces authenticated `SessionContext` and `require_permission(actor, project_id, action) -> None`; project CRUD, membership/role mutation endpoints, versioned project settings with write-only secrets, and administrative account CLI.

- [ ] Add failing tests for login/session revocation, CSRF, viewer/reviewer separation and resource ownership:

```python
assert outsider.get(f"/api/v1/artifacts/{private_artifact}").status_code in (403, 404)
assert viewer.post(approval_url, json=approval).status_code == 403
assert logged_out_client.get("/api/v1/auth/me").status_code == 401
```

- [ ] Run `uv run pytest tests/security/test_access.py -q` and confirm the expected failures.
- [ ] Implement maintained password/session handling, role/membership rules, project scope on artifacts/jobs/events, login limits, secure-cookie config and admin account management. Keep public health responses minimal.
- [ ] Rerun the security tests and check cross-project run, evidence, export and event IDs as those routes are added later.
- [ ] Commit `feat: enforce project membership and authenticated review roles`.

### T03 — Ontology snapshots, safe patches, imports and semantic diff

**Depends on:** T01. **Files:** `domain/ontology.py`, `storage/ontology_repository.py`, `api/proposals.py`, `tests/unit/test_ontology_repository.py`, `tests/fixtures/ontology/`. **Interfaces:** Defines the provider-independent typed patch operation schema and `ProposalDraft` in `domain/ontology.py`; T08 consumes this schema. `stage_patch(base_id: str, draft: ProposalDraft) -> CandidateRevision`; `snapshot(revision_id: str) -> OntologyVersion`; `diff(base_id: str, revision_id: str) -> OntologyDiff`.

- [ ] Write failing tests for accepted/candidate isolation, malformed Turtle, full import snapshot, stale base and blank-node restrictions:

```python
assert accepted_digest_after_staging == accepted_digest_before_staging
assert semantically_equal_restriction_diffs == []  # differing blank-node labels
assert stale_base_request.status_code == 409
```

- [ ] Run `uv run pytest tests/unit/test_ontology_repository.py -q` and verify failure.
- [ ] Implement immutable snapshots, reviewed local import closure, typed patch operations and stable axiom/subgraph identities. Record the canonicalization method and tests; support full replacement + semantic diff where fragment editing is unsupported.
- [ ] Verify additions/deletions/restriction-list edits preserve parseability, schema/ABox isolation and history; run the test suite above.
- [ ] Commit `feat: stage versioned ontology patches with safe semantic diffs`.

### T04 — Real Apache Jena bridge and semantic checks

**Depends on:** T00, T03. **Files:** `services/jena-bridge/`, `adapters/jena.py`, `domain/reports.py`, `configs/reasoning.yaml`, `tests/integration/test_jena.py`. **Interfaces:** Defines `CheckRequest`, `CheckReport`, `QueryRequest`, `QueryResult`; implements `JenaAdapter.check/query` using immutable artifacts and a pinned Java executable.

- [ ] Write failing real-engine tests for the four categories in §6.3, asserted/inferred differences, query term normalization, unsupported constructs and process failures:

```python
assert expected_inference.outcome == "entailed"
assert incomplete.owl_outcome == "not_entailed"
assert incomplete.shacl_conforms is False
assert unsupported.status == "unsupported"
assert timed_out.status == "execution_error"
```

- [ ] Run `uv run pytest tests/integration/test_jena.py -m real_tools -q`; confirm missing bridge/capability failures. This command must not silently skip if the real-tools gate is requested.
- [ ] Implement JSON-over-stdin bridge, explicit graph/profile selection, inference, SHACL and bounded read-only SPARQL; capture tool versions, exact inputs and raw reports. Treat supported contradiction diagnostics honestly.
- [ ] Run bridge build/tests with `mvn -f services/jena-bridge/pom.xml test`, then the integration command; save the capability smoke output.
- [ ] Commit `feat: run profile-qualified Jena inference and SHACL checks`.

### T05 — Pinned OntoCheck assessments and comparable diffs

**Depends on:** T00, T03. **Files:** `adapters/ontocheck.py`, `domain/reports.py`, `configs/ontocheck.yaml`, `tests/integration/test_ontocheck.py`, `tests/unit/test_assessment_comparison.py`. **Interfaces:** Defines `AssessmentRequest`, `AssessmentReport`, `AssessmentDiff`; implements `OntoCheckAdapter.assess/compare` from §5.3.

- [ ] Write failing tests for fixed-term coverage/utilisation changes, same-local-name different-IRI ambiguity, approved versus suggested mappings, zero denominators, raw schema changes and missing metrics:

```python
assert candidate.coverage.value > base.coverage.value
assert with_irrelevant_terms.utilisation.value < base.utilisation.value
assert suggested_mapping.is_approved is False
assert unavailable.value is None and unavailable.capability == "unavailable"
assert incompatible_comparison.error_code == "ASSESSMENT_CONTEXT_MISMATCH"
```

- [ ] Run `uv run pytest tests/unit/test_assessment_comparison.py tests/integration/test_ontocheck.py -q`; inspect failing fake/real cases separately.
- [ ] Inspect installed pinned code, implement isolated invocation and output normalization; persist raw labels, per-metric availability, denominators, terms/questions, scope/import/mapping digests and comparison refusal. Disable automatic semantic authorization from names/prefixes.
- [ ] Run `uv run pytest tests/integration/test_ontocheck.py -m real_tools -q` on actual base/candidate fixtures; persist reports and tested-capability ledger, including unavailable conceptual/structural fitness if applicable.
- [ ] Commit `feat: integrate versioned OntoCheck assessments and honest capability states`.

**M1 gate:** T01/T03/T04/T05 provide a reproducible `uv run python scripts/smoke_kernel.py` with separate real Jena and OntoCheck base/candidate reports. Document a blocker rather than pretending a fake satisfies this gate. Implement that script as part of this task.

### T06 — Versioned document ingestion, evidence and TrustGraph

**Depends on:** T01, T02. **Files:** `domain/documents.py`, `documents/`, `adapters/trustgraph.py`, `api/documents.py`, `tests/unit/test_evidence.py`, `tests/integration/test_trustgraph.py`. **Interfaces:** Defines `CorpusVersion`, `IngestionReceipt`, `RetrievalRequest`, `EvidenceBundle`; implements `RetrievalAdapter.ingest/retrieve`, versioned extraction and passage lookup.

- [ ] Write failing tests for document supersession, correct extraction offsets, duplicate upload idempotency, missing provenance, parser failure and forged source IDs:

```python
assert evidence.document_version_id == original_version.id
assert extracted_text[evidence.start:evidence.end] == evidence.quote
assert retrieval_without_locator.status == "blocked_missing_provenance"
```

- [ ] Run `uv run pytest tests/unit/test_evidence.py -q` and confirm failure.
- [ ] Implement bounded upload/extraction jobs, original/extracted artifact retention, explicit scanned-PDF behavior and deterministic retrieval fake. Then integrate the verified TrustGraph API with project/corpus isolation and local immutable evidence reconciliation.
- [ ] Run unit tests and `uv run pytest tests/integration/test_trustgraph.py -m live_trustgraph -q`; the live smoke ingests one public fixture and reopens the exact returned source passage/version. Test outage/retry without fallback-to-fake behavior.
- [ ] Commit `feat: ground retrieved evidence in immutable document versions`.

### T07 — Requirements, approved scenarios and sealed dataset packs

**Depends on:** T02, T03, T04. **Files:** `domain/requirements.py`, `requirements/`, `api/requirements.py`, `fixtures/demo/`, `tests/unit/test_dataset_packs.py`, `tests/security/test_partition_access.py`. **Interfaces:** Defines `DatasetPack`, `ScenarioVersion`, `ScenarioDraftBatch`, `approve_scenario(draft_id, actor) -> ScenarioVersion`, `freeze_pack(request, actor) -> DatasetPack` and scoped pack readers.

- [ ] Write failing tests for draft versus approved expectations, all four categories, pack immutability, normalized ASK/SELECT answers and sealed access:

```python
assert draft_scenario.can_be_reference is False
assert frozen_pack.digest != modified_successor_pack.digest
assert development_capability.read(held_out_pack.id).denied is True
```

- [ ] Run `uv run pytest tests/unit/test_dataset_packs.py tests/security/test_partition_access.py -q` and confirm failure.
- [ ] Implement CQ/scenario authoring/review, explicit query semantics and partitioned storage; prepare tiny fictional development fixtures and a separately permissioned synthetic held-out test pack. Label development approvals as fixture metadata, not real expert participation.
- [ ] Verify generated expectations cannot self-approve and held-out data is absent from normal API/search/artifact lists; rerun tests.
- [ ] Commit `feat: version reviewed competency questions and isolated evaluation packs`.

### T08 — Provider adapter and the two agent roles

**Depends on:** T03, T06, T07. **Files:** `adapters/llm.py`, `agents/proposal_agent.py`, `agents/test_generation_agent.py`, `domain/runs.py`, `tests/unit/test_agents.py`. **Interfaces:** Defines `ModelRequest/Response`, `BudgetReservation`, `ProposalContext`, `RevisionContext`, `ScenarioContext`; consumes `ProposalDraft` from T03 and `ScenarioDraftBatch` from T07; implements `LLMProvider.generate`, `ProposalAgent.propose/revise`, `TestGenerationAgent.draft`.

- [ ] Write failing deterministic-provider tests for schema validation, evidence references, unapproved mappings, malicious source instructions, truncated responses and role separation:

```python
assert proposal.output_kind == "ontology_patch"
assert draft_tests.output_kind == "scenario_drafts"
assert fabricated_evidence.status == "invalid_output"
assert agent_capabilities.can_publish is False
```

- [ ] Run `uv run pytest tests/unit/test_agents.py -q` and confirm failure.
- [ ] Implement provider-neutral HTTP/SDK boundary for the chosen provider, structured outputs, deterministic fake, prompt versioning and allowed-tool schemas. Validate referenced evidence, ontology parseability and patch scope; return drafts only. Test-agent outputs stay declarative and unapproved.
- [ ] Rerun tests and one opt-in public-fixture provider smoke; record provider/model identity and actual structured-output compatibility without treating generated content as correct by default.
- [ ] Commit `feat: add bounded ontology proposal and scenario-generation agents`.

### T09 — Workflow controller, feedback isolation, budgets and cancellation

**Depends on:** T01, T04, T05, T08. **Files:** `workflow/`, `agents/feedback_policy.py`, `configs/conditions.yaml`, `api/runs.py`, `tests/unit/test_workflow.py`, `tests/security/test_feedback_policy.py`. **Interfaces:** Defines `StartRun`, `RunRef/Status`, `FeedbackRequest/Envelope`; implements `WorkflowController.start/advance/cancel` and `FeedbackPolicy.build`.

- [ ] Write failing tests for bounded repair, matched B/C allowances, feedback sentinels, cancellation and uncertain external-call retry:

```python
assert "ONTOCHECK_SENTINEL" not in serialized(b_prompt)
assert "ONTOCHECK_SENTINEL" not in serialized(c_prompt)
assert c_feedback.kinds == {"failed_entailment"}
assert run_after_limit.stop_reason == "budget_exhausted"
assert ambiguous_call.retry_automatically is False
```

- [ ] Run `uv run pytest tests/unit/test_workflow.py tests/security/test_feedback_policy.py -q`; confirm failure.
- [ ] Implement persisted state transitions/checkpoints, budget reservation, redacted progress events and cancellation. Apply policy before assembling prompts/tool outputs; no unrestricted report-reading capability. Preserve failures/partial candidates.
- [ ] Rerun tests with provider timeouts, malformed outputs, duplicate delivery and worker restart; confirm no hidden budget-resetting retry.
- [ ] Commit `feat: orchestrate recoverable condition-scoped ontology refinement`.

### T10 — Human review, mapping approval and timing

**Depends on:** T02, T03, T05, T07, T09. **Files:** `domain/review.py`, `review/`, `api/reviews.py`, `configs/acceptance.yaml`, `tests/unit/test_review_gate.py`, `tests/unit/test_review_timing.py`. **Interfaces:** Defines `ReviewCommand/Result`, `ApprovalCommand`, `Approval`; implements `ReviewService.decide/approve`, mapping-version updates and timing events.

- [ ] Write failing tests for exact revision/context, per-change subset assembly, source-fidelity attestation, edits/mapping invalidation and role checks:

```python
assert approve(old_revision, current_context).error_code == "STALE_APPROVAL"
assert approve(candidate_with_failed_required_check).error_code == "CHECKS_REQUIRED"
assert approved_mapping.successor_revision_id != original_revision.id
assert stopped_timer.active_seconds == expected_visible_unpaused_seconds
```

- [ ] Run `uv run pytest tests/unit/test_review_gate.py tests/unit/test_review_timing.py -q`; confirm failure.
- [ ] Implement accept/modify/reject/request-changes records, dependency resolution and successor rechecks, full-context operational approval, explicit human identity, configurable blocking policy and auditable timing. Store producing-reviewer fidelity attestation separately from later independent study acceptance. No score-only acceptance or historic approval reuse.
- [ ] Rerun tests for concurrent reviewers, pause/idle/reconnect, unsupported metrics and rebase; verify source-fidelity objections block acceptance until resolved under the same policy.
- [ ] Commit `feat: bind human review and approval to exact checked revisions`.

### T11 — Web shell, onboarding and complete review workbench

**Depends on:** T02, T06, T07, T09, T10. **Files:** `web/package.json`, `web/src/app/`, `web/src/api/`, `web/src/features/{projects,documents,requirements,scenarios,runs,review,settings}/`, `web/src/components/`, `web/tests/review.spec.ts`, `web/tests/accessibility.spec.ts`. **Interfaces:** Typed client generated from FastAPI OpenAPI; consumes §9 routes; URL-addressed revision state and SSE reconnect.

- [ ] Write failing browser tests for the useful journey, required-check blockers, null/unavailable metrics, evidence navigation, refresh/reconnect and keyboard controls:

```typescript
await expect(page.getByRole('button', { name: 'Approve revision' })).toBeDisabled();
await expect(page.getByText('Structural fitness unavailable')).toBeVisible();
await expect(page.getByTestId('evidence-document-version')).toHaveText(originalVersion);
```

- [ ] Run `npm --prefix web run test:e2e -- review.spec.ts accessibility.spec.ts`; verify failure against the test environment.
- [ ] Implement the project/document/requirements/scenario/run/review/settings routes in §3, including scenario expectation approval, membership management, write-only provider configuration/connection test and integration/budget status. Add seeded-demo onboarding, an editable structured axiom form, diff/evidence panels, separate reports, selection/recheck/approval, recoverable errors and accessible responsive behavior. Render unknown/unsupported/errors explicitly.
- [ ] Run `npm --prefix web run typecheck`, `npm --prefix web test -- --run`, `npm --prefix web run build`, and the browser tests. Inspect desktop and narrow-screen screenshots for overflow, focus, status clarity and empty/error states.
- [ ] Commit `feat: deliver an accessible evidence-linked ontology review workspace`.

### T12 — Atomic approved release publication, lineage and history UI

**Depends on:** T03, T10, T11. **Files:** `storage/release_repository.py`, `exports/release_bundle.py`, `api/releases.py`, `web/src/features/releases/`, `tests/integration/test_publication.py`, `web/tests/publication.spec.ts`. **Interfaces:** Defines `PublishCommand`, `ReleaseRef`, implements `PublicationService.publish` plus intent reconciler, per-project Git storage, and `build_release_bundle(release_id, actor) -> ArtifactRef` for a basic policy-filtered download.

- [ ] Write failing tests for publication base lock, duplicate submission, stale/missing approval, crash between Git and DB, and accepted-only visibility:

```python
assert publish_twice(same_command).release_count == 1
assert competing_old_base.error_code == "BASE_CONFLICT"
assert recover_after_git_commit().git_commit == first_attempt_commit
assert published_snapshot.contains_test_abox is False
```

- [ ] Run `uv run pytest tests/integration/test_publication.py -q`; confirm failure.
- [ ] Implement intent/outbox, deterministic per-project Git commit, reconciliation, finalized release pointer and linked manifest/history UI. Provide a basic verified release download containing Turtle, release/evidence/check/approval manifests and permitted supporting reports, without waiting for the experiment subsystem. Implement revert as a new checked proposal.
- [ ] Rerun integration and browser publication tests; verify approval/context/report/evidence links resolve, the basic release download passes hash/permission checks, and rejected/failed candidates remain retained separately.
- [ ] Commit `feat: publish approved ontology releases atomically with audit lineage`.

**M2 gate:** A logged-in reviewer can use the fictional demo from document/evidence through checked revision to final approval, release and download; restarting services preserves history. Label fake/live capabilities precisely.

### T13 — Entity browser, ontology graph and inference inspection

**Depends on:** T03, T04, T11. **Files:** `api/queries.py`, `web/src/features/ontology/`, `web/src/components/EntityGraph.tsx`, `tests/unit/test_entity_queries.py`, `web/tests/ontology.spec.ts`. **Interfaces:** Produces paginated `EntitySummary`, bounded `OntologyNeighborhood`, and asserted/inferred `QueryResult` views for a selected revision/profile.

- [ ] Add failing tests for full-IRI ambiguity, graph caps, schema/ABox separation and asserted/inferred labeling:

```python
assert same_label_entities[0].iri != same_label_entities[1].iri
assert len(neighborhood.nodes) <= 200
assert inferred_result.profile_id == selected_profile
```

- [ ] Run `uv run pytest tests/unit/test_entity_queries.py -q`; confirm failure.
- [ ] Implement class/property tree, graph neighborhood using a maintained graph renderer, searchable details and definitions, diff overlay and query-result table. Provide keyboard/table alternatives and avoid unstable blank-node labels as user-facing identifiers.
- [ ] Rerun API/browser tests; manually inspect a cyclic/multi-parent hierarchy and a large capped graph.
- [ ] Commit `feat: inspect ontology entities and profile-qualified inferred results`.

### T14 — Grounded expert questions and controlled explanations

**Depends on:** T04, T06, T08, T11, T13. **Files:** `queries/`, `api/queries.py`, `web/src/features/questions/`, `tests/security/test_query_policy.py`, `tests/unit/test_grounded_answers.py`, `web/tests/questions.spec.ts`. **Interfaces:** `answer_question(request: QuestionRequest, actor: SessionContext) -> GroundedAnswer`; `execute_query(request: QueryRequest, actor: SessionContext) -> QueryResult`.

- [ ] Write failing tests for citations/version, no-support answers, unauthorized graph access, AST-rejected remote/update queries, and RQ3 explanation restrictions:

```python
assert unsupported_answer.kind == "insufficient_evidence"
assert execute_query(service_query).error_code == "QUERY_NOT_ALLOWED"
assert explanation_control_session.request_explanation().status_code == 403
```

- [ ] Run `uv run pytest tests/security/test_query_policy.py tests/unit/test_grounded_answers.py -q`; confirm failure.
- [ ] Implement narrow retrieval/report-grounded answers and AST-based read-only query controls with limits. Link exact evidence/reports; mark modelling suggestions; no automatic patch execution and no invented derivations.
- [ ] Rerun API/browser tests with malicious document text, prompt injection and unavailable inference/evidence.
- [ ] Commit `feat: answer expert questions with scoped evidence and inference links`.

### T15 — Frozen A–D execution and matched comparison manifests

**Depends on:** T07, T09, T10, T12. **Files:** `domain/experiments.py`, `evaluation/protocol.py`, `evaluation/runner.py`, `api/experiments.py`, `tests/unit/test_experiment_runner.py`, `tests/security/test_experiment_blinding.py`. **Interfaces:** Defines `ExperimentProtocol`, `ExperimentRun`, `FreezeCommand`, `FrozenOutput`; `run_conditions(protocol_id, task_ids, actor) -> ExperimentBatch`; implements `EvaluationService.freeze`.

- [ ] Write failing tests for common input digests, paired B/C seed candidate, shared C/D automated checkpoint, A no-revision and freeze-before-scoring:

```python
assert runs["B"].initial_candidate_id == runs["C"].initial_candidate_id
assert runs["B"].budget == runs["C"].budget
assert runs["D"].automated_checkpoint == runs["C"].automated_checkpoint
assert runs["A"].revision_count == 0
assert freeze_rejected_candidate.is_valid is True
```

- [ ] Run `uv run pytest tests/unit/test_experiment_runner.py tests/security/test_experiment_blinding.py -q`; confirm failure.
- [ ] Implement immutable protocol, paired/replicate IDs, condition-scoped execution and typed freezes (`production`, `pre_review`, `post_review`, `post_correction`) including failed/unapproved outputs. Preserve production versus common-correction lineage; freeze final A–C correction and D post-review outputs for RQ4. Freeze tests and expectations before arm execution. Record failure categories and all attempted calls.
- [ ] Rerun tests and a fake-provider A–D smoke; prove unrelated OntoCheck/held-out sentinels cannot reach any repair prompt or tool output.
- [ ] Commit `feat: run and freeze controlled ontology experiments across four conditions`.

### T16 — Independent evaluation worker and reference scoring

**Depends on:** T05, T07, T15. **Files:** `evaluation/scorer.py`, `evaluation/metrics.py`, evaluator process entry point, evaluator DB/storage roles, `tests/security/test_evaluator_isolation.py`, `tests/unit/test_repair_metrics.py`. **Interfaces:** Defines `ScoreRequest`, `EvaluationReport`; implements `EvaluationService.score`; normal agent/API credentials cannot instantiate sealed pack readers.

- [ ] Write failing tests for evaluator-only credentials, all-assigned-case denominators, source-fidelity reference independence and metric context equality:

```python
assert repair_report.assigned_cases == successes + unsuccessful_cases
assert repair_that_breaks_protected_entailment.correct is False
assert failed_generation.included_in_accounting is True
assert published_but_source_inconsistent.study_accepted is False
assert development_worker.can_open_reference is False
```

- [ ] Run `uv run pytest tests/security/test_evaluator_isolation.py tests/unit/test_repair_metrics.py -q`; confirm failure.
- [ ] Implement frozen-output scoring with held-out Jena/CQ checks, same-config OntoCheck assessments and independently approved reference judgments. Add `IndependentAcceptanceVerdict` on the final RQ4 correction snapshot, with separate logical/CQ/regression and independent source-fidelity outcomes under the common rubric; a producing-reviewer attestation cannot set this verdict. Record missing judgments as unavailable, not fabricated truth; keep evaluator outputs outside feedback data stores.
- [ ] Rerun tests with malformed outputs, timeouts, no eligible cases, incompatible metric config and forbidden attempts to score an unfrozen output.
- [ ] Commit `feat: independently score frozen outputs without evaluation leakage`.

### T17 — Review study allocation, RQ dashboards and effort analysis

**Depends on:** T10, T11, T14, T15, T16. **Files:** `evaluation/allocations.py`, `evaluation/metrics.py`, `web/src/features/experiments/`, `tests/unit/test_review_allocations.py`, `tests/unit/test_study_metrics.py`, `web/tests/study_mode.spec.ts`. **Interfaces:** `allocate_review_cases(protocol_id, reviewers) -> AllocationManifest`; `summarize_experiment(experiment_id, actor) -> StudySummary` with explicit numerator/denominator and censoring fields.

- [ ] Write failing tests for RQ3 no-repeat exposure, identical source access/UI signals, RQ2 before/after reference comparison and RQ4 all-effort/censoring accounting:

```python
assert len(exposures_for(reviewer, proposal)) <= 1
assert explanation_treatment.source_access == explanation_control.source_access
assert over_budget.accepted is False and over_budget.right_censored is True
assert summary.expert_time.includes_common_correction_stage is True
assert counterbalanced_rq4.all_arms_presented_under_common_policy is True
assert final_assessment.snapshot_kind in {"post_review", "post_correction"}
```

- [ ] Run `uv run pytest tests/unit/test_review_allocations.py tests/unit/test_study_metrics.py -q`; confirm failure.
- [ ] Implement counterbalanced RQ3 allocation/exposure ledger and RQ4 correction-stage presentation/task order, immutable review assignments, RQ1–4 tables and uncertainty-ready raw exports. Use independent final acceptance verdicts for RQ4, retaining failed independent assessments separately from producing-reviewer approval. Distinguish active/wall time, production versus correction stages, source-fidelity results and secondary OntoCheck outcomes.
- [ ] Run tests and browser mode tests; confirm explanation requests cannot bypass the control condition, pilots are excluded from main analysis, and synthetic reviewer data is labeled simulation.
- [ ] Commit `feat: support controlled explanation review and complete study accounting`.

### T18 — Release exports and reproducibility bundles

**Depends on:** T12, T15, T16, T17. **Files:** `exports/`, `evaluation/exports.py`, `api/exports.py`, `scripts/export_run.py`, `scripts/verify_bundle.py`, `tests/unit/test_exports.py`. **Interfaces:** Extends T12's existing `build_release_bundle(release_id, actor) -> ArtifactRef` without changing its operational download contract; defines `build_reproducibility_bundle(experiment_id, actor, scope) -> ArtifactRef`; `verify_bundle(path) -> VerificationResult`.

- [ ] Add failing tests for hash-verified manifests, artifact completeness, permission filtering, private-source redaction and sealed export restrictions:

```python
assert verify_bundle(release_bundle).ok is True
assert public_bundle.contains_provider_secret is False
assert reviewer_bundle.contains_held_out_answers is False
assert missing_required_artifact.status == "incomplete"
```

- [ ] Run `uv run pytest tests/unit/test_exports.py -q`; confirm failure.
- [ ] Extend the existing release bundle with optional policy-permitted reproducibility details; implement separate machine-readable JSON/CSV evaluation results, configs/tool/model/prompt versions, per-question diagnostics and reproduction commands. Private original source bytes are included only when policy/role permits.
- [ ] Verify a bundle in a fresh directory; exact artifacts/reports reproduce where deterministic. Clearly record that remote model regeneration can vary.
- [ ] Commit `feat: export auditable ontology releases and reproducible experiment records`.

### T19 — Private deployment, recovery, monitoring and restore

**Depends on:** T01, T02, T04–T06, T09, T12, T18. **Files:** `compose.yaml`, `infra/`, `scripts/backup.py`, `scripts/restore.py`, `docs/operations.md`, `docs/privacy.md`, `.github/workflows/ci.yml`, `tests/integration/test_recovery.py`, `tests/security/test_surface.py`. **Interfaces:** Defines reproducible demo/pilot/study service profiles and backup manifest version 1.

- [ ] Write failing recovery/security tests for worker loss, external-call uncertainty, Git/DB reconciliation, cross-project downloads, upload/query egress and backup integrity:

```python
assert restored_release.digest == original_release.digest
assert recovered_publish.finalized_release_count == 1
assert interrupted_unknown_call.was_silently_retried is False
assert sealed_path_is_mounted_in_development_worker is False
```

- [ ] Run `uv run pytest tests/integration/test_recovery.py tests/security/test_surface.py -q`; confirm missing behavior.
- [ ] Implement pinned non-root containers, TLS/private-network runbook, persistent volumes, migration sequence, health/readiness, safe logs and service metrics (queue lag, failures, cost/budget, tool health). Include TrustGraph operational dependencies and retention/index cleanup.
- [ ] Run the tests, `docker compose config --quiet`, build/start clean demo and live-integration profiles, restart services mid-job, and complete a backup/restore drill to an isolated instance. Record hardware and measured resource use.
- [ ] Commit `ops: deploy and restore the private ontology engineering workspace`.

### T20 — End-to-end pilot acceptance and honest handoff

**Depends on:** T00–T19. **Files:** `tests/acceptance/test_product_journey.py`, `web/tests/product-journey.spec.ts`, `README.md`, `docs/integrations.md`, `docs/protocol.md`, `PROJECT_MEMORY.md`, `docs/acceptance.md`. **Interfaces:** Produces the M3 integrated-product evidence pack and M4 research-readiness checklist; no invented expert results.

- [ ] Add a complete acceptance fixture: ingest a versioned public document, prepare a reviewed development pack, retrieve real evidence, propose with a real configured provider, draft scenarios with the second agent, check with Jena, assess with pinned OntoCheck, review/edit/recheck, approve and publish, ask a grounded question, inspect inferred results and verify export.
- [ ] Run targeted acceptance tests first and fix integration failures; then run `make check` (defined in §12) with real-tool and browser gates. Save logs/artifact IDs rather than merely recording “passed.”
- [ ] Exercise A–D with separate evaluator credentials; inspect actual prompts/access logs for blinding, budgets, pre/post D snapshots, all-output retention and RQ3 control behavior. Validate reporting on known synthetic scores without calling them study findings.
- [ ] Have a real intended reviewer complete the private pilot journey when available; record usability failures, review time instrumentation limits, accessibility and measured performance. If no participant/final corpus exists, mark the corresponding study gates pending while delivering the working capability.
- [ ] Update README, capability ledger and project memory with verified commands, versions, blockers, limitations and next scientific decisions. Commit `docs: record integrated product acceptance and research readiness`.

## 12. Execution, verification, delivery and future work

### 12.1 Required command contract

T01/T11/T19 create these commands/scripts; they are target interfaces, not commands claimed to work in the current source-only workspace.

| Command | Required behavior |
|---|---|
| `uv sync --frozen` | Reproduce locked backend environment. |
| `npm --prefix web ci` | Reproduce locked frontend environment. |
| `make dev` | Start API/worker/UI against documented local dependencies. |
| `make demo` | Start labeled fictional demo, create demo account via safe setup, seed synthetic data; no cloud keys required. |
| `make kernel-smoke` | Real pinned Jena + OntoCheck deterministic fixture; emit separate reports and capability ledger. |
| `make check` | Lint/typecheck, offline software tests, pinned real Jena/OntoCheck integration tests, bridge tests, frontend unit/build/browser acceptance and applicable security tests; nonzero on required missing tool. |
| `make live-smoke` | Explicitly configured real TrustGraph + provider public-fixture round-trip; unavailable credentials are an unexecuted gate, never a pass. |
| `make backup` / `make restore` | Manifested consistent backup and restore to a specified isolated destination. |
| `make verify-bundle BUNDLE=...` | Hash and required-artifact verification, without evaluating arbitrary code from the bundle. |

Unit tests use deterministic fakes. Integration tests prove actual pinned tooling. Tests should assert semantic/workflow behavior and user risks, not mirror private implementation details or call paid providers by default. Do not repeatedly broaden tests after relevant checks pass unless a new change/failure justifies it.

### 12.2 Final acceptance checklist

- [ ] A fresh private deployment can be installed from documented locks/configuration, login works and project membership is enforced.
- [ ] A new user can complete the bounded demo journey without editing backend files, and fake/live states are visible.
- [ ] Real TrustGraph evidence survives original document supersession and resolves to immutable source passages.
- [ ] Both agent roles work through the configured provider and cannot publish, read held-out material, or self-approve references.
- [ ] Real Jena inference/SHACL/query/regression checks and pinned OntoCheck base/candidate reports are separate and traceable.
- [ ] Conceptual/structural metric availability is proven or explicitly unresolved with an approved scoped decision; no fabricated score or mislabeled substitute.
- [ ] Class/property/definition/axiom/reuse-mapping changes are inspectable with evidence, semantic diff, graph/tree view and inferred results.
- [ ] Accept/modify/reject/request-changes, per-change dependencies, stale revision conflicts and mandatory rechecks work through the browser.
- [ ] Only an exact validated human-approved candidate can become the next accepted release; duplicate/crashed publication recovers safely.
- [ ] Natural-language questions return grounded explanations/results or lack-of-support responses, respecting RQ3 session restrictions.
- [ ] A–D share frozen inputs; B/C budgets and permitted feedback are controlled; held-out/reference data is backend-isolated.
- [ ] Independent evaluation accepts frozen failed/unapproved candidates; RQ4 final corrected outputs receive a distinct independent acceptance verdict, with counterbalanced presentation, all effort and unsuccessful/censored cases retained.
- [ ] Export bundles verify; confidential/held-out artifacts are appropriately restricted; backups restore complete lineage and source/report links.
- [ ] Real integration, browser, security, recovery and accessibility checks have stored evidence; pending scientific work is clearly marked.

### 12.3 Codex session protocol

At session start: inspect repository state, read applicable `AGENTS.md`, this file, `PROJECT_MEMORY.md`, and the current task's files. Summarize only material source/code mismatches. Work on the next dependency-ready task; update its boxes only after the verification command succeeds. Read neighboring interfaces before changing them.

At task end: report behavior implemented, tests actually run, results and unresolved limitations. Record dated decisions, exact versions/profiles, commits/artifacts, confirmed working components and next task in `PROJECT_MEMORY.md`. Do not manufacture progress or overwrite historical research settings. Commit small coherent changes; preserve unrelated user work.

If a core tool fails, investigate and record the specific compatibility gap, keep honest unavailable states, and continue independent tasks where possible. Do not remove the tool, substitute a fake in live mode, change the scientific comparison, or relax acceptance without an explicit recorded decision.

### 12.4 Suggested first implementation instruction

> Read `developPlan.md`, the repository's `AGENTS.md`, and `PROJECT_MEMORY.md` if present. Inspect the actual repository and sources. Implement T00, then T01/T03/T04/T05 in dependency order to deliver the M1 deterministic semantic kernel, including **real Apache Jena and pinned OntoCheck** with separate persisted reports. Verify exact upstream interfaces before coding adapters. Add meaningful tests and record actual capabilities/blockers. Do not claim an integration is complete from a fixture fake or a dependency declaration. After M1, continue the remaining tasks in dependency order within the execution scope authorized for this session.

### 12.5 Later extensions, after required gates

Optional modified Delphi rounds; reviewed FIBO reuse and Ontology RAG; a dedicated OWL 2 DL reasoner when required; separately labeled OntoCheck-guided automated repair experiments; OCR for scanned corpora; object storage; more advanced collaborative editing. Each changes only its documented scope and needs its own capabilities/tests; none replaces the core requirements above.
