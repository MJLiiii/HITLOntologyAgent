# Documentation

Start with the [application README](../README.md) for installation and the repository map. Current guides live here; dated reports live in [evidence/](evidence/) and completed plans in [archive/](archive/README.md).

## Using and operating Studio

| Document | Use it for |
| --- | --- |
| [Workflow](workflow.md) | Sources → proposal → checks → human review → publication; experiments and exports |
| [Operations](operations.md) | Local/team identity, independent processes, migrations, backup and recovery |
| [Ubuntu test deployment plan](ubuntu-test-deployment-plan.md) | Proposed four-service setup for the Ryzen / 16 GB test server, Linux confinement work and capacity checks |
| [Two-agent design](two-agent-team-development.md) | Agent boundaries, roles and implementation decisions |
| [Architecture](architecture.md) | Runtime dependencies, HTTP module ownership and workflow boundaries |
| [Model configuration](multi-llm.md) | Server-owned profiles, providers and bounded comparisons |
| [Known limitations](known-limitations.md) | Current capability boundaries and external gates |
| [Contributor guidance](../AGENTS.md) | Code ownership, workflow invariants and verification commands |

## Domain and research

| Document | Use it for |
| --- | --- |
| [Domain scope](domain-scope.md) | Selected DORA preparation and the application's synthetic scope |
| [DORA modelling specification](dora-modelling.md) | Vocabulary, requirement families and competency questions |
| [DORA source packet](../research/corpora/dora-v1/README.md) | Official documents, extracts, provenance and offline integrity check |
| [Synthetic tasks](../research/SYNTHETIC_TASKS.md) | Registered task packets and A–D execution controls |
| [Evaluator](../research/EVALUATOR.md) | Frozen evaluation and study boundaries |
| [Research protocol](../research/protocol.yaml) · [Data dictionary](../research/data-dictionary.md) | Protocol configuration and export definitions |

## Contracts and integrations

| Document | Use it for |
| --- | --- |
| [Frontend contract](frontend-contract.md) · [Generated OpenAPI](openapi.json) | UI/API operations and response contracts |
| [Integration status](integrations.md) · [Initial integration investigation](integration-spike.md) | Engine and upstream compatibility, evidence and remaining limits |
| [PDF ingestion](pdf-ingestion.md) | Bounded document extraction and provenance |
| [Development test generation](synthetic-test-generation.md) | Candidate-derived tests and human oracle review |
| [TrustGraph source contract](trustgraph-source-contract.md) | Source retrieval and upstream completion limits |
| [TrustGraph import contract](trustgraph-import-contract.md) | Durable jobs, verified passage selection and frozen snapshots |
| [TrustGraph model integration](trustgraph-multi-llm.md) | Profile-bound extraction workers |

## Verification and status

Use these records for what was actually tested, including failures and limits. Test counts and live-service observations are dated evidence, not assertions about a new checkout.

- [Two-agent/team verification](evidence/two-agent-team-2026-11-02.md) and [actual team browser workflow](evidence/team-browser-2026-11-02.md): Mac accounts, agents, independent processes and comparison results.
- [Implementation ledger](implementation-ledger.md) and [requirements audit](requirements-audit.md): implementation decisions and coverage.
- [Architecture cleanup verification](evidence/architecture-refactor-2026-11-02.md): route separation, workflow simplification and regression results.
- [OpenAI/Claude cleanup verification](evidence/llm-api-cleanup-2026-11-02.md): current two-provider runtime, cleanup and regression evidence.
- [GUI model selection verification](evidence/gui-model-selection-2026-11-03.md): multiple GPT/Claude choices, controlled compatibility and browser evidence.
- [Multi-LLM verification](multi-llm-verification.md) and [model comparison](model-comparison.md): model-layer checks and bounded live observations.
- [Ubuntu host inspection](evidence/ubuntu-host-inspection-2026-11-03.md): actual server OS/resources, installed runtimes and a limited Bubblewrap capability probe; application deployment remains pending.
- [Release verification](evidence/release-verification.md), [backend review](evidence/backend-review.md) and [bundled resources audit](evidence/bundled-resources-audit.md).
- [Browser acceptance](evidence/browser-acceptance.md) and [local model browser smoke](evidence/browser-smoke.md).
- [Portal smoke](evidence/portal-smoke.md), [TrustGraph pipeline smoke](evidence/trustgraph-pipeline-smoke.md) and [native editor boundary](evidence/native-editor-boundary.md).
- [OntoCheck benchmark compatibility](evidence/ontocheck-benchmark-compatibility.md).
- [DORA source verification](dora-source-verification.json): source-packet preparation checks, separate from ontology validation.

Machine-readable evidence JSON, [screenshots](screenshots/) and the [release manifest](release-manifest.json) retain their existing paths and bytes. Generators and historical hash records refer to those paths. The release manifest describes its original checkout; it is not regenerated to disguise later file moves. Reports formerly at `docs/<name>.md` now live at `docs/evidence/<name>.md`. The [archive index](archive/README.md) records plan relocations.

## Local files

The source tree and local working state serve different purposes:

| Location | Contents and treatment |
| --- | --- |
| `.env`, `.data/`, `infra/portal/runtime/` | Private configuration, application history and integration state; preserve |
| `.runtime/`, `research/results/` | Models, budgets, logs and retained experiment evidence; preserve |
| `backups/`, `output/` | Original user documents and historical outputs; preserve |
| `.venv*`, `node_modules/`, `infra/portal/upstream/` | Installed environments, dependencies and pinned upstream builds |
| UI `dist/`, `dist-plugin/`, Jena `target/` | Build products used to run Studio; rebuild before use if removed |
| Source `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.DS_Store` | Disposable caches and Finder metadata; already ignored by Git |

Keep new feature plans in `docs/` while active, move completed plans to `archive/`, and put dated verification reports in `evidence/`. Append progress to the existing ledgers. Avoid blanket deletion of ignored files: ignored state includes credentials, approved ontology history and sealed research records.
