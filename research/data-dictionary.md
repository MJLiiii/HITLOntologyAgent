# Engineering export data dictionary

JSON is the complete record. CSV emits one row per run with nested fields encoded as JSON, preserving raw diagnostics and nulls. A blank scalar CSV cell means missing, never zero; consult the corresponding `metrics` entry's reason. UUIDs, timestamps and measured wall time vary on rerun. Frozen packet, initial/output and workload digests are stable for identical inputs and software.

| Field | Meaning |
|---|---|
| `id`, `protocol_id`, `task_id`, `condition`, `replicate` | Run identity. Logical unit is task × condition × replicate; deterministic demo replicates are not independent observations. |
| `mode`, `study_status` | `deterministic_demo` or actual `model_pilot`; both remain `external_gates_pending`. |
| `status`, `evaluation_status` | Final workflow status and automated check status. D waits for a human even when checks fail. |
| `task_packet_digest`, `source_bundle_digest` | Hash of shared task packet and supplied application bundle identity. |
| `agent_manifest` | Common synthetic sources and source hashes, plain questions, inference profile and initial/base digests. No answer oracles or held-out data. |
| `evaluation_manifest` | Development test/question hashes and explicit absence of held-out study data. |
| `initial_candidate_digest`, `candidate_digest`, `candidate_ttl` | Identical starting candidate and each frozen output's SHA-256 and Turtle. |
| `budget`, `repair_history` | Frozen call/output/context/time/operation limits and actual steps/allowed feedback. Demo uses zero model calls. B receives no automated reports. |
| `validation`, `assessment` | Real engine reports, manifests, statuses, raw measurements and limitations. These do not imply human approval. |
| `case_counts` | Scheduled, passed, failed, error, timeout, unsupported, not-run; TP/FP/FN/TN and unevaluable ASK counts. |
| `metrics` | Each metric stores value, numerator, denominator, unit, and missing reason. |
| `reasoning_pass_rate` | In `metrics`: passed expected outcomes / all scheduled cases. |
| `answer_precision`, `answer_recall` | Flat aliases of finite demo ASK metrics, distinct from vocabulary measures. Missing on incomplete evaluation. |
| `vocabulary_coverage`, `vocabulary_utilisation` | Flat aliases of OntoCheck task-term and ontology-term overlap ratios. |
| `strict_fitness`, `approximate_fitness`, `structural_fitness` | OntoCheck workload diagnostics; approximate support is unapproved. |
| `elapsed_seconds` | Observed wall time for this condition's automated stage and assessment. Includes extra C/D diagnostic validation. |
| `correction_seconds` | Null until actual human work is recorded; never zero for unreviewed output. |
| `phase`, `pre_review_snapshot`, `post_review_snapshot` | D is pre-review; post-review is null until a separately recorded human workflow occurs. |
| `review_status`, `review_decisions` | D waits for a human; demo supplies no approval or simulated identity. |
| `batch_id`, `record_digest` | Model pilot invocation identity and SHA-256 seal of the complete record excluding its own seal. A changed field invalidates verification. |
| `generation_calls`, `generation_call_ids` | Model inputs, system prompt, raw/parsed outputs, hashes, observed usage, errors and call IDs. Shared initial and C/D calls appear in multiple logical arms; deduplicate IDs for physical totals. |
| `evaluation_inputs`, `evaluation_manifest.inputs_sha256` | Exact frozen development workload and base, shared across arms and post-review evaluation. No held-out input is accepted by the pilot runner. |
| `environment`, `model` | Code/lock hashes and configured model identity. Missing live weight digest/seed are explicit; configured tags are not verified weight identities. |
| `parent_run_id`, `parent_record_digest` | D post-review snapshot references its sealed pre-review run; the pre-review record is never overwritten. |
| `workflow_review_reports` | Actual persisted reports authorizing the human review, distinct from the rerun of the original experiment workload. |
| `expert_active_seconds`, `time_to_acceptance_right_censored` | Supplied observed active-time ledger total and whether the decision is unsuccessful. Missing ledger time stays null. |

The record's `metrics.answer_accuracy_required` and `metrics.answer_accuracy_evaluable` expose both required and evaluable denominators. `model_cost` and `model_tokens` are null with `deterministic_demo_no_model`. Engine failure is preserved as its status with unavailable assessment values, never converted to a successful run.

For model pilots, token/cost totals are known only when every contributing call reports that quantity. A failed structured edit retains the raw output and usage but has no final candidate; every scheduled test remains in the denominator. `elapsed_seconds_scope` explains logical/shared timing, including C's diagnostic validation. Post-review elapsed wall time is not inferred from prior automated timing. These traces can contain source text and should follow the source retention policy.
