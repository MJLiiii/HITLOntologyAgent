# Operations and recovery

Run from the repository root. Python application dependencies are locked in `uv.lock`, frontend dependencies in `apps/studio-plugin/package-lock.json`, and the separate OntoCheck environment in `requirements-ontocheck.lock`. The assessed upstream source commit is `69d42e38979f381fe531ae547fcc49b8ad58ef15`; version `0.1.3` alone is not its pin. Java dependencies and Maven plugin versions are fixed in `services/jena-runner/pom.xml`.

Make exports `OE_JAVA_EXECUTABLE` from `JAVA_HOME`, so the worker uses the same Java installation as the build. If launching Python directly on a machine without the documented Homebrew JDK, set `OE_JAVA_EXECUTABLE` explicitly to the real Java 21 executable; the macOS system launcher may select an older installation.

`make demo` serves only loopback. Local browser identity assumes a trusted single-machine operator who can read the terminal bootstrap URL or `.data/session.key`. `/session` requires the valid bootstrap header or existing human cookie; a service credential cannot mint a human cookie. The URL fragment is removed by the frontend and never saved in localStorage. Service tokens are not human identities and cannot authorize review/publication. Team account mode is configured separately below. Keep terminal bootstrap URLs, `.env`, `.data`, source uploads, model keys and session keys out of source control and public exports.

Database schema changes use Alembic: `make migrate` applies `0001` (workflow state) and additive `0002` (accounts, memberships, sessions and throttles). Existing artifact bytes, actor records and approvals are preserved. An unversioned local database is adopted only after comparison against the exact frozen `0001` or `0002` schema; unknown, partial or changed schemas are refused. Team API/worker and account commands require an already migrated database and never create tables implicitly. Back up first and stop writers during migration. Do not blindly stamp an unknown schema or delete a database to resolve migration errors.

## Team development on Mac

Use a separate data directory and PostgreSQL database. Keep configuration private; do not overwrite an existing `.env`. Configure `OE_MODE=team`, `OE_DATABASE_URL=postgresql+psycopg://…`, `OE_DATA_DIR=/absolute/private/team-data`, and the exact browser origin in `OE_TEAM_ORIGIN`. HTTPS is required except explicit Mac loopback development with `OE_TEAM_ALLOW_INSECURE_LOOPBACK=true` and, for example, `OE_TEAM_ORIGIN=http://127.0.0.1:5173`. `OE_TEAM_TEST_SQLITE` is reserved for isolated automated tests, not team operation.

Run `make migrate`, then start `make dev-api`, `make dev-worker` and `make dev-ui` in three terminals with the same backend configuration. Vite forwards `/api` to `STUDIO_API_URL` (default `http://127.0.0.1:8000`); the browser uses one origin and same-origin cookies. The API does not start a worker by default. `make demo` explicitly retains an embedded worker for the local demonstration. API-backed generation is configured through the private profile registry. A worker receives SIGINT/SIGTERM and finishes its current bounded operation before stopping; an abrupt interruption leaves a lease which later becomes an explicit failure, without replaying uncertain model calls. Existing publication reservations remain recoverable.

Operator account commands run from the repository root with `PYTHONPATH=services/api/src` and the same private backend environment:

```sh
export PYTHONPATH=services/api/src
.venv/bin/python -m oe_studio.account_cli create alice
.venv/bin/python -m oe_studio.account_cli set-roles alice PROJECT_ID researcher reviewer
.venv/bin/python -m oe_studio.account_cli reset-password alice
.venv/bin/python -m oe_studio.account_cli revoke-sessions alice
.venv/bin/python -m oe_studio.account_cli disable alice
```

Passwords are prompted without echo; `--password-stdin` supports protected automation without password arguments. There is no registration, SSO or email recovery. Obtain the project ID from the project list as an existing member, or inspect `projects` as the database operator for initial provisioning. Any membership permits reading that project. Researcher permits drafts, source imports and jobs; reviewer permits test expectations, mapping decisions and non-acceptance ontology reviews; approver permits scope acceptance, release acceptance and publication. Review timing is available to either reviewer or approver. Roles can be combined. A researcher creating a project receives researcher membership only; operators assign its other roles.

Passwords use Argon2 through the pinned `argon2-cffi` package. This follows the algorithm recommendation in the [FastAPI password-hashing reference](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/#install-pwdlib); Studio uses revocable opaque server sessions. Session cookies are HttpOnly/SameSite Strict and Secure for HTTPS. Tokens are hashed in PostgreSQL; mutation requests require an exact Origin and a session-bound CSRF token. Sessions expire after `OE_SESSION_HOURS` (default 12), logout revokes the current session, and password reset/disable/revoke-sessions invalidate existing sessions. Project roles and model grants are rechecked before queued execution and result commit. Stable CSRF tokens support multiple tabs. Login is throttled per normalized account and client address.

The operator's database, session table and password hashes require protected backups. Password hashes, cookie tokens and CSRF credentials are not included in application artifact/job/research exports. Historical actor records may include a non-credential session record ID for audit linkage. This Mac milestone supplies application permissions; Ubuntu engine isolation and hosted deployment remain deferred.


The optional PostgreSQL 17.6/alpine3.22 image is fixed to multi-platform manifest `sha256:ef257d85f76e48da1c64832459b59fcaba1a4dac97bf5d7450c77753542eee94`. This digest was returned by the public official Docker registry manifest endpoint on 2026-11-01; the image tag is also listed on [Docker Hub](https://hub.docker.com/layers/library/postgres/17.6-alpine3.22/images/sha256-e81e6e8ca50f8c08f2d6d0e434e7b40238434107e2ed51f8282210305d9326cf). The isolated deployment/restore exercise below also verified this image. Patch updates require an explicit pin change and a tested backup/migration path.

Stop Studio before a backup so the database, artifact directory and approved Git refs represent one consistent point. The backup utility refuses an existing destination and does not overwrite application data. It excludes `session.key`; a restored application creates a fresh local session secret.

```sh
.venv/bin/python scripts/backup_restore.py backup --data-dir .data --destination /absolute/new-backup
.venv/bin/python scripts/backup_restore.py restore --data-dir /absolute/new-backup --destination /absolute/new-restored-data
OE_DATA_DIR=/absolute/new-restored-data .venv/bin/python -m uvicorn oe_studio.main:app --app-dir services/api/src --host 127.0.0.1 --port 8000
```

`make backup-restore-check` performs both operations in a temporary isolated directory, verifies hashes and exact workflow rows, checks every content-addressed artifact, runs SQLite integrity/foreign-key checks and `git fsck`, then compares Git refs and project approved-version IDs. It requires initialized local storage; it does not create a fabricated production backup. Preserve the resulting verification output with your release evidence.

For PostgreSQL, stop writes and use a version-compatible `pg_dump`/`pg_restore` procedure plus copies of the artifacts and Git directory from that same maintenance window. The SQLite utility explicitly does not implement PostgreSQL recovery. The isolated verification below proves the synthetic workflow and coordinated restoration; backing up an actual deployment still requires its own maintenance window and protected destination.

Run the reproducible isolated PostgreSQL check with Docker available:

```sh
PYTHONPATH=services/api/src .venv/bin/python scripts/check_postgres.py
```

It reads the exact image pin from `infra/compose.yaml`, creates only the labelled `oe-studio-pg-check` container on `127.0.0.1:54329`, and refuses to replace an existing container or overwrite an output directory. A temporary mode-`0600` env file carries a random credential. Each case gets a new test database and separate synthetic artifact/Git storage under a fresh `research/results/postgres-check/` directory; normal `.data`, `.env`, other containers and volumes are untouched.

The seven current live cases cover fresh Alembic migration and metadata equality, exact adoption of an unversioned existing schema without data loss, team account/membership/session revocation, two independent Studio instances competing to publish, and fresh-instance recovery after each of `reserved`, `commit_created`, `ref_advanced` and `finalized`. Validation/assessment reports and human approvals are explicit synthetic test fixtures; these operational tests do not claim a real human review. Jena/OntoCheck are exercised separately by engine contract tests.

After applications stop writing, the check uses the **container's own PostgreSQL 17.6** `pg_dump` and `pg_restore` to restore every case into a new database, copies artifacts and the bare Git repository, verifies exact database rows, schema metadata, artifact hashes/references, `git fsck`, all Git file hashes and approved-head agreement. It checks the source did not change during backup. Session keys and database credentials are excluded from durable evidence. The finalizer removes only the test container whose random ownership label matches this invocation, including on failure.

On 2026-11-01, all six cases passed in 9.74 seconds and all six restored stores matched. The retained local evidence is `research/results/postgres-check/run-20261101/report.json`, `pytest.log`, `pytest.xml`, and per-case `backups/*/backup-manifest.json`; the report confirms PostgreSQL 17.6, the digest pin, six successful restores and removal of the owned container. No session keys remained. These tests skip during ordinary test runs unless the check script provisions its restricted test environment.

Retention/deletion of source content, reviewer information and model traces must be agreed with the organization before real data is used. Hashes do not exempt personal information from those policies. Restore backups only to a protected destination with the same access and retention rules.

On 2026-11-02 the team extension passed seven PostgreSQL cases and seven exact restores; see `research/results/two-agent-team-postgres-20261102-r3/report.json`. The original six-case record above remains historical evidence.
