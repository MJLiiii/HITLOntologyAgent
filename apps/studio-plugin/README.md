# Ontology Studio frontend

React and TypeScript workspace with six views: Chat, Ontology, Sources, Proposals, Validation, and Experiments. The same components build as a standalone application and a TrustGraph remote plugin.

```sh
npm ci --prefix apps/studio-plugin
npm --prefix apps/studio-plugin run dev
npm --prefix apps/studio-plugin test
npm --prefix apps/studio-plugin run build
```

The development server listens on `127.0.0.1:5173` and proxies `/api` to `http://127.0.0.1:8000`. Set `STUDIO_API_URL` to change the proxy target. Production output is `dist/`; the FastAPI application can serve it directly.

Use the session link or local token printed by the backend launcher. A `#session=…` fragment is passed once in the `X-OE-Session-Token` header and removed after successful session establishment. The frontend does not store this token in local storage. API calls use same-origin cookies; service secrets and automatic approvals are never bundled.

The initial synthetic reference is visibly **not approved**. Source scope acceptance, test-oracle acceptance, review submission, ontology acceptance, and publication each require their own human action. Reports, approvals, evidence, and expected heads remain bound to exact revisions. Editing the displayed cumulative proposal diff produces incremental changes against the previous candidate.

Sources includes a versioned scope editor for the synthetic scope label/purpose, required boolean ASK questions, SHACL shapes, and fixtures. A saved scope version awaits a separate written human decision; historic versions remain inspectable. The fixed namespace and demonstration classification remain explicit. Turtle seed import stages pasted or uploaded ontology text against the inspected frozen corpus as a proposal, available before the first approved release. Importing never approves the seed.

Validation includes proposed development tests, explicit expected results, and a human test-oracle decision. Accepting expectations creates an unvalidated successor revision; required checks remain intact. A negative ASK result is described as non-entailment in the test graph, not logical negation.

Validation also provides full-IRI assessment mapping proposals, resolved corpus evidence selection, and a separate human accept/reject decision. Mapping sets replace the complete active configuration; an accepted empty set clears it. Reviewed correspondences are tool configuration, never asserted OWL equivalence axioms. Configuration changes require a successor candidate and fresh checks, assessment, and review. Assessment reports show their frozen mapping digest, reviewer, decision, evidence, and diagnostics rather than substituting current settings.

The proposal review timer starts, pauses, resumes, and ends only through explicit clicks. It restores the current human's persisted timing events for the exact revision, excludes paused intervals, and distinguishes the live elapsed estimate from the last server-recorded active duration. Navigation does not implicitly stop or start timing.

After failed validation, Request repair sends only the exact bundle to the bounded repair endpoint. The backend admits failed competency-question diagnostics, limits proposals to two attempts, and returns an unvalidated successor. Engine errors do not enable automatic repair; pending publication and stale revisions block it. Required checks and human acceptance must happen again.

Ontology version provenance shows the approved head separately from the inspected historical version and pending publications. Exact read-only links connect the publication receipt, candidate revision, human decisions, validation, and assessment reports. The audit panel shows related entity events with their recorded chain hashes and offers the full project history.

## TrustGraph artifact

The build emits `dist-plugin/ontology-studio.iife.js` and `dist-plugin/ontology-studio.css`. The `OntologyStudioPlugin` global is the default React component expected by the inspected TrustGraph loader. React and its JSX runtime resolve through `TrustKitShared`; the host must explicitly load the stylesheet and provide a same-origin `/api/v1` route with the required session.

The plugin export is checked against pinned upstream loader source in the repository's integration fixtures. An actual TrustGraph host deployment and browser smoke remain a separate integration gate; the standalone harness does not prove that deployment.

## Verification

Component and API-client tests cover authorization failures, pagination, failed jobs, escaped source text, source processing state, stale acceptance, immutable revision deltas, separate review/publication clicks, engine-error reporting, approximate mapping labels, session bootstrap, grounded chat, and human test-oracle decisions. `npm run build` type-checks both application and test code, then builds both deliverables.
