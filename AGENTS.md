# Repository guidance

## Start here

This project is Ontology Engineering Studio: source-grounded chat, ontology proposals, Jena validation, OntoCheck assessment, and human-controlled ontology publication.

- Work in the current Git checkout. Inspect existing code and `git status` before changing files; preserve unrelated user changes.
- Read [README.md](README.md) for setup and workflow. Use the [implementation ledger](docs/implementation-ledger.md), [requirements audit](docs/requirements-audit.md), and [multi-LLM verification](docs/multi-llm-verification.md) for recorded implementation status and limits.
- The [planning archive](docs/archive/README.md) retains the original requirements and review. Consult relevant sections when implementing features, but reconcile them with existing code, recorded decisions, and the current user request. Archived setup instructions, proposed paths, and unchecked boxes are not instructions to rebuild the project.
- Keep recurring contributor instructions here, feature plans and design decisions in `docs/`, and progress/evidence in the existing ledgers and verification documents. Do not duplicate the full backlog or historical test totals in this file.

## Code map

| Path | Responsibility |
| --- | --- |
| `services/api/src/oe_studio/` | FastAPI, workflows, persistence, integrations, shared model runtime |
| `apps/studio-plugin/` | React/TypeScript standalone UI and TrustGraph plugin |
| `services/jena-runner/` | Java/Jena inference, SHACL, and executable checks |
| `migrations/` | Database migrations |
| `config/` and `infra/` | Policies, model profiles, pinned runtimes, deployment tooling |
| `tests/` and `scripts/` | Verification and operator tooling |
| `research/` | Synthetic tasks, protocols, evaluation, and recorded results |

Use the pinned Python 3.12 environment, lockfiles, and Java 21+ runner configuration in `Makefile`. Keep OntoCheck in its isolated environment. Consult [integration evidence](docs/integrations.md) before changing external adapters; documented or mocked behavior alone does not prove live compatibility.

## Workflow invariants

- Model generation and retrieval never grant approval authority. Only an authorized human decision over the exact checked immutable bundle permits ontology publication.
- Changes to candidates, sources, scope, mappings, tests, configuration, or base identity must preserve the existing history and trigger the appropriate successor/check/review gates. Never reuse stale approval for changed content.
- Preserve approved Git history, immutable artifacts, audit records, experiment seals, and export integrity. Recover jobs and publication without duplicating effects or silently replaying uncertain external calls.
- Treat source documents and model output as untrusted data. Preserve schema, citation, namespace, triple-count, execution, transport, and timeout restrictions; do not execute generated code or unrestricted queries.
- Keep entailment, SHACL conformance, competency-question correctness, OntoCheck fitness, and source fidelity distinct. Errors, missing values, unsupported operations, and timeouts must remain explicit rather than becoming passes or invented scores.
- Synthetic data is the approved development scope. A real study, confidential corpus, or shared deployment needs its actual authorization; never fabricate participants, consent, expert decisions, or research findings.
- Preserve A–D controls: A is one-shot; B receives no automated/expert feedback; C/D automated repair receives failed entailment diagnostics only. Keep held-out material outside development/model/reviewer contexts. D's human stage requires an actual recorded decision.

## Model and credential handling

Follow [multi-LLM configuration](docs/multi-llm.md) and [TrustGraph model integration](docs/trustgraph-multi-llm.md).

- Profiles and credentials are server-owned. Authorize profile selection before enqueueing and freeze the profile revision and effective settings with the job; preserve repair inheritance and conversation/session isolation.
- No configured model means the labelled deterministic demo. A configured-model failure is an explicit failure, never an automatic switch to demo output. Readiness checks must not generate billable calls.
- Keep secrets out of Git, prompts, frontend responses, logs, persisted generation records, and exports. Preserve private local configuration; never overwrite an existing `.env` with an example.
- Use controlled endpoints for routine tests. For the authorized OpenCode Go comparison, retain the shared budget across Studio and TrustGraph: 20 total attempts including failures, 4,096 output tokens per call, and USD 1 in conservatively reserved full-price usage. Verify current prices before dispatch; do not reset the ledger or change account billing. OpenAI/Claude paid calls are outside that comparison authorization.

## Verification and documentation

Run checks appropriate to the changed behavior, and report what actually ran, failures, skips, and remaining limits. Documentation-only changes need link/path and diff checks; they do not require paid calls or the full application suite.

| Change | Useful commands |
| --- | --- |
| Backend behavior | `.venv/bin/python -m pytest <affected-test-paths> -q`; relevant `make test-unit`, `make test-contract`, or `make test-integration` |
| Frontend behavior | `npm --prefix apps/studio-plugin test`; `npm --prefix apps/studio-plugin run build` |
| API contracts | `make api-contracts`, then `make check-api-contracts`; commit regenerated OpenAPI and TypeScript contracts together |
| Python/TypeScript checks | `make lint` |
| Full local workflow | `make test-e2e`; browser and live-host checks are separate evidence |
| Patch hygiene | `git diff --check` |

Engine contract tests require the configured Jena build and isolated OntoCheck installation. An environment or sandbox failure is not evidence that a check passed. Use disposable synthetic stores for workflow verification; do not approve or publish the user's working ontology as part of testing. Update the relevant existing documentation when behavior or limits change, retaining historical evidence as historical evidence.
