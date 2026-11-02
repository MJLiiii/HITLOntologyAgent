# Architecture cleanup implementation plan

> Execution: Superpowers writing-plans and executing-plans, incrementally in the current checkout as requested. Existing behavior is the specification; no new feature, API, schema, dependency or data migration is intended.

## Design and constraints

The HTTP application currently combines startup, authentication dependencies,
request models, pagination and every endpoint in one closure. Separate these
responsibilities into ordinary modules and FastAPI routers. Keep `main.create_app`
and `main.app` as the entry points. Route names, paths, operation IDs, response
models and authorization decisions must remain identical.

The workflow remains the transaction coordinator. Extract job dispatch into a
focused method and centralize the repeated frozen-profile authorization check.
Keep lease checks, atomic effects/results, recovery and publication transactions
where they are. Avoid mixins, registries, generic repositories or new frameworks.

A whole workflow rewrite would enlarge the risk to immutable history and job
recovery. A cosmetic file cleanup would leave the HTTP coupling intact. This
bounded separation is the implementation choice for the user's requested
behavior-preserving refactor. Preserve all local state and historical evidence.

## Tasks

- [x] Establish baseline unit/integration results and add application-isolation
  coverage: independently configured apps must keep their routes, sessions and
  writes bound to their own Studio instance.
- [x] Move request-only models into `api/requests.py`; move shared pagination and
  authorization dependencies into `api/`; register cohesive routers for sessions,
  health, projects, sources, proposals/review, experiments and jobs. Keep error
  handlers and application lifecycle in `main.py`. Update the route metadata test
  to inspect registered endpoints rather than assuming a single source file.
  Verify workflow, team access, pagination, response contracts and OpenAPI parity.
- [x] Simplify job execution by extracting `_dispatch_job` and
  `_authorize_job_profile`, preserving the order of checks and effect commits.
  Verify recovery, profiles, worker processes and agent workflows.
- [x] Remove only the unused `binding_from_environment` helper after checking
  source, tests, scripts, docs and runtime configuration references; retain the
  actual server-owned binding path in `trustgraph_workflow.py`. Correct the stale
  integration documentation and run gateway contract tests.
- [x] Run backend and frontend checks, build, lint and generated-contract drift
  check. Review the diff independently, document architecture and actual evidence,
  append the implementation ledger, and archive this plan.

## Review focus

- Local and team session authorization must preserve per-route roles.
- Shared routers must never retain a Studio instance from a different app.
- Chunk pagination must reject malformed cursors and changed provenance.
- A failed or expired job must never replay an uncertain call or commit late effects.
- Experiment exports must preserve sealed values and missing measurements.

## Verification policy

Use existing tests as characterization coverage before moving code, then rerun
the relevant subset after each step. New tests cover meaningful behavior gaps,
not private file layout. This is the refactor phase of the test cycle: do not
manufacture behavior changes or failing assertions to justify code movement.
All application fixtures use disposable synthetic stores and controlled model
endpoints. No paid calls or mutation of the user's working ontology is part of
verification. Final review covers the working diff; changes remain uncommitted
for user review.

## Execution notes

- Keep HTTP request envelopes in `api/requests.py`: putting `MappingSetRequest`
  in the core `schemas.py` would introduce a cycle through
  `assessment_contracts.py`. Their existing schema names remain unchanged.
- Initial confined unit/integration baseline: 429 passed, 7 skipped, 13 failures
  caused by the outer sandbox blocking the required Seatbelt launcher. With
  execution permission and the pinned Java runtime, the same suites plus the
  new app-isolation characterization test passed: 443 passed, 7 skipped.
- Route extraction is mechanical, using Python AST source spans; generated
  OpenAPI and TypeScript contracts remain byte-for-byte unchanged.
- HTTP-focused verification passed 80 cases; job/gateway-focused verification
  passed 53 with one optional live skip. Final backend verification passed 609
  with 8 optional skips; frontend passed 64. Both builds, lint and API-contract
  checks passed. Independent review found no actionable issues. See the
  [verification report](../evidence/architecture-refactor-2026-11-02.md) for limits.
