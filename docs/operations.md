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

The operator's database, session table and password hashes require protected backups. Password hashes, cookie tokens and CSRF credentials are not included in application artifact/job/research exports. Historical actor records may include a non-credential session record ID for audit linkage. This Mac milestone supplies application permissions; the Ubuntu installation and verification requirements follow below.

## Private Ubuntu setup through SSH

The selected initial Ubuntu setup uses fresh synthetic data, local identity and SQLite. The API serves the production UI on `127.0.0.1:8000`; an independent worker handles jobs. It does not require PostgreSQL, a public hostname or model credentials. Keep the Mac installation untouched. The team templates in the next section are optional later work.

The checkout-local Linux runtimes are `.runtime/setup/tools/bin/uv`, `.runtime/python`, `.runtime/node`, `.runtime/maven` and `.runtime/java`. Put their `bin` directories on `PATH` for builds and export `UV_PYTHON_INSTALL_DIR` and `JAVA_HOME` to those absolute paths. Build with the existing lockfiles and `make setup build`; `setup` removes group/other write permission from the bundled NLTK resource tree, which NLTK requires even when the sandbox mounts it read-only. Do not replace Ubuntu's system tools.

Use a private `.env` with `OE_MODE=local`, `OE_DATA_DIR=/absolute/checkout/.data/ubuntu-private`, `OE_EMBEDDED_WORKER=false`, `OE_EAGER_JOBS=false`, `OE_ENGINE_ISOLATION=linux-bubblewrap`, `JAVA_HOME=/absolute/checkout/.runtime/java` and `OE_JAVA_EXECUTABLE=/absolute/checkout/.runtime/java/bin/java`. Leave `OE_DATABASE_URL` empty for SQLite and model/provider registries unconfigured for the labelled demo. Never overwrite an existing `.env`. Run schema migration before first startup, with the same configuration, after real Linux engine checks pass.

The [local API](../infra/ubuntu/ontology-local-api.service) and [local worker](../infra/ubuntu/ontology-local-worker.service) are user-service templates for `~/projects/HITLOntologyAgent`; adjust all paths together if the checkout moves. They use the existing user account and restrictive file permissions. Verify and install them with `systemctl --user link` or copies under `~/.config/systemd/user`, then enable/start the API, check readiness, and start the worker. User services survive logout/boot only when the user's service manager is kept alive (for example, an existing linger setting); do not claim boot verification from a successful start.

From the client machine, create the tunnel and keep it running:

```sh
ssh -N -L 8000:127.0.0.1:8000 mjli@ms02
```

Replace `ms02` with the server's reachable SSH hostname/IP if necessary. Keep client port 8000 because local-origin checks allow it. For this installation, read the saved private session URL in an Ubuntu terminal and open it in the client browser while the tunnel is running:

```sh
cat /home/mjli/projects/HITLOntologyAgent/.runtime/ubuntu-private/session-url.txt
```

Treat its session fragment as a credential; never paste it into reports. The UI removes it after authentication. If the session key is replaced, retrieve the new startup URL privately from the API journal and update the saved file with mode 0600. Use `systemctl --user status ontology-local-api ontology-local-worker` for status and `systemctl --user stop ontology-local-api ontology-local-worker` for maintenance.

Stop both writers before a backup. This installation uses `.data/ubuntu-private`, so run the SQLite utility against that directory, rather than its default `.data`:

```sh
systemctl --user stop ontology-local-api ontology-local-worker
.venv/bin/python scripts/backup_restore.py backup --data-dir .data/ubuntu-private --destination /absolute/new-private-backup
systemctl --user start ontology-local-api ontology-local-worker
```

Choose a new protected destination and verify the backup result before restarting. See the restore and integrity checks below, substituting this installation's configured data directory wherever appropriate.

Linux sandbox and process watchdog errors fail closed. The watchdog samples aggregate descendant RSS/tasks/output, so its ceilings are not instantaneous kernel quotas; the user services additionally cap the entire API/worker cgroups. Do workflow/publication/recovery tests in separate disposable stores, and keep the user's initial workspace free of automatically accepted scope or published ontology.

## Optional Ubuntu team deployment

The user selected a **fresh synthetic Ubuntu store**, leaving the Mac installation and history untouched. The [Ubuntu templates](../infra/ubuntu/) prepare one API process serving the built UI, one independent worker, the existing pinned PostgreSQL 17.6 image, and one Nginx HTTPS origin. They are installation inputs, not evidence of a running or verified deployment. No hostname or certificate is assumed: `studio.example.invalid` deliberately requires replacement. Private loopback access through an SSH tunnel is a separate local-mode configuration; do not expose local bootstrap identity on a shared interface or enable insecure team flags to bypass HTTPS.

Use the [deployment plan](ubuntu-test-deployment-plan.md) and its dated evidence for actual Linux build and confinement results. Before enabling these services, the real Jena, OntoCheck and PDF boundary checks must pass on the target host, including inside the service account's execution environment. A missing or denied Bubblewrap launcher is an explicit failure; never disable confinement to make readiness green.

### Release and private configuration

The examples use `/opt/ontology-studio` for a reviewed Linux release, `/etc/ontology-studio` for private configuration, and a new `/var/lib/ontology-studio` for artifacts and ontology Git. Use the dedicated `ontology-studio` system account with no login shell. Keep source, virtual environments and runtimes root-owned and readable/executable by that account; only state and temporary scratch space need application writes. Do not reuse or overwrite existing directories without inspecting their ownership and contents.

Prepare the release at its final path using the source revision and intentionally included patch recorded in the release evidence. Do not copy `.env`, `.data`, Mac environments or private model registries from another checkout. Use Python 3.12.14, the pinned Node/uv/Maven toolchain and tested Java 21 runtime; install the Linux Python base under `.runtime/python` and Java under `.runtime/java`. Create both virtual environments at this final path, so their interpreter references do not point into an operator's home or a moved build directory. With those tools on the build operator's `PATH`:

```sh
cd /opt/ontology-studio
export UV_PYTHON_INSTALL_DIR=/opt/ontology-studio/.runtime/python
export JAVA_HOME=/opt/ontology-studio/.runtime/java
export OE_JAVA_EXECUTABLE="$JAVA_HOME/bin/java"
uv python install 3.12.14
make setup
make build
```

Build as the installation operator, then make the completed release root-owned. Confirm both Python interpreters and Java are executable by `ontology-studio`, and that `apps/studio-plugin/dist` and `services/jena-runner/target/oe-jena-runner.jar` exist. Runtime downloads/builds require network access; production service startup does not run Maven, npm, migrations, Uvicorn reload or Vite.

For a first installation only, after verifying the account and paths are unused:

```sh
sudo useradd --system --user-group --home-dir /var/lib/ontology-studio --no-create-home --shell /usr/sbin/nologin ontology-studio
sudo install -d -o root -g ontology-studio -m 0750 /etc/ontology-studio
sudo install -d -o ontology-studio -g ontology-studio -m 0700 /var/lib/ontology-studio
sudo test ! -e /etc/ontology-studio/studio.env && sudo install -o root -g ontology-studio -m 0640 infra/ubuntu/studio.env.example /etc/ontology-studio/studio.env
sudoedit /etc/ontology-studio/studio.env
```

Run these commands from the release root. Set the database URL password and `OE_POSTGRES_PASSWORD` to the same privately generated random hexadecimal password, and set `OE_TEAM_ORIGIN` to the exact chosen HTTPS origin without a trailing slash. The blank database password deliberately prevents Compose startup until configured. Hex avoids URL encoding and Compose variable interpolation; other password alphabets require correct escaping in both fields. Keep `OE_TEAM_ALLOW_INSECURE_LOOPBACK` and `OE_TEAM_TEST_SQLITE` false. Do not install a release-root `.env`; API and worker receive the same systemd `EnvironmentFile`, and operator commands below use it too. The example leaves all model/provider registries unconfigured, giving the labelled deterministic demo and no paid requests. Configure project-authorized profiles separately only when needed.

### Isolated PostgreSQL and schema

Keep the existing host PostgreSQL 18 on port 5432, the older cluster, unrelated Docker resources and the app on port 8080 untouched. Check that loopback ports 54329 and 8000 and the chosen proxy ports are available before starting anything. The [Ubuntu overlay](../infra/ubuntu/postgres.compose.yaml) adds restart and resource limits to [the pinned base Compose](../infra/compose.yaml); it does not replace its image digest or `127.0.0.1:54329` binding. Use the explicit Compose project name on every command:

```sh
cd /opt/ontology-studio
sudo docker compose --project-name ontology-studio-ubuntu --env-file /etc/ontology-studio/studio.env -f infra/compose.yaml -f infra/ubuntu/postgres.compose.yaml config --quiet
sudo docker compose --project-name ontology-studio-ubuntu --env-file /etc/ontology-studio/studio.env -f infra/compose.yaml -f infra/ubuntu/postgres.compose.yaml up -d --wait
sudo docker volume inspect ontology-studio-ubuntu_postgres_data --format '{{.Mountpoint}}'
```

Record that volume location privately with the release inventory. Inspect any pre-existing volume with that exact name before using it; a fresh deployment must not silently adopt or empty an existing store. `restart: unless-stopped` restores the database on Docker startup unless explicitly stopped. Changing `OE_POSTGRES_PASSWORD` later does not rotate an initialized database password; perform a coordinated database-role/configuration rotation. Avoid plain `docker compose config` with the real env file because it prints resolved secrets.

Before first API/worker startup, migrate **only this new database** with the shared private configuration. For later upgrades, stop both services and make the coordinated backup described below before migration. The service units deliberately do not run migrations on restart.

```sh
sudo systemd-run --unit=ontology-studio-migrate --wait --pipe --collect --uid=ontology-studio --gid=ontology-studio --property=WorkingDirectory=/opt/ontology-studio --property=EnvironmentFile=/etc/ontology-studio/studio.env --setenv=PYTHONPATH=/opt/ontology-studio/services/api/src /opt/ontology-studio/.venv/bin/python scripts/migrate.py
```

### Services, HTTPS and accounts

Install [the API unit](../infra/ubuntu/ontology-api.service) and [the worker unit](../infra/ubuntu/ontology-worker.service), then validate before starting:

```sh
sudo install -o root -g root -m 0644 infra/ubuntu/ontology-api.service infra/ubuntu/ontology-worker.service /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/ontology-api.service /etc/systemd/system/ontology-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now ontology-api.service ontology-worker.service
```

The API binds only `127.0.0.1:8000` and trusts forwarded headers only from `127.0.0.1`. Nginx passes paths, Host, Origin, cookies and CSRF headers through the single origin, replacing the client-supplied forwarded address rather than trusting a chain. The [proxy template](../infra/ubuntu/nginx.conf) permits 20 MiB plus 64 KiB overhead, matching the application request-body cap, and disables upstream retries. Queued jobs are polled by the UI; increasing proxy timeouts is not a substitute for worker recovery.

Replace every `studio.example.invalid` in the proxy template with the chosen DNS name. Provision a trusted certificate/full chain and private key at `/etc/ontology-studio/tls/fullchain.pem` and `privkey.pem`; protect the key for root/Nginx access and keep certificate renewal operational. Review existing Nginx virtual hosts, ports and TLS policy before enabling this additional site. The template belongs inside Nginx's `http` context, not as a replacement for the global configuration. After editing the installed copy:

```sh
sudo install -o root -g root -m 0644 infra/ubuntu/nginx.conf /etc/nginx/sites-available/ontology-studio
sudoedit /etc/nginx/sites-available/ontology-studio
sudo ln -s /etc/nginx/sites-available/ontology-studio /etc/nginx/sites-enabled/ontology-studio
sudo nginx -t
sudo systemctl reload nginx
```

Only enable access after the placeholder origin is gone, TLS validation succeeds, and the Linux engine checks have passed. Open only the required HTTPS/access route for authorized testers; neither database nor API ports belong on public interfaces. The template's HTTP redirect requires port 80 if used. Preserve other virtual hosts and certificate settings.

Provision synthetic accounts using the same environment, with a terminal so passwords are prompted without echo:

```sh
sudo systemd-run --unit=ontology-studio-account --wait --pty --collect --uid=ontology-studio --gid=ontology-studio --property=WorkingDirectory=/opt/ontology-studio --property=EnvironmentFile=/etc/ontology-studio/studio.env --setenv=PYTHONPATH=/opt/ontology-studio/services/api/src /opt/ontology-studio/.venv/bin/python -m oe_studio.account_cli create alice
```

For subsequent account operations, keep that command prefix and replace `create alice` with the `set-roles`, `reset-password`, `revoke-sessions` or `disable` arguments documented above. A new authenticated account can create a synthetic project and initially receives its researcher role. Assign reviewer/approver roles explicitly to the intended test humans using that project's ID; no setup command records a human review or publishes an ontology.

### Verification and lifecycle

Check `/api/v1/health/live` and `/api/v1/health/ready` through the chosen HTTPS hostname with normal certificate verification, then use a real browser to verify login/logout, Secure/HttpOnly/SameSite cookies, CSRF rejection, project isolation, source upload, queued-job completion and the production UI. Readiness probes execute local engine checks but never generate billable model requests. Test rejection of oversized uploads and wrong Origin without real data. Inspect `journalctl -u ontology-api -u ontology-worker` privately; do not publish logs or resolved service environments containing sensitive material.

The initial caps are API 1.5 GiB, worker 3 GiB and database 1.5 GiB, with one API process and one worker. They are starting limits, not measured capacity. `TasksMax`, private temporary directories and a restrictive umask apply to both services. Root-owned code/configuration and the dedicated account complement the engine sandbox. Namespace/seccomp/`NoNewPrivileges` hardening is intentionally absent pending real Bubblewrap/AppArmor tests; adding it without verification can prevent the launcher from obtaining its scoped user-namespace permission. Keep model secrets outside the engine's declared mounts.

Stop ingress/API before stopping the worker for maintenance. The worker receives SIGTERM first and finishes its current operation; `KillMode=mixed` leaves its engine children running until it exits or the 75-minute stop deadline expires, then reaps the whole service cgroup. This exceeds the current one-hour experiment lease; re-evaluate both bounds if job budgets change. It does not extend job leases or turn interrupted work into success. Abrupt failure retains the existing explicit-failure/reconciliation behavior and must not trigger replay of uncertain model calls. The API gets 120 seconds to drain requests and systemd allows 150 seconds before forced termination.

Verify worker stop/start with a controlled synthetic job, process-tree cleanup, restart after database recovery, boot startup, resource usage and a restore into a separate database/directory. PostgreSQL backup must include coordinated artifacts/Git from the same stopped-writer window; use the procedure below, not the SQLite utility. Record actual results and failures in dated evidence. Static template validation alone does not establish TLS, browser, boot, engine-isolation or recovery acceptance.


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
