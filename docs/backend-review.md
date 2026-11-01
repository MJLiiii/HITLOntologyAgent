# Independent backend review — 1 November 2026

Scope: implemented workflow, publication/recovery, evidence and report integrity, local authentication, durable jobs, model boundary and grounded chat. Reviewed `workflow.py`, `main.py`, `auth.py`, `db.py`, `rdf.py`, `model.py`, `git_store.py`, `chat.py`, API tests, and the development plan's global invariants and sections 5–8/10. The synthetic-test/repair endpoints being implemented concurrently were excluded as missing-feature findings.

Evidence: focused probes used temporary databases/artifact stores/Git repositories and the existing integration-test fixture. Engine doubles supplied controlled report outcomes; publication, authentication, integrity checks, recovery, jobs and chat code were real. No root implementation files were edited by the reviewer. No broad test suite was rerun for this review. Root fixes arriving during review are identified separately below.

## Open findings at review handoff

### R1 — P1: A service client can obtain approver identity by omitting its token

Location: `main.py:create_app.session`, `auth.py:require_actor`.

`GET /api/v1/session` issues the human cookie to any loopback HTTP client without an Authorization header. A client holding only the service credential can omit that header, obtain the cookie, and use human-only endpoints. The initial probe supplied the service token to `/session`, received a human actor/cookie, and successfully accepted scope (HTTP 201). Root changed the token-present path to return service identity without a cookie, but the token-omission path remains equivalent: the endpoint has no operator-only bootstrap proof.

Reproduction after the header-path fix: start a fresh HTTP client; call `/api/v1/session` without Authorization; use the returned cookie on `/scope-decisions`, `/reviews` and `/publications`. The cookie resolves to `local-human` with `approver` role. A localhost service client has every input needed to do this. `test_service_session_does_not_issue_human_cookie` only checks the header-present case.

Impact: this is not a remote-network bypass, and the documentation explicitly assumes a trusted local machine. However, the claimed service-versus-human credential boundary is not enforced against other loopback clients. The model itself has no tool/network interface, which is a separate, intact boundary. To enforce the stated credential separation, require a researcher-controlled bootstrap capability unavailable to service clients; rejecting Authorization on the bootstrap endpoint alone is insufficient. Otherwise document that all loopback callers are trusted to impersonate the single operator and do not claim service credential isolation as a security property.

### R2 — P1: Publication accepts reports that the read endpoint rejects as corrupted

Location: `workflow.py:eligibility`, `reports`, `publish` and `reconcile_publication`.

The eligibility gate reads validation/assessment `Item.data` fields directly without checking them against their immutable `_payload` artifacts. The normal report GET path calls `body()` and detects the same corruption. Approval and publication therefore have a weaker integrity boundary than inspection.

Executed reproduction: complete checks and human approval; change only the selected assessment's `data.strict_fitness` to `0.123` and its limitations, leaving `_payload` unchanged; GET that assessment; publish the already approved bundle. Observed GET **409**, publication **202 / completed**, and a non-null approved head. The simulated database corruption was confined to the temporary test database. This does not require constructing another valid artifact or changing the review.

Fix direction: verify the selected reports with `body()`/`get_verified()` before trusting their status or bundle binding, both during approval and before publication CAS. Preserve the exact immutable report references in the approval/release evidence. Root added `test_tampered_assessment_report_blocks_publication`; the independent narrow run observed its intended red result, **202 instead of 409**. Implementation was still in progress at that check.

### R3 — P1: Bundle engine identity omits the executable that actually runs

Location: `workflow.py:engine_configuration` and `eligibility`.

The captured configuration hashes Python adapters, the profile JSON and Maven POM. It does not hash the selected Jena JAR, Java source files, OntoCheck dependency lock or actual selected isolated runtime. Replacing/rebuilding the JAR under the same runner/Jena version therefore leaves existing approval eligibility unchanged. A validation report records its JAR SHA, but the bundle/gate does not bind that SHA.

Concrete regression: point `validation.RUNNER_JAR` at a temporary file with bytes `runner-v1`; create/check/approve a bundle with controlled engine fixtures; overwrite that same file with `runner-v2`; publish. Root's new `test_changed_runner_invalidates_bundle` returned **202 instead of 409** in the independent run. This tests the publication identity gate and does not attempt to execute the fake JAR.

Fix direction: include the actual selected executable artifact and complete frozen dependency/configuration identities. A source version string is insufficient to distinguish different builds with the same metadata. Validate the same identity again immediately before approval/publication. Root implementation was in progress at handoff.

### R4 — P2: One unrecoverable publication prevents every queued job from running

Location: `main.py:create_app.worker`, `workflow.py:reconcile_pending`.

The worker calls `reconcile_pending()` before `work_once()` inside one try block. A single pending publication with an unexpected Git head raises on every iteration, so `work_once()` is never reached, including for other projects. The intended operator-reconciliation gate for one project becomes a global job outage.

Executed reproduction: reserve a publication and stop before CAS; install an unrelated valid commit as that project's approved Git ref; restart with the normal background worker; create a second project; enqueue a question there. The question POST returned **202**, two recovery attempts logged `git_head_mismatch`, and the unrelated job stayed **queued**. The same control flow repeats indefinitely until the first project's conflict is repaired.

Fix direction: isolate recovery failures per publication/project, retain an actionable blocked/error state, and continue servicing unrelated jobs. A failed recovery must not silently advance the bad ref, but it must not monopolize the worker.

### R5 — P2: An unknown named entity silently widens the chat answer to all owners

Location: `chat.py:answer_question`, owner branch (`known` filtering).

The code filters owner triples only when it finds a known label. If a question names an absent entity, `known` is empty and the response lists every ownership relation as though the requested lookup succeeded.

Executed example: **“Who owns Lunar Service?”** against the demo. The response was “Analytics Service is owned by Data Team. Payroll Service is owned by Operations Team.” with both triples, supporting-source labels, and **`unresolved_points: []`**. Lunar Service exists in neither selected graph nor sources. The existing unknown-question test asks about the moon's market price, which avoids this branch and therefore misses the defect.

Fix direction: distinguish an explicitly named but unresolved target from an unrestricted request such as “List service owners.” Return a missing-target reason and no target-specific claim when resolution fails. The same distinction should be checked in the classification/general-description branches.

## Findings repaired during this review

### R6 — P1: A reserved publication could publish an already superseded revision

Original location: `workflow.py:revise` and `reconcile_publication`.

Executed original reproduction: approve revision 1; stop publication at the `reserved` checkpoint; POST an ordinary revision 2 correction (HTTP **201**); resume `reconcile_pending()`. The approved head used revision 1's bundle while revision 2 already existed with a different bundle. No report or artifact was tampered with. Recovery did not re-run eligibility before CAS. Scope rejection/source invalidation during that interval had the same missing recheck.

Root added a pending-publication guard to revision creation and an eligibility check immediately before CAS when the ref has not already advanced. Independent focused execution of `test_changed_scope_blocks_recovery_before_ref_advance` passed. An already advanced ref remains a receipt-reconciliation case, rather than an invitation to rewrite history. The original exact superseding-revision probe should be retained as a regression in addition to the scope case.

### R7 — P2: Follow-up answers with different histories had identical context digests

Original location: `workflow.py:question`.

Executed original reproduction: ask “Who owns it?” with prior user history “Tell me about Payroll Service”, then with “Tell me about Analytics Service.” The answers correctly differed (Operations Team versus Data Team) but had the same `context_digest`, because history was omitted from its input. This prevented that digest from identifying the actual retrieval/answer context.

Root added history to the digest input. Independent focused execution of `test_followup_context_digest_includes_history` passed.

## Focused verification record

The temporary probes were `/private/tmp/oe-backend-review-probes.py`, `/private/tmp/oe-backend-integrity-probe.py`, and `/private/tmp/oe-backend-worker-probe.py`. Their observations are recorded above so this report does not depend on retaining temporary files.

The narrow command was:

```sh
.venv/bin/python -m pytest tests/integration/test_workflow.py -q \
  -k 'changed_scope_blocks_recovery or followup_context_digest or tampered_assessment_report or changed_runner or service_session'
```

At the review snapshot it produced **3 passed, 2 failed**: the two failures were R2 and R3, whose fixes were being implemented concurrently. It also emitted the existing upstream Starlette/AnyIO deprecation warning. Passing the service-header test does not resolve R1's omitted-header counterexample.

The review did not find an arbitrary tool/publication capability in model output: strict schemas exclude it and `ModelClient` only calls the configured model endpoint. Reference-ID checking establishes that references exist, not that generated prose logically follows from them; the code already states that limitation. No complete OWL consistency, live TrustGraph authorization or real-study result is inferred from these backend checks.

## Final release-review addendum — 1 November 2026

The earlier sections retain the observations at their original handoff. They are historical review snapshots, not a current unresolved-defect list. The later review inspected the current local workflow, authorization, publication recovery, evidence retrieval, model constraints, experiment records, evaluator boundaries, timing/allocation and task-level analysis. It did not repeat every original probe or claim a fresh independent full-suite run.

Three additional findings were corrected by root:

- **P1 — withdrawn-source reactivation:** `_ingest` could process a source withdrawn before its first ingestion, set its status to `complete`, and resolve the resulting evidence. A temporary-store probe reproduced this. The new guard rejects withdrawn sources before both the prior-ingestion lookup and any processing.
- **P2 — RDF literal whitespace loss:** inherited string stripping changed literal lexical values and made deletion of an exact imported literal fail. A temporary probe reproduced both the changed value and missing-triple error. `Triple` now preserves whitespace, with an add/delete round-trip regression.
- **P2 — question-name-dependent repair:** repair admitted failed diagnostics by the `CQ-` prefix although scope questions permit other identifiers. It now reads IDs from the verified immutable question artifact and excludes unrelated prefixed diagnostics. Root observed the regression red before its fix.

Independent final focused execution passed **five cases in 1.88 seconds**: withdrawal before/after ingestion, literal whitespace round-trip, arbitrary frozen question IDs, and the two-attempt repair budget. The reviewer used temporary stores, disabled bytecode/pytest-cache writes and created no approvals. Upstream deprecation warnings remained. No additional demonstrated blocker was found in the reviewed trusted-loopback synthetic workflow.

The independent staged-source audit subsequently inspected **197 staged files**, compared **12 known local secret forms** with zero matches, and checked all seven then-staged screenshots against their exact staged bytes. No runtime/private credentials, real reviewer data, downloaded dependency trees or unintended private source files were found. The sole token-pattern match was a descriptive frontend test fixture. The screenshots displayed synthetic UI without visible credentials and had no EXIF/XMP markers. This audit covered that index snapshot; later additions still need the final source scan. No files or index entries were changed during the review or scan; this addendum and the requirements-audit update were separately authorized documentation edits.

Root separately executed the clean application suite (**278 passed, 9 skipped**), frontend checks (**36 passed**), locked cached reproduction/startup, lint/API drift checks, main-store backup/restore and three identical final JAR builds. Actual-browser acceptance created two expressly simulated releases only in disposable data; the persistent main store retained zero approved refs. See `release-verification.md`, `browser-acceptance.md` and `requirements-audit.md` for evidence and scope. These root/frontend executions are not attributed to this reviewer.

The review does not certify shared identity, a deployed publisher/evaluator OS boundary, generic live TrustGraph terminal processing or automatic corpus activation, model semantic accuracy, a complete accessibility audit, broad OWL benchmark equivalence, or real-study readiness. The user explicitly confirmed that no real study is approved. The local synthetic engineering result remains distinct from completion of the full development plan; the first consolidated source commit and final source freeze are pending at this addendum.
