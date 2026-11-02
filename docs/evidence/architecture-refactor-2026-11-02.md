# Architecture cleanup verification — 2 November 2026

This report covers the behavior-preserving refactor against source baseline
`b1ec850`. Changes were made in the existing checkout with an initially clean
working tree. No schema migration, dependency update, new feature or generated
API contract change was required.

## Changes verified

- Separated HTTP routes into seven responsibility-based routers with shared
  request models, pagination and request-scoped authorization dependencies.
  `main.py` now contains application setup/lifecycle in 77 lines, down from 582.
- Separated job dispatch from lease/completion/failure handling and consolidated
  the frozen-profile authorization check used at dispatch and completion.
- Removed the unused `binding_from_environment` function and its two unused
  imports. Reference searches across source, scripts, tests and documentation
  found no callers; the sole documentation mention was corrected to describe the
  existing configuration-file path. Actual TrustGraph binding validation remains
  in `trustgraph_workflow.py`.
- Added an application-isolation characterization test before moving routes. It
  checks independent sessions, cross-store project reads and isolated writes.
- Updated the job metadata contract test to inspect registered route handlers
  instead of assuming every handler is defined in `main.py`.

## Results

All backend runs used disposable synthetic data directories and disabled default
model configuration. The full run used the pinned Python 3.12 environment and
Java 21 executable from the Makefile. No paid model calls, live provider probes,
working-ontology publication or real study activity were performed.

| Check | Result |
| --- | --- |
| Initial confined unit/integration baseline | 429 passed, 7 skipped, 13 engine-related failures |
| Unit/integration baseline with engine-launch permission, including the new characterization test | 443 passed, 7 skipped |
| HTTP/workflow/team/pagination/contract/export subset after extraction | 80 passed |
| Job recovery/profile/worker/team/test-generation/gateway subset after simplification | 53 passed, 1 skipped |
| Full backend: `.venv/bin/python -m pytest -q` | **609 passed, 8 skipped**, 96.26 seconds |
| Frontend: `npm --prefix apps/studio-plugin test` | **64 passed**, 14 files |
| Frontend: `npm --prefix apps/studio-plugin run build` | TypeScript and both standalone/plugin builds passed |
| `make lint` | Ruff and TypeScript passed |
| `make check-api-contracts` | OpenAPI, operation map and aliases unchanged |
| Local documentation links and `git diff --check` | Passed |

The initial engine failures were environmental: even a minimal `sandbox-exec`
invocation returned `sandbox_apply: Operation not permitted` inside the outer
execution sandbox. Rerunning with the required permission allowed the existing
confined Jena/OntoCheck execution paths to run. No isolation code was weakened.

The final eight skips are seven separately configured PostgreSQL cases and one
opt-in TrustGraph live read probe. The backend emitted 3,416 dependency warnings,
including existing RDFLib/pyparsing and Pydantic warnings; they were not suppressed.
These results do not establish new live-provider, PostgreSQL or browser-host
compatibility evidence. Historical verification and release hashes remain intact.

## Independent review

A read-only reviewer found no actionable issues. It compared all 76 moved
definitions and 68 route signatures against the baseline, checked route ordering,
authorization, chunk provenance, sealed exports, and the unchanged ingestion
transaction and job-lease ordering. The reviewer did not duplicate the suite or
perform live provider calls; the completed checks above supply local execution
evidence, while live integration limits remain as documented.

See the [architecture guide](../architecture.md) and
[completed plan](../archive/2026-11-02-architecture-refactor.md).
