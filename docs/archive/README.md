# Planning and review archive

These three documents were moved from the repository root on 1 November 2026. Their bytes and line numbering are preserved. They retain requirements, rationale, and source-review evidence; their unchecked tasks and original execution instructions do not describe current implementation status.

| Original root file | Preserved document | How to use it |
| --- | --- | --- |
| `developPlan.md` | [Web product implementation plan](developPlan.md) | Product planning baseline dated 1 November 2026, brought into this checkout during the repository move. Its T00–T20 backlog has not received the older plan's requirement-by-requirement implementation audit. Consult it for product requirements; do not assume every item is implemented or superseded. |
| `CODEX_DEVELOPMENT_PLAN.md` | [Original Studio implementation plan](CODEX_DEVELOPMENT_PLAN.md) | Plan dated 31 October 2026, used for the existing implementation and the task/line references in the requirements audit. Retained for traceability. |
| `ONTOCHECK_REVIEW.md` | [OntoCheck source review](ONTOCHECK_REVIEW.md) | Historical review dated 31 October 2026 explaining the assessment design and its source-review limits. Later runtime evidence lives in the integration and verification documents. |

## Completed implementation records

The [2 November architecture cleanup plan](2026-11-02-architecture-refactor.md)
records the incremental route separation and workflow simplification; see its
[verification report](../evidence/architecture-refactor-2026-11-02.md) for results.

The [3 November GUI model selection plan](2026-11-03-gui-model-selection-plan.md)
records per-action GPT/Claude selection and preserved server boundaries; see its
[verification report](../evidence/gui-model-selection-2026-11-03.md) for results.

The following records were also consolidated here on 1 November 2026. Their requirements, decisions and observations remain intact; relative links were adjusted for the move, and the multi-LLM ledger now points to its later live verification.

| Previous path | Preserved document | How to use it |
| --- | --- | --- |
| `docs/superpowers/plans/2026-11-01-ontology-studio.md` | [Studio execution plan](2026-11-01-ontology-studio.md) | Historical work packages and review focus for the existing implementation. Use the current implementation ledger and requirements audit for status. |
| `docs/multi-llm-implementation.md` | [Multi-LLM implementation ledger](multi-llm-implementation.md) | Shared-model interfaces and implementation history. Its original credential-blocked status predates the live comparison follow-ups. |

## Current guidance and evidence

- [AGENTS.md](../../AGENTS.md): recurring contributor instructions, invariants, and checks.
- [Application README](../../README.md): setup and user workflows.
- [Implementation ledger](../implementation-ledger.md) and [requirements audit](../requirements-audit.md): decisions, implementation coverage, and outstanding gates for the original Studio plan.
- [Multi-LLM implementation](multi-llm-implementation.md), [verification](../multi-llm-verification.md), and [comparison report](../model-comparison.md): the later shared model layer and its separate live-test limits.
- [Integration evidence](../integrations.md), [known limitations](../known-limitations.md), and [release verification](../evidence/release-verification.md): dated capability and release records.

Current user instructions and recorded subsequent decisions take precedence over old execution directions. In particular, the archived instruction to keep `developPlan.md` at the root is superseded by the user's cleanup request. The new-repository assumptions, example instruction to execute only Task 1, old folder paths, and planning-time claims that no implementation exists are historical context. Do not restart completed work from them or discard unmet product requirements without reconciling them with the current task.

The ledger's initial statement that `developPlan.md` was absent describes the workspace at that time; the file was brought in later. The two plans use different task numbering, so the older requirements audit does not establish coverage of the newer plan.

## Historical paths and hashes

References to the original root filenames in old records now resolve to the same filenames under `docs/archive/`. The [release manifest](../release-manifest.json) remains unchanged: its original paths and hashes describe that release's checkout. In particular, the archived `CODEX_DEVELOPMENT_PLAN.md` still has the recorded SHA-256 and the line numbers cited in the requirements audit. Keep the two original plan/review files together so their relative link continues to work.

The dated Markdown reports formerly at `docs/{name}.md` now reside at `docs/evidence/{name}.md`, retaining their filenames: `backend-review`, `browser-acceptance`, `browser-smoke`, `bundled-resources-audit`, `native-editor-boundary`, `ontocheck-benchmark-compatibility`, `portal-smoke`, `release-verification`, and `trustgraph-pipeline-smoke`. Their observations are preserved and navigation links updated. Evidence JSON files and screenshots remain at their existing paths. The two completed implementation records use the exact old-to-new mapping above. Historical manifests retain the original paths and hashes rather than being rewritten to describe this reorganization.

Future plans and reviews belong under `docs/`; current working instructions belong in root `AGENTS.md`. Preserve these source documents rather than updating their historical checkboxes to look current.


## Retired local-model setup

On 2 November 2026 the user selected API-backed generation and removed the bundled Qwen installer, model-launch Make targets and local-model test-agent benchmark option. [The original model pin](qwen-model.lock.json) preserves the bytes formerly at `infra/model.lock.json` for historical verification. Earlier release manifests and local-model observations remain historical; use [the current API setup](../multi-llm.md) for new runs.

The [OpenAI/Claude cleanup plan](llm-api-cleanup-plan.md) records the completed two-provider runtime cleanup. Historical provider evidence remains unchanged; current setup is in [model configuration](../multi-llm.md).
