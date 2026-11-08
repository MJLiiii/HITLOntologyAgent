# Fresh private Ubuntu setup — 3 November 2026

The user explicitly selected a **fresh Ubuntu setup** and **private access through an SSH tunnel**, replacing the intermediate request to preserve Mac history. The Mac installation was not accessed or changed. This deployment contains only synthetic demonstration data and has no configured model or paid API traffic.

## Running installation

- Host: `ms02`, Ubuntu 26.04.1, x86_64; checkout `/home/mjli/projects/HITLOntologyAgent`.
- Source baseline: `73166584ba3d5f8448dd1a704a4f348f7c006a13` plus this uncommitted Ubuntu implementation and documentation patch. No commit or remote publication was made.
- Production UI/API: user service `ontology-local-api.service`, bound to **127.0.0.1:8000**. No Vite development server or public proxy is running for Studio.
- Independent worker: user service `ontology-local-worker.service`. Both are enabled and active, with zero restarts at the final observation. Existing user lingering was already enabled; it was not changed. A reboot was not performed.
- Private configuration: newly created mode-0600 `.env`. Fresh SQLite/artifact/ontology-Git state: `.data/ubuntu-private`, protected from other accounts. No prior configuration was overwritten.
- Private session URL: `.runtime/ubuntu-private/session-url.txt`, mode 0600. Its value is deliberately absent from this report and tool outputs. See [SSH access and operation](../operations.md#private-ubuntu-setup-through-ssh).
- Existing PostgreSQL clusters, Docker resources and the unrelated app on port 8080 were preserved. No Studio PostgreSQL, Nginx or TrustGraph deployment was started. Team deployment templates are prepared options only.

Readiness through the actual user service returned HTTP 200: `status=ready`, `mode=local`, Jena/OntoCheck/database available, model/TrustGraph/shared authentication not configured. A read-only database check found one synthetic project, zero jobs/proposals, no accepted scope and no approved version. Browser workflow writes were confined to a separate disposable store.

## Runtime and implementation

Installed alongside system tools, under the checkout:

| Runtime | Version / location |
| --- | --- |
| Python | 3.12.14, managed under `.runtime/python`; application `.venv` and separate `.venv-ontocheck` |
| uv | 0.13.6, `.runtime/setup/tools/bin/uv` |
| Node | 26.13.0, `.runtime/node` |
| Maven | 3.10.0, `.runtime/maven` |
| Java | Temurin 21.0.13+9, `.runtime/java` |
| Bubblewrap | Existing host 0.11.1 |

Python, application, optional SDK, frontend and OntoCheck dependencies were installed from the repository pins/lockfiles. Node, Maven and Java archives were checked against their official SHA-256/SHA-512 values; download identities/checksums are in `.runtime/setup/downloads/*-verified.json`. System runtimes were not replaced. Jena and both frontend production bundles built successfully.

`engine_isolation.py` now selects `linux-bubblewrap` on Linux while retaining the macOS Seatbelt path. The Linux policy creates isolated namespaces, disables nested user namespaces, drops capabilities, clears the engine environment, exposes system libraries and declared inputs read-only, and gives each invocation one writable scratch directory. The sandbox root is read-only. Host/external networking is isolated; sandbox-local loopback, proc and dev remain available. Missing/denied confinement never falls back to an ordinary process. Launcher bytes and policy identity participate in engine configuration.

`engine_process.py` supervises aggregate descendant RSS, process/thread counts and combined output. Jena uses 1 GiB/128 tasks/16 MiB output/30 seconds; OntoCheck uses 1 GiB/64 tasks/8 MiB output/default 20 seconds; PDF uses 512 MiB/32 tasks/8 MiB output/15 seconds and retains its child CPU/address-space/file limits. Cleanup covers timeout, cancellation and normal exit with leftover descendants. These watchdogs sample at approximately 50 ms and permit transient overshoot; they are not instantaneous kernel quotas. The private API and worker services additionally cap their complete cgroups at 1.5 GiB and 3 GiB.

Resource-supervisor changes now alter the immutable engine fingerprint. Old checked bundles cannot silently inherit new resource enforcement. Published history and historical evidence were not rewritten. NLTK refused the clone's group-writable resources; `make setup` now removes group/other write permission from `resources/nltk`, preserving its verified contents.

## Verification

| Check | Actual result |
| --- | --- |
| Final complete backend suite | **648 passed, 8 skipped**, 106.96 seconds |
| Frontend interactions | **76 passed**, 15 files |
| Java and both production UI builds | Passed |
| Ruff, TypeScript, API contract drift | Passed |
| Real Linux file/network boundary tests | Passed; native TCP/UDP and descendants could not reach host listeners |
| Process supervision | Timeout/cancellation/normal-exit cleanup, nested-session cleanup, aggregate RSS/task/output exhaustion and CPU-timeout classification passed |
| Actual browser | Production UI, six views, deterministic proposal creation, real Jena `passed` and OntoCheck `completed`; no scope acceptance/publication or page errors |
| Actual private service | Production UI loaded; bootstrap fragment removed; readiness available; working store remains fresh |
| Disposable SQLite backup/restore | Passed; 19 workflow items, artifact hashes and empty approved Git refs retained |
| User unit syntax | `systemd-analyze --user verify` passed before installation; both installed services active |
| Independent code review | One assessment failure-report issue reproduced and fixed with a red/green regression; no other actionable blocker reported |
| Documentation and patch hygiene | 156 local Markdown paths/anchors resolved; code fences, Ruff and `git diff --check` passed |

Backend skips were exactly one opt-in live TrustGraph probe and seven isolated PostgreSQL tests. PostgreSQL was not selected for this setup. The backend emitted 3,415 existing dependency deprecation warnings. Logs/XML, build output, lint/contracts and backup verification are retained under `.runtime/setup/`; final backend records are `backend-final.log` and `backend-final.xml`.

Browser checks used Playwright 1.64.1 in `.runtime/browser` and an existing Chromium installation in a fresh temporary profile; Ego was unavailable on Ubuntu. Credential-free screenshots and the final structured result are `.runtime/setup/browser/private-home.png`, `engine-checks.png` and `result.json`. Initial browser-driver attempts used overly strict selectors or matched “not completed” prematurely; those were test-driver failures, not successful workflow evidence. Corrected checks verified completed API results and rendered UI. Both disposable API processes were stopped, and no test runtime remains listening on port 5183.

Initial installation hit sandbox DNS restrictions; the authorized network installation then succeeded. The first Java metadata request failed, so the exact official Temurin release was discovered and checksum-verified instead. A direct OntoCheck import first lacked bundled data, then exposed the directory-permission issue; its corrected confined import and full engine suites passed. These attempts are not relabelled as initial successes.

At the final service snapshot, the API used approximately 78 MiB and the idle worker 41 MiB, with observed cgroup peaks of approximately 164 MiB and 43 MiB. These are momentary startup/readiness observations, not a concurrent-user benchmark or memory requirement.

## Remaining boundaries

- SSH routing from the user's client, reboot recovery, sustained capacity and public/team HTTPS deployment were not exercised. The server's actual loopback UI and user services were verified.
- Linux ran locally on Ubuntu 26.04.1. CI now includes Ubuntu 24.04 and macOS, but those remote jobs and a live Mac regression run were not executed in this session. The Mac process-table parser was checked against upstream source and a controlled fixture.
- `npm audit` reported four existing development-tool dependency entries (one moderate, one high, two critical: Vite/Vitest and their test dependencies). They remain pinned; no forced upgrade was applied. The deployment serves compiled assets rather than their development/test servers. Details: `.runtime/setup/npm-audit.json`.
- No live OpenAI/Claude generation, real-data study, Mac state transfer, human acceptance or ontology publication occurred. Synthetic workflow/publication fixtures in the backend suite used disposable stores.

See the [current deployment plan](../ubuntu-test-deployment-plan.md) and [operations guide](../operations.md). The [earlier investigation](ubuntu-migration-readiness-2026-11-03.md) remains historical evidence of the pre-implementation state.
