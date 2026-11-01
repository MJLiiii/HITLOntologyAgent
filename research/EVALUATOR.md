# External evaluation and study helpers

The application and model runner do not load held-out packets. `scripts/evaluate_frozen.py` is an offline evaluator process: it reads an externally frozen manifest and sealed outputs, evaluates each scheduled candidate with the same per-task Jena and OntoCheck inputs, and writes an immutable report into a separate evaluator output directory. Missing or failed candidates remain scheduled observations. No study has been run and no real held-out answers are included in this repository.

The checked-in `evaluator-protocol.json` defines the engineering boundary. Generated `evaluator-manifest.schema.json` and `evaluator-packet.schema.json` describe the exact Pydantic-validated inputs. A real study still needs signed scope/consent, independent oracle and mapping approval, real tasks, reviewer allocation, a common acceptance standard and a preregistered analysis freeze. The supported evaluator currently admits finite ASK answer oracles under the named-triple RDFS profile. OntoCheck may return unsupported for a question; that is retained.

Provision input and output directories outside both the repository and the application's configured data directory. Both must belong to the evaluator OS account and have mode `0700`. The input directory contains:

- `manifest.json`: protocol ID, evaluator subject, the `held_out` split, a digest-bound output file, per-task packet paths/digests and every scheduled task/condition/replicate.
- `.evaluator.key`: an independently provisioned random credential of at least 32 bytes, mode `0600`. Deliver the matching credential only to the evaluator.
- The frozen output JSON array, copied after generation has stopped. Each record's `record_digest` and canonical candidate digest are checked, and the manifest binds the full file's SHA-256.
- One packet per task, containing independently approved held-out ASK cases, OntoCheck questions, base ontology and shapes. Packet content is hash-bound before evaluation and shared by all conditions.

Invoke the evaluator as its separately provisioned identity:

```sh
PYTHONPATH=services/api/src .venv/bin/python scripts/evaluate_frozen.py \
  --input-dir /EXTERNAL/evaluator-input --output-dir /EXTERNAL/evaluator-output \
  --subject EVALUATOR_PSEUDONYM --credential-file /EXTERNAL/evaluator-credential \
  --app-data-dir /APPLICATION/data
```

Those paths and pseudonym are placeholders, not configured study resources. The CLI rejects application/repository mounts, symlink escapes, changed artifacts, wrong credentials, duplicate run keys and inconsistent schedules. It never invokes a model, retrieval, review or publication operation. Output files have mode `0600` and unique names; reports include evaluator and manifest provenance but assert no study conclusion. Keep these reports in the evaluator mount. Only explicitly reviewed aggregates should be released to the application after output and study freezes.

Separate directories plus a CLI token are not an OS isolation boundary when the application runs as the same OS user. Production study execution requires different OS/service identities and mounts that the agent/application cannot read. This deployment gate is explicit; local contract tests only establish application/path/credential behavior.

`research/study.py` supplies pure functions over supplied observations:

- `allocate_explanation_arms(cases, reviewers, seed, prior_exposures)` gives each case to two distinct pseudonymous reviewers, once with explanations and once without. It copies identical source-packet and development-assessment digests into both displays, balances assignment counts, and prevents a reviewer from seeing the same task again, including another replicate. Insufficient unexposed reviewers is an error. Consent, availability and blinding remain operator inputs; allocation sends no invitations.
- `expert_time(events, observation_end, accepted, acceptance_standard_digest)` counts every active inspection/rework interval across reviewers. Events have task, condition, reviewer, timezone-aware time and `start/pause/resume/end`; caller supplies the complete ledger, including first inspection. Missing ledgers stay null. Open unsuccessful sessions are right-censored at the explicit cutoff. Acceptance requires ended intervals and the same preapproved standard.
- `paired_task_analysis(records, task_ids, replicate_ids, metric)` averages the frozen replicate schedule within each task and reports paired condition differences. Incomplete pairs and missing replicate IDs remain visible; they do not become zero. Duplicate pre/post or repeated-run rows require an explicit phase/batch selection. The function produces descriptive values and no significance or confidence claim.
- `paired_task_bootstrap(analysis["tasks"], seed=..., minimum_tasks=6, resamples=10000, confidence_level=.95, missingness_policy="require_complete")` is an optional, separately invoked percentile interval for the mean paired task difference. It never runs automatically on pilot outputs. See [the analysis policy](analysis/bootstrap-policy.md) before invoking it. Six to ten tasks support only an exploratory, potentially unstable interval; the six-task minimum follows this project's proposed task range and does not establish statistical adequacy.

Known-answer tests exercise all these calculations using explicitly fabricated test fixtures. They are software tests, not observed reviewer behavior or study results. Before collecting real observations, freeze the protocol, schemas, implementation, environment, allocation seed, analysis plan and all external artifact hashes together; record later amendments rather than overwriting the freeze.
