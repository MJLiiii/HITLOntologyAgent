# Studio frontend contract

The Studio is a React/TypeScript application with a standalone Vite development entry and a TrustGraph IIFE plugin entry. All workflow reads and writes go through the project-owned same-origin `/api/v1` API. No service secrets or automatic approvals are embedded in the browser.

`make api-contracts` exports the actual FastAPI OpenAPI document to `docs/openapi.json` and deterministically generates request-only types in `apps/studio-plugin/src/api/openapi.ts`; `make check-api-contracts` checks reproducibility. Response view models in the legacy-named `generated.ts` are hand-owned, since current response handlers return generic dictionaries. Backend runtime constraints remain authoritative.

## Experience

A persistent left navigation exposes Chat, Ontology, Sources, Proposals, Validation, and Experiments. Project, demo classification, approved version, and corpus snapshot remain visible. Chat is the first screen: an evidence-grounded conversation, inspectable citations, and ontology triples returned with answers. Ontology includes read-only approved vocabulary and immutable version history. Proposals combines revision diff, evidence, expert review, and publication. Validation separates logical checks from vocabulary/fitness assessment. Experiments includes A–D filters and export.

Sources also exposes the current scope, saved immutable scope versions, explicit human scope decisions, and staged Turtle seed import. Editing the scope/domain label does not select an organizational study domain: this deployment remains restricted to the synthetic demo and its fixed namespace. Saving scope clears its acceptance. A seed import creates an unvalidated proposal against the inspected frozen corpus; it never creates an approved version.

The visual design uses a light warm canvas, white panels, navy text, indigo actions, subtle borders, compact tables, and a narrow persistent context rail. Responsive navigation collapses on small screens. Every action has a disabled/loading/error state and eligible-state reason. Source/model content is rendered as escaped text.

## API contract

List responses are `{items: T[], next_cursor: string | null}`. API errors are `{code, message, details?, correlation_id?}`. Identifiers are opaque strings. Dates are ISO strings. JSON responses should not include secrets. Decimal metrics are fractions (0–1), and unavailable metrics are null with an optional reason.

- `GET /session` → actor, mode and model mode. An existing authenticated cookie or operator-provided `X-OE-Session-Token` establishes the human session. The frontend consumes a `#session=…` bootstrap fragment, clears it after success, and never persists the token in browser storage. An unauthenticated browser shows a local token entry form.
- `GET /projects` → project list. Project: `id, name, domain, description?, approved_version_id, corpus_snapshot_id, pending_publication_id?, scope_digest, scope_accepted, review_policy_id?, mode?` (`mode: demo` for synthetic fixture).
- `GET /projects/{p}` → Project.
- `GET /projects/{p}/scope` → current ScopeVersion, including the initial reference when no scope version has been saved: `id: string | null, title, purpose, namespace, digest, status?, accepted, competency_questions, shapes_ttl, fixtures_ttl, created_at?`.
- `GET /projects/{p}/scopes` → saved immutable ScopeVersion list. Historical scopes are inspectable, never accepted by silently switching the current scope.
- `POST /projects/{p}/scope` → append a scope version with `{title, purpose, namespace: "https://example.org/oe-demo/", competency_questions, shapes_ttl, fixtures_ttl}`. Each question is `{id, question, sparql_query, expected: boolean, required: true}`. One to twenty unique IDs; only explicit boolean ASK oracles are supported. The server parses SPARQL/Turtle. Saving resets scope acceptance and does not mutate earlier candidate bundles.
- `POST /projects/{p}/scope-decisions` → explicit human decision with `{scope_digest, decision: "accept" | "reject", rationale}`. The UI refreshes the current scope digest before posting and requires a written rationale. A negative ASK expectation means non-entailment in the test graph, not proof of negation.
- `POST /projects/{p}/seed-imports` → JobRef from `{ontology_ttl, corpus_snapshot_id, profile: "rdfs", rationale}`. Available only before the first approved release and without a pending publication. The UI accepts pasted Turtle or a local `.ttl` file, bounded to 1 MiB and the server's 100-operation change limit. Successful result is `{proposal_id, revision, bundle_digest}`; validation, assessment, review, acceptance and publication remain separate.
- `GET /projects/{p}/versions` → Version list. Version: `id, label, created_at, commit?, parent_version_id?, status, triple_count, class_count, property_count, triples: Triple[], reviewer?, source_snapshot_id?, publication_id?, bundle_digest?, manifest?`.
- `GET /projects/{p}/documents` → SourceDocument list. Source: `id, title, edition, classification, status, created_at, chunk_count?, content_hash?, error?, text?`. Status distinguishes `uploaded`, `queued`, `processing`, `complete`, `incomplete`, `failed`; source responses may include ingestion/extraction diagnostics.
- `POST /projects/{p}/documents` multipart `file, title, edition, rights, classification` → SourceDocument. The local source adapter accepts UTF-8 `.txt`/`.md` and text-based `.pdf`, up to 20 MiB. Incomplete PDF extraction remains visible and cannot enter a frozen corpus.
- `POST /projects/{p}/ingestions` `{document_id, configured_flow_key: "default"}` → JobRef.
- `POST /projects/{p}/corpus-snapshots` `{ingestion_run_ids}` → immutable snapshot. Document response `ingestion_run_id` identifies its completed processing run.
- `GET /projects/{p}/proposals` → ProposalSummary list: `id, title, revision, status, base_version_id, bundle_digest, created_at, summary?, stale?, validation_run_id?, assessment_run_ids?`.
- `GET /projects/{p}/proposals/{id}/revisions/{r}` → Revision: summary fields plus `rationale, additions: Triple[], deletions: Triple[], evidence: Evidence[], assumptions?: string[], history?: HistoryEvent[], validation?, assessment?, approval_ids?, review_eligibility?: {eligible: boolean, reasons: string[]}`.
- `POST /projects/{p}/proposal-jobs` `{base_version_id, corpus_snapshot_id, competency_question_ids: [], instruction}` → JobRef.
- `POST /projects/{p}/proposals/{id}/revisions` `{parent_revision, structured_changes: {additions: Triple[], deletions: Triple[]}, rationale}` with `If-Match` revision → Revision.
- `POST /projects/{p}/validation-jobs` `{proposal_id, revision, bundle_digest}` → JobRef.
- `POST /projects/{p}/repair-jobs` same bundle request → JobRef. The UI offers repair only after failed validation on a current candidate with no pending publication. The backend admits failed competency-question diagnostics only, bounds attempts to two per proposal, and returns `{proposal_id, revision, bundle_digest, repair_attempt}` for the successor. Required checks must run again; no acceptance is implied.
- `POST /projects/{p}/assessment-jobs` same request → JobRef.
- `POST /projects/{p}/test-generation-jobs` `{proposal_id, revision}` → JobRef whose result contains `{id, status: "needs_review", digest, revision_id, bundle_digest, tests}`.
- `GET /projects/{p}/test-suites` → TestSuite list. Queries, fixtures, rationale and expected results are displayed as untrusted data.
- `POST /projects/{p}/test-oracle-decisions` `{test_suite_id, test_suite_digest, decision, rationale}` → decision or new successor Revision after acceptance. Human oracle acceptance preserves required sentinels and does not validate or approve the successor.
- `POST /projects/{p}/review-submissions` `{proposal_id, revision, validation_run_id, required_assessment_run_ids}` with `If-Match` → eligibility/revision response.
- `POST /projects/{p}/reviews` `{proposal_id, revision, bundle_digest, validation_run_id, required_assessment_run_ids, decision, rationale, review_policy_id}` → ReviewDecision.
- `POST /projects/{p}/publications` `{proposal_id, revision, bundle_digest, approval_ids, expected_head}` → PublicationRef.
- `GET /projects/{p}/publications/{id}` → exact publication receipt with status, candidate/revision identifiers and approval IDs. A pending receipt is not displayed as a completed publication.
- `GET /projects/{p}/reviews/{id}`, `/validation-runs/{id}`, and `/assessment-runs/{id}` → exact read-only decision or report. Version provenance links these records and distinguishes the inspected historical version from the current approved head.
- `GET /projects/{p}/audit` → audit list: `action, entity, actor, time, event_hash, previous_event_hash, sequence?, detail_digest?`. The UI filters related version/publication/review entities and offers the whole project chain; recorded hashes are not presented as client-verified signatures.
- `GET /projects/{p}/review-sessions?revision_id=…` → current actor's persisted timing events. `POST` to the same collection with `{revision_id, event: "start" | "pause" | "resume" | "end"}` → event with `active_seconds` and `time`. Timing writes require explicit clicks. The running display labels its local live estimate separately from the server-recorded duration; navigation neither starts nor ends a session.
- `POST /projects/{p}/question-jobs` `{question, history?, proposal_id?: string, revision?: number}` → JobRef. Optional proposal targets approved head, or the visibly unapproved demo reference when no approved head exists; chat is read-only. Proposal and revision must be supplied together when selecting a candidate.
- `GET /jobs/{id}` → `{id, status, progress?, stage?, result?, error?}`. `result` is inline for this slice; answer result: `{answer, evidence: Evidence[], triples: Triple[], version_id?, limitations?: string[]}`. Proposal result includes `proposal_id, revision`; validation/assessment result includes report.
- `GET /projects/{p}/experiments` → Experiment list: `id, condition, task_id, replicate, status, created_at, vocabulary_coverage?, vocabulary_utilisation?, strict_fitness?, approximate_fitness?, answer_precision?, answer_recall?, elapsed_seconds?, correction_seconds?, workload_id?, phase?`.
- `POST /projects/{p}/experiment-jobs` `{protocol_id: "demo-v1" | "model-pilot-v1", condition: "A" | "B" | "C" | "D" | "all", task_ids: ["demo-ownership"], replicate_ids: [1]}` → JobRef. The UI explicitly chooses deterministic demonstration versus configured model pilot; both remain synthetic development workloads.
- `POST /projects/{p}/experiments/{run_id}/proposal` without a request body → unapproved Revision for a waiting model D pre-review run. Staging never runs validation, records a decision, or publishes. An explicit subsequent click opens Proposals.
- `GET /projects/{p}/reviews?revision_id=…` → paginated persisted ReviewDecision records, including accept/request_changes/reject. The revision ID is the distinct `revision_id`, not the proposal `id`.
- `POST /projects/{p}/experiments/{run_id}/review-results` `{review_id}` → new immutable post-review Experiment. Only a fetched human decision can be selected; linking requires an explicit authorized-human click. The backend verifies exact candidate ancestry, bundle and reports. The pre-review record remains unchanged. Missing/incomplete review timing remains null; a rejection or request for changes remains right-censored for time to acceptance.
- Experiment responses additionally expose `protocol_id, phase, parent_run_id?, linked_review_id?, candidate_digest?, candidate_ttl?, model?, repair_history?, validation?, assessment?, review_status?, evaluation_status?, limitations?`. The UI keeps protocols separate and suppresses aggregate fitness across mixed phases. Frozen candidate/reports remain read-only.
- `GET /projects/{p}/experiments/export?format=csv|json` → download containing all protocols/phases and failed outcomes.

`JobRef = {job_id, status_url?, correlation_id?}`. Async creates and publications send a fresh `Idempotency-Key`. Browser polls jobs until succeeded/failed/cancelled with bounded polling and errors visible. Writes refresh current project/revision to detect changed heads.

`Triple = {subject, predicate, object, object_type?: "iri" | "literal", datatype?, language?}`.

`Evidence = {id, document_id, title, quote, locator?, chunk_id?, content_hash?, resolved: boolean}`. The UI explicitly labels unresolved evidence and cannot treat a generated quotation as verified evidence.

`Validation = {id, status, profile, engine?, created_at?, cases: {id, name, status, message?, expected?, actual?}[], limitations?: string[]}`. Engine is an object with `name, version?, runner_version?`. Status includes passed/failed/error/timeout/unsupported/not_run. Failed expectations differ from broken engines. Expected and actual values can be booleans, objects, or row arrays.

`Assessment = {id, status, vocabulary_coverage: number | null, vocabulary_utilisation: number | null, strict_fitness: number | null, approximate_fitness: number | null, structural_fitness?: number | null, questions?: {id, question, status?, missing_terms?: string[]}[], mappings?: {source, target, tier, approved}[], limitations?: string[]}`. Successful assessment uses `completed`. Questions without individual result status are labelled as included in the assessment; no individual pass is inferred. Approximate support is labelled a suggestion, never an accepted equivalence.

## Build and verification

Use exact dependency pins and lockfile. `npm --prefix apps/studio-plugin run dev` serves the standalone app and proxies `/api` to configurable local FastAPI. `npm --prefix apps/studio-plugin run build` type-checks and builds standalone plus plugin artifacts. Component tests verify displayed failures/errors, immutable revision requests, stale approval disablement, authorization errors, and escaped source text. A real backend smoke checks the complete safe review loop. The actual pinned TrustGraph host/template smoke is recorded separately in `docs/portal-smoke.md`; shared identity and full native ingestion remain separate gates.
