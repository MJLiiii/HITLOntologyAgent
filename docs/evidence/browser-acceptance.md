# Browser acceptance — simulated engineering test

Executed 1 November 2026 in Chrome against an isolated Studio at `http://localhost:5173`, with a fresh temporary `OE_DATA_DIR`, SQLite, eager jobs, and no configured language model. These are simulated engineering records, not expert-study observations or approvals of a real ontology. The main workspace’s `.data` was not used for these writes.

All workflow mutations below were performed through the actual built web interface. A read-only SQLite export corroborates the resulting identities and statuses in [browser-acceptance-evidence.json](../browser-acceptance-evidence.json). This evidence omits session keys, cookies, bootstrap tokens, and raw request headers.

## Executed workflow

1. Opened the isolated workspace using its operator session link. The fragment was cleared and reload preserved the cookie session. Initial state correctly showed no approved version and an unaccepted synthetic scope.
2. Uploaded a 267-byte UTF-8 synthetic source, labeled `SIMULATED ENGINEERING TEST — ownership input`, using Chrome’s native file picker. The extension file-chooser helper was unavailable because file URL access was disabled; no extension permissions were changed. Explicit **Process source** completed, and **Freeze corpus snapshot** included this source and all three original synthetic sources.
3. Inspected the two required ASK questions, then explicitly accepted the synthetic scope with a rationale beginning `SIMULATED ENGINEERING TEST`. This decision occurred only in the disposable workspace.
4. Generated the first unapproved candidate. Created revision 2 by removing both `CriticalService rdfs:subClassOf Service` and `hasOwner rdfs:domain Service`. The revision rationale explicitly described this deliberate engineering failure.
5. Ran real Apache Jena 6.2.0 validation. `CQ-01` returned `false` against expected `true`; `CQ-02` passed. The interface displayed **Candidate needs correction**, the exact oracle, reasoning limitations, and disabled submission/acceptance/publication. The failed bundle remains preserved.
6. Explicitly clicked **Request repair**. Attempt 1 produced revision 3 as an unvalidated draft, restored the source-supported hierarchy, and did not approve or publish it. Separate **Run validation** and **Run assessment** actions then passed/completed for that exact bundle.
7. Inspected both reports, explicitly submitted revision 3, entered an expressly simulated acceptance rationale, accepted the exact bundle, and separately clicked **Publish version**. Release 1 became the approved head with 20 asserted triples. Its provenance displayed the exact revision, bundle, review, validation, assessment, publication receipt, Git commit, and audit events.
8. Generated a second synthetic proposal. The deterministic fixture added one `Service rdfs:comment` statement. Separately validated, assessed, submitted, accepted with another `SIMULATED ENGINEERING TEST` rationale, and published it as release 2 with 21 triples.
9. Selected **Approved release 1** in the ontology version selector. The interface showed **Historical approved version**, 20 triples, and release 1’s exact provenance, while the approved head remained release 2. The final database confirms head `7b57d01b-8c06-492b-a641-d105c9959486` and no pending publication.

No review timer was started; no correction time was invented. No experiment observations or human-study records were generated.

## Keyboard, responsive, and error checks

- Keyboard activation through Enter operated navigation, revision tabs, validation, assessment, submission, acceptance, and publication. The focused control is visibly outlined.
- At a 390 × 844 viewport, ontology history and the model experiment selector fit without horizontal page overflow: `clientWidth = scrollWidth = 390`. The navigation opened and closed, and selecting a destination closed it. The temporary viewport override was reset afterwards.
- The closed mobile navigation initially remained keyboard-focusable while translated off screen. It now uses `visibility: hidden` until opened. After rebuilding, Tab from the skip link reached the visible **Open navigation** control; Enter opened the menu. `aria-expanded` and `aria-controls` expose the toggle state and target.
- The model experiment selector displayed **Configured model pilot**, its actual-model-call explanation, and the explicit synthetic engineering-pilot/no-completed-expert-evaluation limitation. No model run was started during this acceptance test.
- The uploaded `<script>alert("untrusted evidence")</script>` text appeared literally in the evidence citation, with its source hash and character span. DOM inspection found zero injected fixture script nodes, and no JavaScript alert was open.
- A separate unauthenticated origin at `127.0.0.1:5173` rejected an intentionally invalid token and returned the actionable local-session recovery message. No security setting was altered.
- Uploading, processing, freezing, validation, assessment, publication, initial loading, and provenance loading showed visible pending states. Controls were disabled during dependent mutations. The final browser console had no warnings or errors.

This is a focused keyboard and responsive smoke test, not a complete WCAG audit. Browser control intermittently timed out before or after dispatch; visible state was inspected before retrying, and the retained records contain exactly two reviews and two publications.

## Fixes and verification

The real Jena response omits optional case display names. The report now falls back to the stable case ID, so `CQ-01` and `CQ-02` remain identifiable. A response-shaped component regression test failed before this fix and passed afterwards; the existing four validation/assessment tests were preserved.

Final frontend verification: **36 tests passed across 12 files**, TypeScript passed, and both standalone and plugin Vite production builds passed. Existing third-party notices are included in the static build.

## Retained browser evidence

- [Failed CQ with explicit expected/actual result](../screenshots/acceptance-failed-cq.jpg)
- [Published release and provenance](../screenshots/acceptance-published-version.jpg)
- [Historical approved version with unchanged current head](../screenshots/acceptance-previous-approved-version.jpg)
- [Literal untrusted source text](../screenshots/acceptance-malicious-source-escaped.jpg)
- [Model experiment selector](../screenshots/acceptance-experiment-selector.jpg)
- [Mobile ontology history](../screenshots/acceptance-mobile-history.jpg)
- [Mobile model experiment selector](../screenshots/acceptance-mobile-experiments.jpg)
- [Rejected session recovery](../screenshots/acceptance-session-error.jpg)

The disposable server and its temporary data are removed after exporting this sanitized evidence. See [portal-smoke.md](portal-smoke.md) for the separate real TrustGraph host checks and their precise scope.

After cleanup, a final read-only check reloaded the latest Studio plugin inside the real TrustGraph host at `127.0.0.1:5183/ontology-studio`. Both sessions survived, the native footer showed **Authenticated**, and the main Studio still showed **No approved version** and **Scope awaiting human acceptance**. The model pilot selector and its limitations rendered correctly; no experiment, review, or publication action was taken in the main workspace. [Final host screenshot](../screenshots/trustgraph-studio-experiments-final.jpg).
