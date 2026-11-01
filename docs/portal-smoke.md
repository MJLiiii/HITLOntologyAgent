# Pinned TrustGraph portal smoke

Executed on 2026-11-01 against the real, unchanged upstream portal and a real TrustGraph 2.11.1 gateway/IAM. This closes the host registration, mount, authentication, reload, theme, and harmless Studio-read subset. It does **not** establish a complete TrustGraph ingestion/GraphRAG/OntologyRAG pipeline or a shared-deployment identity bridge.

## Exact runtime and source evidence

All archive, lockfile, and image hashes are recorded in `infra/portal/source-pins.json` and `infra/portal/compose.yaml`.

- Portal: `trustgraph-ai/trustgraph-ui@02efcac8adf04a1de1a4f601c1ecbb70ed910d6d`; committed lock; React 19.2.8, Vite 7.3.6, TypeScript 6.0.3.
- Official template: `trustgraph-ai/ui-plugin-template@9b8763e0e9c833477004c59aafb5d5530d13d4a9`; committed lock resolves TrustGraph provider/state/trustkit 2.0.3. Its own clean build initially failed because the upstream package omits TypeScript. Supplying the portal lock's TypeScript 6.0.3 executable on PATH builds the **unchanged** template (1.40 kB IIFE). No source or lockfile patch was made.
- Backend source: `trustgraph-ai/trustgraph@25d5d56ef6ee32a15dcd6710b9e1ab8c42419027`; official arm64 image `trustgraph/trustgraph-flow@sha256:29ab8fbb59fcb05318dc9208d946d4a1b2b74e6863099b9f752fc72ffc52bc0e`. Running distributions report `trustgraph-base==2.11.1` and `trustgraph-flow==2.11.1`. The running image's `auth_endpoints.py` SHA-256 is `97e91595ef189e64bb51cf49d74941925cb8005fa8d3980010368be4a2f84a18`, identical to the pinned source.
- Full `build_upstream.py` execution passed: locked installs, actual full portal build, unchanged template build, and byte comparison of every original file in all three source archives. **Zero source mismatches.** Build logs are retained locally in ignored `infra/portal/runtime/`.

The earlier cached 2.8.17 image was not used. The differing package metadata versions were tested at the actual pinned runtime; compatibility is established for the observed host/API subset, not every TrustGraph feature.

## Observed browser/API results

| Check | Observed result |
|---|---|
| Real IAM bootstrap and login | Official token-mode IAM plus official `WorkspaceInit`; synthetic operator login; real JWT authenticated `whoami` and `list-workspaces` passed. |
| Native WebSocket | Actual host footer reports **Authenticated**; the proxy relays the real first-frame authentication exchange. |
| Unchanged template | Added through the real `components.json` mechanism; rendered **Hello, World / Plugin loaded successfully** through the actual upstream loader. |
| Host theme | Midnight → Light updates the unchanged template and host. Studio's styles remain scoped and readable. |
| Studio registration and mount | Default export is a React component; actual loader renders it without props. Separate section route `ontology-engineering` avoids collision with component route `ontology-studio`. |
| Session boundary | TrustGraph sign-in leaves Studio on its local unlock screen. `check_read_boundaries.py` verifies native JWT → Studio session **401**, unauthenticated Studio session **401**, explicit Studio bootstrap session → project read **200**. |
| Grounded read | Embedded Studio returned a local-model answer to the synthetic service-ownership question with **3 verified citations and 3 triples**. Expanding the ownership citation showed frozen text, character span 0–196, and SHA-256 `cb1e2ef93963d39caca87d86523e95b1bbfd9f63fa0f0b7a717b4ef9cfd85136`. |
| Reload and navigation | Hard reload preserved both authentication sessions and reloaded Studio. Navigation to the portal section unmounted Studio; the known component route mounted it again. |
| Host layout | Real testing exposed a full-viewport-height issue. Studio now uses inherited `--page-height` with a standalone `100dvh` fallback; the host header stays visible. Both Studio builds passed after the change. |
| Approval state | No acceptance, human review, publication, or review timer action was used. Scope remains awaiting human acceptance and the approved head remains absent. |

Screenshots: [unchanged template with host light theme](screenshots/trustgraph-template-light.jpg), [Studio mounted beneath host navigation](screenshots/trustgraph-studio-mounted.jpg), [grounded answer and expanded citation](screenshots/trustgraph-studio-grounded.jpg), [Studio beneath the restored Midnight host](screenshots/trustgraph-studio-midnight.jpg). Configuration/artifact hashes are in `infra/portal/smoke-evidence.json`.

Two unrelated upstream `Local` manifest entries (`threat-intel`, `market-dynamics`) reference bundles not included in the pinned build and produce loader warnings/404s. These entries were retained, and are not reported as successful plugins. The original host smoke used only control-plane services. A later isolated overlay adds actual librarian/storage/dataflow processors; its tested scope and answer-quality limitation are recorded in [the pipeline report](trustgraph-pipeline-smoke.md).

## Reproduce locally

From the repository root, with Node/npm, Python 3.12+, Docker, and the documented optional `.venv-trustgraph` environment:

```sh
python3 infra/portal/build_upstream.py
npm run build --prefix apps/studio-plugin
python3 infra/portal/prepare_runtime.py
docker compose --env-file infra/portal/runtime/.env -f infra/portal/compose.yaml up -d
python3 infra/portal/bootstrap_smoke.py
.venv-trustgraph/bin/python infra/portal/serve.py
python3 infra/portal/check_read_boundaries.py
```

The Studio API must already run at `http://127.0.0.1:8000`; its local CSRF allowlist includes port 5183. Open `http://127.0.0.1:5183/`, choose Username login, and use the generated synthetic credentials in ignored `infra/portal/runtime/login.json`. Then open Ontology Studio and use the existing private Studio operator link/token. Do not commit, print, or share those credentials.

All new containers, networks, and volumes belong to Compose project `oe-portal-smoke`; only the gateway is published, at `127.0.0.1:18888`. Database/bus ports stay private. The portal is bound only to `127.0.0.1:5183`. No pre-existing containers/configuration are modified. The runtime `.env` contains generated bus and `tg_`-prefixed IAM bootstrap credentials. `control.yaml` uses official config, IAM, flow, and bootstrap processors; `seed.json` is an empty synthetic workspace seed.

`serve.py` serves the actual built portal; it does not replace its auth gate or React source. It appends the two test plugins to the existing manifest and adds the explicit Studio CSS link required by the upstream script-only loader. Only `/api/v1/session`, `/api/v1/projects`, `/api/v1/jobs`, and `/api/v1/health` route to Studio; all remaining native API/WebSocket paths route to the real TrustGraph gateway. No responses are mocked. The bridge is local-only and does not equate native IAM identity with Studio approval authority.

Stop this smoke stack without removing its state:

```sh
docker compose --env-file infra/portal/runtime/.env -f infra/portal/compose.yaml stop
```

## Gates still open

- Synthetic native GraphRAG/OntologyRAG and exact source/chunk/subgraph provenance are now exercised in the pipeline overlay. Global completion, PDF/page lineage and approved immutable corpus activation remain open; upload acknowledgement alone does not prove completion.
- Unresolved-provenance and cross-workspace denial tests in that complete dataflow.
- Shared deployment workspace/actor mapping; the application remains explicitly local-only.
- The real native ontology editor mutation now has [candidate-store/canonical-release invariance evidence](native-editor-boundary.md), including a populated disposable approved ref and actual native-JWT publication denial. OS publisher isolation, shared identity, and arbitrary native/dataflow feature coverage remain open.
