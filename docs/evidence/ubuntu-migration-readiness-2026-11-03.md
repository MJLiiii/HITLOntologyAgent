# Ubuntu cloned-checkout migration investigation — 3 November 2026

Historical investigation: the user subsequently switched to a fresh setup with private SSH access. See [the completed Ubuntu setup](ubuntu-private-setup-2026-11-03.md); the source-transfer requirement below is no longer active.

The user requested an investigation of the cloned Ubuntu project and the referenced Codex chat **Plan Ubuntu deployment capacity** (`01a1a2c3-0428-72a1-b1fd-021d453ac269`). That chat was read directly. Its four-service proposal and previous host inspection are planning/history evidence, not an executed deployment. During this investigation the user selected **preserve existing Mac projects and history**, superseding the earlier fresh-data assumption.

## Checkout and state

- Host: `ms02`, Ubuntu 26.04.1, x86_64, kernel `7.0.0-42-generic`.
- Checkout: `/home/mjli/projects/HITLOntologyAgent`, clean `main` at `73166584ba3d5f8448dd1a704a4f348f7c006a13` before this documentation update.
- Absent: `.env`, `.data`, `.runtime`, `.venv`, `.venv-ontocheck`, frontend `node_modules`/`dist`, Jena `target`, `infra/ubuntu` and `infra/portal/runtime`.
- The connected-device list contained only `ms02`. The referenced Mac checkout is `/Users/snuffred/Repository/HITLOnotloy`; its active database, data directory and backup were not accessible or inspected.

Git intentionally excludes private state, environments, builds, `.runtime` and `research/results`. The clone therefore supplies source and committed evidence, not proof of a transferred application store. No secrets or source project contents were read.

## Fresh host observations

| Check | Result |
| --- | --- |
| Default Python | 3.15.2 in this shell; the earlier inspection recorded 3.14.4 |
| Separate Python | 3.12.13; repository pin is 3.12.14 |
| uv | 0.11.21; recorded project pin is 0.13.6 |
| Node / npm | 24.21.0 / 11.19.0; Node pin is 26.13.0 |
| Java | OpenJDK 25.0.4.1; project records Java 21.0.13 |
| Maven | Not on PATH; recorded build tool is 3.10.0 |
| Bubblewrap | 0.11.1 |
| Docker / Compose | 29.8.1 / 5.5.1; no running containers reported |
| Memory | `free -h`: approximately 12 GiB total, 10 GiB available, 4 GiB swap unused; initial byte-precise total was 12.84 GiB |
| Root disk | 751 GiB available according to `df -hT` |
| Existing services | PostgreSQL 18 online at localhost 5432; PostgreSQL 16 stopped; existing listener on `0.0.0.0:8080` |
| Proposed ports | No listeners on 443, 8000 or 54329 at the unsandboxed snapshot |

These are local observations, not benchmarks or guarantees of external reachability. Runtime pins were read from the checkout; their download availability and a Linux lockfile installation were not tested. No installed tools were replaced.

The first restricted `ss` call reported a netlink permission error even with exit code 0, and restricted `pg_lsclusters` reported both clusters down. Those results were not accepted as host evidence. A permitted read-only check outside the Codex sandbox established the listener/cluster results above. No services were stopped or reconfigured.

## Reproduced Linux blocker

Loading `services/api/src/oe_studio/engine_isolation.py` directly with Python 3.12 (without importing or starting Studio) returned:

```text
mode: unsupported
launcher: /usr/bin/sandbox-exec
platform: linux
```

Calling `isolated_command(['/usr/bin/true'], workdir=<disposable temporary directory>, readable=[])` raised:

```text
ValueError: Unsupported engine isolation configuration; a verified macOS Seatbelt launcher is required
```

The host separately executed this transient capability probe with exit status 0:

```sh
bwrap --ro-bind /usr /usr --symlink usr/lib /lib \
  --symlink usr/lib64 /lib64 --unshare-all --die-with-parent \
  --new-session -- /usr/bin/true
```

That proves a basic namespace launch with system runtime mounts. It does not prove Studio file/network boundaries, resource limits, real engine execution or cleanup. [Bubblewrap's own documentation](https://github.com/containers/bubblewrap/blob/main/README.md) makes the constructing application's policy responsible for the protection provided.

Static inspection also found migration-relevant work beyond choosing a launcher: OntoCheck report metadata names macOS, existing boundary assertions assume macOS, PDF RSS monitoring measures only the launch PID, and Jena/OntoCheck timeout handling needs descendant verification. The [revised deployment plan](../ubuntu-test-deployment-plan.md) records these acceptance requirements without claiming they were implemented.

## Preservation requirements

`scripts/backup_restore.py` supports offline SQLite/artifact/bare-Git backup and restore. It checks hashes, SQLite integrity/foreign keys, workflow item references and Git integrity/refs; its logical state summary covers project heads and workflow items. It excludes `session.key` and does not include private configuration, profile files, external state or research/budget evidence. A migration must separately verify all database tables and preserve those additional records. PostgreSQL requires a coordinated version-compatible dump/restore and artifact/Git backup.

`make migrate` upgrades the schema and does not copy or convert a database. No SQLite-to-PostgreSQL converter was found. Preserve the source backend for the first restore: SQLite with local loopback access, or PostgreSQL with team identity. The source version must be established before selecting a PostgreSQL target; the existing 17.6 plan is not authorization for a downgrade.

`Studio.engine_configuration()` fingerprints runtime/configuration and `eligibility()`, `validate_job()` and `assessment_job()` reject changed engine configurations. Keep historical reports and published refs unchanged. Pending Mac candidates need successors and fresh Linux checks/review before publication; migration must not patch stored manifests to make them eligible.

Keep API/worker stopped until the backup has been verified offline. First startup must not race a Mac writer or dispatch restored queued jobs unexpectedly. Private configuration must use Linux paths while retaining project IDs, allowlists and budget history. Exercise verification/publication only with separate disposable synthetic stores.

## Verification and remaining work

Completed: referenced-chat review, checkout/state inventory, current host/runtime inventory, direct Linux-rejection reproduction, basic Bubblewrap launch and source inspection of backup/settings/engine eligibility. Documentation verification resolved 98 local Markdown path targets across the plan, this report, index and ledger; whitespace/code-fence checks and `git diff --check` passed.

Not performed: dependency installation, application build/test suites, source backup, state transfer/restore, Linux confinement implementation, service installation, browser workflow, paid model calls, publication or capacity testing. The checkout has no installed application environments/builds. Two delegated read-only audits supplied preliminary findings but ended with provider usage-limit errors; they are not completed independent reviews. The findings recorded here were checked directly against the source.

Next input: the Mac source store or a protected consistent backup, accessible through a specified path or authorized host connection. Linux implementation and disposable verification can proceed independently; actual migration and cutover require that source.
