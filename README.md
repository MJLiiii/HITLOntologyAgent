# Ontology Engineering Studio

A local web application for source-grounded ontology chat, inspectable proposals, real Jena validation, OntoCheck assessment and explicit human review before Git publication. The six Studio views cover Chat, Ontology, Sources, Proposals, Validation and Experiments.

This release uses neutral synthetic service-ownership data. A Deloitte domain, real expert study, confidential ingestion and shared deployment have not been approved. The deterministic demo needs no model key. Its A–D outputs demonstrate workflow behavior; they are not model-comparison or human-study findings.

## Start the application

Prerequisites: Python 3.12, `uv`, Node.js with npm, Maven and Java 21+. Git must be on PATH. The first setup/build requires network access for the exact pinned dependencies; later builds can use prepared caches. Do not serve this local-only identity mode on a public interface.

```sh
cp .env.example .env
make setup
# On other machines: export JAVA_HOME=/absolute/path/to/jdk-21
make demo
```

Open the local session URL printed in the terminal by `make demo`. It points to [http://127.0.0.1:8000](http://127.0.0.1:8000); the frontend exchanges the operator bootstrap value from the URL fragment for an HTTP-only session cookie. It then removes the fragment and does not save it to localStorage. Keep the terminal URL private; a plain unauthenticated loopback request cannot mint a human session. `make demo` builds the Java runner and both frontend bundles, applies database migrations, then starts one FastAPI process serving the UI and API. The default local SQLite database, content-addressed artifacts, session key and bare ontology Git repository are stored under `.data/`. API documentation is at `/docs`.

For development, run `make dev-api` and `make dev-ui` in separate terminals. The Vite frontend proxies `/api` to the loopback backend. Optional `OE_MODEL_URL`, `OE_MODEL_NAME` and `OE_MODEL_API_KEY` configure model generation; empty model settings keep the clearly labelled deterministic fallback. Model output cannot authorize publication.

Server-owned, project-allowlisted profiles also support OpenAI, Claude, Ollama, OpenAI-compatible gateways, a LiteLLM proxy and OpenCode Go through a shared SDK runtime. API requests can select an authorized profile; queued jobs retain its frozen non-secret configuration. See [multi-LLM configuration and bounded comparison](docs/multi-llm.md). The website keeps its existing workflow.

The optional model adapter uses the Ollama-compatible `/api/chat` protocol. Set `OE_MODEL_URL` to the server base URL, for example `http://127.0.0.1:11434`, and `OE_MODEL_NAME` to an already installed model's exact identifier; the adapter appends `/api/chat`. An optional API key is sent server-side only. Model setup/download is separate from `make setup`.

On Apple Silicon, the bundled setup pins and verifies Ollama 0.40.13 and Qwen3 1.7B from official sources, storing the runtime and model under `.runtime/`:

```sh
make setup-model
make model-serve     # keep running in one terminal
make demo-model      # run in a second terminal
```

Real local model chat and a follow-up question were verified in the browser on 1 November 2026; see [browser evidence](docs/browser-smoke.md). This is a functional check, not a model-quality study. The model's structured citations are restricted to the supplied evidence and ontology indices, and generation has a total deadline. Invalid output is retained and rejected. A separate real model experiment attempted a duplicate triple and correctly produced failed observations for all scheduled arms; the small model's proposals are not assumed reliable.

## Use the workflow

1. Open the synthetic demo project and ask about service ownership in Chat. Inspect the cited source excerpts and ontology bindings.
2. Create a proposal, inspect the immutable additions and evidence, and run validation and assessment. A failed expectation and a broken engine are separate outcomes.
3. Correct the proposal as a new revision, rerun the checks, and inspect the current review eligibility. An old approval cannot authorize a changed bundle.
4. Record an explicit human review with rationale. Publish only the exact approved revision. The application records immutable release artifacts and advances the approved Git head with a compare-and-swap check.
5. Run the demo A–D experiment and export results. D remains awaiting a human; no expert approval or time is fabricated.

Sources also supports versioned scope/ASK-oracle editing and staged Turtle seed import. Scope changes need explicit acceptance and invalidate previous bundles. Validation provides full-IRI mapping proposals and separate human mapping decisions; these are assessment correspondences, not added OWL equivalence axioms. New mappings require a successor revision and fresh checks. Failed competency questions can request at most two source-grounded repair attempts; assessment diagnostics are withheld from automatic repair.

Development test generation now derives bounded scenarios from the candidate, frozen questions, changes and shapes. Its deterministic mode is explicit. Positive, absent-relation, boundary, missing-data, constraint-contradictory and regression expectations remain pending human oracle review; acceptance creates a successor that retains required sentinels. Unsupported coverage stays visible. See [the generation contract](docs/synthetic-test-generation.md).

The Experiments view lets you choose scripted or actual model A–D engineering runs on the frozen synthetic scope. The model initial call is shared, B receives no engine feedback, and C/D share the exact bounded reasoner-feedback path. Stage a waiting D candidate, review it through the normal workflow, then explicitly link a stored human decision. Linking appends a post-review record and preserves the original. Missing review-timer observations remain null. The equivalent API uses `protocol_id: "model-pilot-v1"`, `POST /projects/{p}/experiments/{run}/proposal` and `POST /projects/{p}/experiments/{run}/review-results` with a persisted `review_id`.

The separate [registered synthetic-task protocol](research/SYNTHETIC_TASKS.md) freezes a selected revision's own source packet, questions, accepted tests, shapes, fixtures and mappings for A–D execution. It preserves the original demo protocol and keeps real-study activation disabled. Each registered task shares its inputs across arms; D still needs an actual recorded workflow decision.

Model chat and proposals use at most 20 verified source passages; chat also uses at most 100 ontology triples. Selection searches the complete frozen snapshot by local word overlap and records the selected counts and any truncation. The paginated evidence browser exposes the complete corpus. A published ontology stays linked to its frozen source snapshot; freezing new sources does not rewrite its provenance.

With operator-owned TrustGraph configuration, Sources offers durable ingestion, recovery and explicit passage selection. Verified selected passages become an immutable local evidence snapshot; upstream whole-corpus completion remains unverified. Chat's source picker can select a frozen snapshot for a read-only question while retaining the published version's historical source scope by default. Candidate questions remain bound to their revision's sources. See [the selected-import contract](docs/trustgraph-import-contract.md). The real native-editor and workspace-denial probes passed; seeded Ontology RAG still failed its known-answer quality check.

Job effects and completion results now commit together, including repair successors and experiment batches. Expired workers cannot commit, and interrupted generation retains its output without automatically replaying the model. The [recovery evidence](docs/implementation-ledger.md#interrupted-job-recovery-continuation) records the tested failure points.

## Check and reproduce

```sh
make test-unit
make test-contract       # real Jena and isolated OntoCheck; requires setup/build
make test-integration
make test-e2e            # complete HTTP workflow and frontend interaction tests
make lint
make check-api-contracts # compare actual schema with generated request/response contracts
make research-pilot     # standalone synthetic run; records failures as well
make export-results     # export existing runs from the running app with a local session
make export-pilot       # regenerate standalone pilot CSV without rerunning engines
```

`test-e2e` is an in-process HTTP workflow plus component interactions. Actual browser/host exercises are recorded separately; see [release verification](docs/release-verification.md) and [portal smoke](docs/portal-smoke.md). Shared deployment and the independent held-out study remain gated. Review [integration evidence](docs/integrations.md), [known limitations](docs/known-limitations.md), [operations](docs/operations.md), [research protocol](research/protocol.yaml) and [data dictionary](research/data-dictionary.md).

The standalone pilot writes JSON, CSV and hashes to `research/results/demo-v1/`. Application export writes to `research/results/application-export/`, resolves the sole demo project automatically and reads existing records; to select a different project, run `PYTHONPATH=services/api/src .venv/bin/python scripts/export_results.py --project-id PROJECT_ID`. Export is a local operator command: it derives the bootstrap value from `.data/session.key` (or `--data-dir`) without printing it, obtains a session cookie and downloads existing records. It does not create an approval or publication.

`make api-contracts` exports the actual FastAPI schema to `docs/openapi.json` and generates request/response types, operation signatures and endpoint-specific job results in `apps/studio-plugin/src/api/openapi.ts`; `generated.ts` contains generated aliases. The UI uses these typed operations. Generation uses a temporary isolated store and includes no runtime credentials. Server validation still enforces value limits and workflow invariants. Historical records remain readable without inventing missing IDs or rewriting their manifests.

`make dev-up` starts the optional digest-pinned PostgreSQL container after you set `OE_POSTGRES_PASSWORD` in `.env`; set `OE_DATABASE_URL` to use it and run `make migrate`. `make dev-down` keeps the database volume. SQLite is sufficient for the single-machine demo. Never use `down -v` unless deletion is intended.

Stop the app before `make backup-restore-check`. This copies SQLite, artifacts and ontology Git history into an isolated temporary directory, restores them, and verifies database integrity, artifact hashes, Git integrity, workflow rows and approved refs. Persistent backup/restore commands and PostgreSQL requirements are documented in [operations](docs/operations.md).
