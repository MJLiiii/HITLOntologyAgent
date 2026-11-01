# Ontology Engineering Studio

A local web application for source-grounded ontology chat, proposals, Jena validation, OntoCheck assessment and human review before Git publication. Its six views are Chat, Ontology, Sources, Proposals, Validation and Experiments.

The running application uses synthetic service-ownership data. The next selected domain is **financial regulatory compliance / DORA contractual obligations**: the [domain specification](docs/domain-scope.md) and [public source packet](research/corpora/dora-v1/README.md) are prepared, but DORA is not yet an application domain or registered experiment. Real studies, confidential ingestion and shared deployment remain outside the approved scope.

## Start

Prerequisites: Python 3.12, `uv`, Node.js/npm, Maven, Java 21+ and Git. Use the repository's pinned versions and lockfiles. Initial setup downloads dependencies.

```sh
# Preserve an existing local configuration.
[ -f .env ] || cp .env.example .env
make setup
# On other machines: export JAVA_HOME=/absolute/path/to/jdk-21
make demo
```

Open the private local session URL printed by `make demo`. The command builds the Java runner and both frontend bundles, migrates the database, and starts the UI and API at [127.0.0.1:8000](http://127.0.0.1:8000). API documentation is at `/docs`. Keep the session URL private and serve this local identity mode only on loopback.

Application data, immutable artifacts and ontology Git history live in `.data/`. For development, run `make dev-api` and `make dev-ui` in separate terminals. The deterministic demo needs no model key; see [model configuration](docs/multi-llm.md) and [local model setup](docs/workflow.md#models-and-development-servers) for optional generation.

## Workflow

1. Select sources and scope; freeze the evidence snapshot.
2. Ask source-grounded questions and create an ontology proposal.
3. Inspect its changes, citations and immutable revision.
4. Run Jena validation and OntoCheck assessment; correct failures in a successor revision.
5. Record an authorized human decision over the exact checked bundle.
6. Publish that approved revision to ontology Git history.

Changes to sources, scope, tests or mappings require fresh checks and review. Model output never grants publication authority. Experiments retain separate A–D controls and do not fabricate human decisions or study findings.

See the [detailed workflow](docs/workflow.md) for source imports, test generation, experiments, recovery and exports.

## Repository map

| Location | Purpose |
| --- | --- |
| [apps/studio-plugin/](apps/studio-plugin/) | React UI and TrustGraph plugin |
| [services/](services/) | Python API/workflows and Java/Jena runner |
| [tests/](tests/) | Backend unit, contract and integration checks; UI tests live with components |
| [scripts/](scripts/) | Setup, migration, export and operator commands |
| [config/](config/) · [infra/](infra/) | Policies, model profiles, runtime pins and optional services |
| [migrations/](migrations/) | Database schema history |
| [prompts/](prompts/) · [resources/](resources/) | Generation guidance and bundled engine resources |
| [research/](research/) | Protocols, evaluation tools, fixtures and source corpora |
| [docs/](docs/README.md) | Current guides, status, verification reports and archived plans |

Local state, environments and downloaded runtimes are ignored by Git. They are separate from source code; see [storage and cleanup guidance](docs/README.md#local-files).

## Verify

```sh
make test-unit
make test-contract       # requires the built Jena runner and isolated OntoCheck
make test-integration
make test-e2e            # HTTP workflow and frontend interactions
make lint
make check-api-contracts
```

Actual browser and host checks are recorded separately from these tests. See [verification records](docs/README.md#verification-and-status), [known limitations](docs/known-limitations.md) and [operations and recovery](docs/operations.md).

Contributor instructions are in [AGENTS.md](AGENTS.md). Start with the [documentation index](docs/README.md) to find current contracts and historical evidence.
