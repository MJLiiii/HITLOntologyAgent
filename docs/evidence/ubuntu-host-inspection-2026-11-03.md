# Ubuntu host inspection — 3 November 2026

The user requested a live check through Remote Desktop Commander. The online device `ms02` was inspected with read-only inventory commands and a transient Bubblewrap capability probe. No packages were installed, services restarted, server configuration changed, project data copied, credentials read or model requests made.

## Observed host

| Item | Live result |
| --- | --- |
| OS | Ubuntu 26.04.1 LTS; kernel `7.0.0-42-generic` |
| Architecture / processor | x86_64; AMD Ryzen 9 7945HX; 16 cores / 32 threads |
| Kernel-visible memory | 13,786,591,232 bytes = 12.84 GiB |
| Available memory at first snapshot | 11,759,370,240 bytes = 10.95 GiB |
| Used memory at first snapshot | Approximately 1.89 GiB |
| Swap | Approximately 4 GiB, unused |
| Root storage | NVMe/ext4; `df -hT` reported 915G total, 119G used, 751G available, 14% used |
| Load / pressure | Load averages 0.00 / 0.00 / 0.00; subsequent memory pressure averages 0.00 |
| Running containers | None reported by accessible Docker daemon; existing images/volumes/stopped containers were not inventoried |

The earlier user-reported Ubuntu 24.04 / 16 GB specification is superseded for deployment sizing by this live snapshot. The reason for the difference between advertised RAM and kernel-visible RAM was not established. These measurements show available resources at inspection time, not a peak-load or concurrent-user benchmark.

## Runtime readiness

| Runtime | Observed | Plan implication |
| --- | --- | --- |
| Default Python | 3.14.4 | Outside Studio's `>=3.12,<3.13` requirement |
| Additional Python | 3.12.13 | Install/use exact project pin 3.12.14 alongside it |
| uv | 0.11.21 | Project CI/runtime pin is 0.13.6 |
| Node / npm | 24.21.0 / 11.19.0 | Project Node pin is 26.13.0; retain lockfile-based installation |
| Java | OpenJDK 25.0.4.1 | Meets Java 21+ floor, but differs from tested Java 21.0.13; use project-specific Java for reproducibility |
| Maven | Not found on current PATH | Provision the recorded build tool (3.10.0) if building here |
| Git / Make | 2.53.0 / 4.4.1 | Available |
| Docker / Compose | 29.8.1 / 5.5.1 | Available and daemon accessible |
| Bubblewrap | 0.11.1 | Available; minimal namespace launch succeeded |
| Nginx / Caddy | Neither found on current PATH | HTTPS proxy still needs provisioning |

PATH checks do not prove that no alternate installation exists. Tool replacement is unnecessary: project-specific versions can coexist with existing applications. Requirements were compared with `.python-version`, `.node-version`, `.github/workflows/ci.yml`, `infra/versions.lock.yaml`, `pyproject.toml` and the current Makefile.

## Existing workloads and ports

Native PostgreSQL 18 `main` is online on localhost port 5432; a PostgreSQL 16 `main` cluster on port 5433 is stopped. An existing Uvicorn process listens on port 8080 on all IPv4 interfaces. Its application was not interrogated. Other development/management processes are running and contribute to the measured baseline.

Ports 443, 8000 and 54329 had no TCP listeners at inspection time. This establishes local availability only, not firewall rules, external reachability, DNS or certificate readiness. Preserve existing services; use the plan's separate pinned PostgreSQL 17.6 instance on localhost 54329 and separate test storage.

The inspected standard project/deployment locations did not contain Studio. This was a limited location check, not an exhaustive filesystem search or proof that no copy exists elsewhere.

## Sandbox capability and its limits

AppArmor was enabled, `apparmor_restrict_unprivileged_userns=1`, `unprivileged_userns_clone=1`, and the user-namespace maximum was 41,215. Cgroup v2 controllers included memory, CPU, I/O and PIDs.

The following transient command returned exit status 0:

```sh
bwrap --ro-bind / / --unshare-all --die-with-parent -- /usr/bin/true
```

This demonstrates that this account can perform that basic namespace launch under the observed host policy. It deliberately makes the host filesystem visible read-only, executes only `true`, and does **not** verify restricted file visibility, network denial via actual connection attempts, descendant cleanup, resource limits or Studio's eventual sandbox policy. It does not change AppArmor or system settings.

The repository still implements only macOS Seatbelt in `engine_isolation.py`. Linux engine support and its real boundary tests remain the blocking implementation task. A successful `bwrap` probe does not make Jena, OntoCheck or PDF extraction ready in the current app.

## Updated recommendation

Keep the [four-service core plan](../ubuntu-test-deployment-plan.md): HTTPS proxy, API with built UI, one independent worker and a separate PostgreSQL container. Revise the nominal 16 GiB budget to the measured 12.84 GiB: initially allow roughly 6 GiB for new Studio services, about 2 GiB for the existing light baseline, and about 4.8 GiB for headroom. These are planning allocations, not enforced or benchmarked limits; require at least 3 GiB available under the actual workload.

Keep TrustGraph deferred. Do not downgrade Ubuntu solely to match the initial plan; implement and verify on the actual 26.04.1 host. Install the pinned project runtimes alongside existing ones, then carry out the plan's workflow, recovery and load tests before estimating user capacity.

Evidence was obtained using `lscpu`, `/etc/os-release`, `/proc` memory/load/pressure data, `free`, `df`, `lsblk`, version commands, `docker ps/stats`, `systemctl list-units`, `ss`, `pg_lsclusters`, and the stated launcher probe. No privileged commands or permission changes were attempted. Independent review confirmed the implications and prompted correction of the original RAM headroom assumption. This is host evidence only; no Studio application tests ran on the server.
