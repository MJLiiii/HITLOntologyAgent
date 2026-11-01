# Analysis status

No confirmatory study has been run. `make research-pilot` exports a synthetic demonstration under ignored `research/results/demo-v1/`; `make export-pilot` regenerates its CSV and file-hash manifest without rerunning engines. `make export-results` downloads existing records from the running application's demo project into `research/results/application-export/`. All scheduled runs and engine errors are retained. Read `data-dictionary.md` and `scoring-rubric.md` before interpreting scores.

The future analysis must aggregate replicate outcomes within tasks, use tasks as paired/resampling units, preserve D pre/post-review results, retain unsuccessful cases and count all active expert minutes. Freeze code, rubric, exclusions and hashes before confirmatory data collection. Do not compute confidence intervals or significance from repeated deterministic demo outputs. Proposed sample sizes and outcomes in the development plan are targets, not observed findings.

To exercise the actual configured model without starting a study:

```sh
OE_MODEL_URL=http://127.0.0.1:11434 OE_MODEL_NAME=qwen3:1.7b \
  .venv/bin/python scripts/research_pilot.py --mode model --maximum-repairs 2
```

Each invocation creates a fresh output directory and retains failed generations. An explicit existing model output cannot be overwritten. `--export-only --output PATH` recreates CSV from the frozen JSON. Model runs share physical call IDs across A–D; summing all row token values would double-count shared work. No command records a human approval.

The separate [evaluator workflow](../EVALUATOR.md) defines external frozen manifests, private inputs/reports, RQ3 exposure-safe allocation, full active-time/censoring calculations and paired task-level descriptive analysis. An optional [task bootstrap helper](bootstrap-policy.md) now implements an explicitly seeded percentile interval over supplied independent task pairs, with a six-task floor and explicit missingness/no-estimate rules. It is not invoked on demonstration runs. Its tests use known-answer synthetic fixtures only; real evaluator mounts and study approvals remain external requirements.
