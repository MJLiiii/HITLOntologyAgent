# Paired task bootstrap policy

`research.study.paired_task_bootstrap` implements an optional analysis operation over supplied task-level differences. It is not connected to the synthetic pilot runner. Its tests contain mathematical fixtures only. No real study, independent-task sample or empirical research conclusion is established by this implementation.

First select one frozen run batch, metric, condition pair and review phase. Call `paired_task_analysis` with the complete scheduled task and replicate IDs, then pass its `tasks` rows to this helper. Every task contributes exactly one mean difference, with the second condition minus the first. A task with any missing scheduled replicate in either condition has a missing difference. Preserve the descriptive result with its metric, condition order, replicate schedule and missing-replicate details alongside the interval report.

```python
paired = paired_task_analysis(
    frozen_records, task_ids=frozen_tasks, replicate_ids=frozen_replicates,
    metric=frozen_metric, conditions=("B", "C"),
)
interval = paired_task_bootstrap(paired["tasks"], seed=frozen_seed)
```

The input rows need unique, nonempty `task_id` strings and `paired_difference` values. Differences may be finite integers/floats or `None`. Booleans, strings, infinities and NaNs are invalid, rather than silently excluded. Duplicate task identities are invalid. The helper cannot verify that differently named tasks are actually independent or that tasks represent the intended population; this remains a protocol and dataset-review responsibility. Renaming repeated deterministic runs does not make them independent tasks.

The defaults are a 95% two-sided percentile interval, 10,000 resamples and at least six complete task pairs. `minimum_tasks` may be increased but cannot be set below six. This is a project policy based on the plan's proposed six-to-ten-task range, **not a universal statistical rule or a power/coverage guarantee**. Results at that scale are exploratory and potentially unstable. Interval method, threshold, seed, exclusions and multiplicity handling must be frozen before collecting study data. This helper computes no hypothesis tests or multiplicity-adjusted intervals.

Each resample draws N task indices with replacement from N complete task pairs and takes the mean of their paired differences. Conditions stay paired and replicates never enter the sampling population. Task IDs sort lexicographically before sampling, so input row order does not change the result. The local Python `random.Random(seed).randrange` generator leaves global RNG state unchanged. The report records Python version, seed, resample count, sample size and a SHA-256 digest of the ordered bootstrap-mean JSON distribution for reproduction; freeze the implementation and interpreter as well as these parameters.

The interval endpoints are the bootstrap-mean quantiles at `(1-confidence_level)/2` and `1-(1-confidence_level)/2`, using linear interpolation at index `(resamples-1)*probability`. These follow the percentile approach and preserve pairing described in [SciPy's official bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html). This implementation uses the standard library and does not depend on SciPy. Percentile intervals can have poor coverage in small or skewed samples; this implementation does not claim BCa correction or guaranteed coverage.

Missingness is explicit:

| Policy or condition | Result |
| --- | --- |
| Default `require_complete`, any missing scheduled pair | No interval; reason `incomplete_task_pairs` |
| Explicit `complete_case` | Resample only complete pairs, preserve all scheduled rows/counts and missing task IDs; may introduce selection bias |
| Fewer than `minimum_tasks` complete pairs | No interval; reason `insufficient_complete_tasks` |
| All complete differences identical | No interval; reason `no_between_task_variation`; avoid presenting zero empirical variance as established precision |

No-interval reports retain the descriptive mean over available pairs, if any, with `status="not_estimated"`, `confidence_interval=null` and zero resamples performed. Missing or failed observations are never replaced with zero, counted as successes, or erased from the denominator. The explicit complete-case policy estimates observed-pair behavior; it does not recover outcomes for missing pairs. Unsuccessful tasks with a valid measured outcome remain ordinary observed pairs. Time-to-acceptance censoring needs a separate, preregistered analysis; do not convert censored times to accepted completion times for this helper.

Known-answer tests verify binomial-bootstrap quantiles, six-task admission, one-task/no-variation refusal, deterministic seeds, row-order invariance, missing-pair policies, and unchanged intervals when replicate counts grow without changing task means. Actual study authorization, approved independent tasks, source/oracle freezes, reviewer participation, assessment of task dependence, study data, and empirical tables/plots remain external work.
