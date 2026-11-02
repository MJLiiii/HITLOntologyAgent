# Workflow and optional services

See the [application README](../README.md) for installation and the [documentation index](README.md) for contracts and verification records. The running demo uses synthetic data; the [DORA packet](../research/corpora/dora-v1/README.md) remains a separate preparation step.

## Source to publication

1. Open the synthetic demo project and ask about service ownership in Chat. Inspect the cited source excerpts and ontology bindings.
2. Create a proposal, inspect the immutable additions and evidence, and run validation and assessment. A failed expectation and a broken engine are separate outcomes.
3. Correct the proposal as a new revision, rerun the checks, and inspect the current review eligibility. An old approval cannot authorize a changed bundle.
4. Record an explicit human review with rationale. Publish only the exact approved revision. The application records immutable release artifacts and advances the approved Git head with a compare-and-swap check.
5. Run the demo A–D experiment and export results. D remains awaiting a human; no expert approval or time is fabricated.

Sources also supports versioned scope/ASK-oracle editing and staged Turtle seed import. Scope changes need explicit acceptance and invalidate previous bundles. Validation provides full-IRI mapping proposals and separate human mapping decisions; these are assessment correspondences, not added OWL equivalence axioms. New mappings require a successor revision and fresh checks. Failed competency questions can request at most two source-grounded repair attempts; assessment diagnostics are withheld from automatic repair.

Development test generation now derives bounded scenarios from the candidate, frozen questions, changes and shapes. Its deterministic mode is explicit. Positive, absent-relation, boundary, missing-data, constraint-contradictory and regression expectations remain pending human oracle review; acceptance creates a successor that retains required sentinels. Unsupported coverage stays visible. See [the generation contract](synthetic-test-generation.md).

The Experiments view lets you choose scripted or actual model A–D engineering runs on the frozen synthetic scope. The model initial call is shared, B receives no engine feedback, and C/D share the exact bounded reasoner-feedback path. Stage a waiting D candidate, review it through the normal workflow, then explicitly link a stored human decision. Linking appends a post-review record and preserves the original. Missing review-timer observations remain null. The equivalent API uses `protocol_id: "model-pilot-v1"`, `POST /projects/{p}/experiments/{run}/proposal` and `POST /projects/{p}/experiments/{run}/review-results` with a persisted `review_id`.

The separate [registered synthetic-task protocol](../research/SYNTHETIC_TASKS.md) freezes a selected revision's own source packet, questions, accepted tests, shapes, fixtures and mappings for A–D execution. It preserves the original demo protocol and keeps real-study activation disabled. Each registered task shares its inputs across arms; D still needs an actual recorded workflow decision.

Model chat and proposals use at most 20 verified source passages; chat also uses at most 100 ontology triples. Selection searches the complete frozen snapshot by local word overlap and records the selected counts and any truncation. The paginated evidence browser exposes the complete corpus. A published ontology stays linked to its frozen source snapshot; freezing new sources does not rewrite its provenance.

With operator-owned TrustGraph configuration, Sources offers durable ingestion, recovery and explicit passage selection. Verified selected passages become an immutable local evidence snapshot; upstream whole-corpus completion remains unverified. Chat's source picker can select a frozen snapshot for a read-only question while retaining the published version's historical source scope by default. Candidate questions remain bound to their revision's sources. See [the selected-import contract](trustgraph-import-contract.md). The real native-editor and workspace-denial probes passed; seeded Ontology RAG still failed its known-answer quality check.

Job effects and completion results now commit together, including repair successors and experiment batches. Expired workers cannot commit, and interrupted generation retains its output without automatically replaying the model. The [recovery evidence](implementation-ledger.md#interrupted-job-recovery-continuation) records the tested failure points.

## Models and development servers

Run `make dev-api`, `make dev-worker` and `make dev-ui` in separate terminals. The frontend forwards `/api` to the backend. Model generation uses server-owned API profiles; no Qwen/Ollama runtime setup or model download is part of this workflow.

Copy an API provider descriptor from `config/llm-profiles.providers.example.json` to a private file, replace its model placeholder and project ID, and configure `OE_LLM_CONFIG_FILE` and `OE_LLM_DEFAULT_PROFILE`. Keep API credentials in the server environment or private `.env`. Include `proposal`, `repair` and `test_generation` in the selected profile's permitted purposes for both agents. See [model configuration](multi-llm.md) for provider endpoints, project allowlists and credential handling.

With no configured model the labelled deterministic demo remains available. Configured API failures remain explicit failures, never automatic demo output. Agents cannot approve expectations or publish. Their sources, prompts, model settings and outputs are frozen and inspectable.

## Verification, exports and storage

Run these commands from the repository root:

```sh
make research-pilot     # standalone synthetic run; records failures as well
make export-results     # export existing application runs with a local session
make export-pilot       # regenerate standalone pilot CSV without rerunning engines
```

`test-e2e` is an in-process HTTP workflow plus component interactions. Actual browser/host exercises are recorded separately; see [release verification](evidence/release-verification.md) and [portal smoke](evidence/portal-smoke.md). Shared deployment and the independent held-out study remain gated. Review [integration evidence](integrations.md), [known limitations](known-limitations.md), [operations](operations.md), [research protocol](../research/protocol.yaml) and [data dictionary](../research/data-dictionary.md).

The standalone pilot writes JSON, CSV and hashes to `research/results/demo-v1/`. Application export writes to `research/results/application-export/`, resolves the sole demo project automatically and reads existing records; to select a different project, run `PYTHONPATH=services/api/src .venv/bin/python scripts/export_results.py --project-id PROJECT_ID`. Export is a local operator command: it derives the bootstrap value from `.data/session.key` (or `--data-dir`) without printing it, obtains a session cookie and downloads existing records. It does not create an approval or publication.

`make api-contracts` exports the actual FastAPI schema to `docs/openapi.json` and generates request/response types, operation signatures and endpoint-specific job results in `apps/studio-plugin/src/api/openapi.ts`; `generated.ts` contains generated aliases. The UI uses these typed operations. Generation uses a temporary isolated store and includes no runtime credentials. Server validation still enforces value limits and workflow invariants. Historical records remain readable without inventing missing IDs or rewriting their manifests.

`make dev-up` starts the optional digest-pinned PostgreSQL container after you set `OE_POSTGRES_PASSWORD` in `.env`; set `OE_DATABASE_URL` to use it and run `make migrate`. `make dev-down` keeps the database volume. SQLite is sufficient for the single-machine demo. Never use `down -v` unless deletion is intended.

Stop the app before `make backup-restore-check`. This copies SQLite, artifacts and ontology Git history into an isolated temporary directory, restores them, and verifies database integrity, artifact hashes, Git integrity, workflow rows and approved refs. Persistent backup/restore commands and PostgreSQL requirements are documented in [operations](operations.md).
