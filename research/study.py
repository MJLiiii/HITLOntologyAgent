"""Analysis/allocation functions over supplied observations; never fabricate study data."""
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
import platform
import random


def allocate_explanation_arms(cases, reviewers, *, seed, prior_exposures=()):
    """Two reviewers per case; a reviewer never sees the same task twice.

    Source and development-assessment digests are copied identically into both arms.
    Reviewers are pseudonyms. Allocation does not send invitations or imply consent.
    """
    if type(seed) is not int or len(set(reviewers)) != len(reviewers) or len(reviewers) < 2:
        raise ValueError('A fixed integer seed and at least two distinct reviewers are required')
    if len({case['case_id'] for case in cases}) != len(cases):
        raise ValueError('Duplicate case identity')
    seen = set(tuple(pair) for pair in prior_exposures)
    totals, arm_totals = Counter(), Counter()
    rng = random.Random(seed)
    ordered = list(cases)
    rng.shuffle(ordered)
    allocations = []
    for case in ordered:
        if not all(case.get(key) for key in ('case_id', 'task_id', 'source_packet_digest', 'assessment_digest')):
            raise ValueError('Cases must freeze both source and assessment displays')
        eligible = [r for r in reviewers if (r, case['task_id']) not in seen]
        if len(eligible) < 2:
            raise ValueError('Insufficient unexposed reviewers; do not reuse cases across explanation arms')
        arms = ['explanation_visible', 'explanation_hidden']
        rng.shuffle(arms)
        for arm in arms:
            rng.shuffle(eligible)
            reviewer = min(eligible, key=lambda r: (totals[r], arm_totals[r, arm]))
            eligible.remove(reviewer)
            seen.add((reviewer, case['task_id']))
            totals[reviewer] += 1
            arm_totals[reviewer, arm] += 1
            displays = {key: case[key] for key in ('case_id', 'task_id', 'source_packet_digest', 'assessment_digest')}
            allocations.append({**displays, 'reviewer_id': reviewer, 'arm': arm,
                                'allocation_seed': seed, 'allocation_version': 'task-exposure-v1'})
    return allocations


def _timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Review event timestamps must include a timezone')
    return parsed.timestamp()


def expert_time(events, *, observation_end, accepted, acceptance_standard_digest):
    """All active inspection/rework time across reviewers; no unobserved time is imputed.

    Input is the complete event ledger for one task/condition. A missing ledger remains
    missing; open intervals are explicitly censored at the supplied observation end.
    """
    if type(accepted) is not bool or not acceptance_standard_digest:
        raise ValueError('Supply the observed decision and common acceptance-standard digest')
    cutoff = _timestamp(observation_end)
    if not events:
        return {'expert_active_seconds': None, 'time_to_acceptance_seconds': None,
                'right_censored': not accepted, 'missing_reason': 'review_event_ledger_missing',
                'acceptance_standard_digest': acceptance_standard_digest}
    if len({(e['task_id'], e['condition']) for e in events}) != 1:
        raise ValueError('One task and condition per time ledger')
    active, states = {}, {}
    total = 0.
    previous = -math.inf
    for event in events:
        moment = _timestamp(event['time'])
        if moment < previous or moment > cutoff:
            raise ValueError('Events must be chronological and within the observation window')
        previous = moment
        who, action = event['reviewer_id'], event['event']
        if action in ('start', 'resume'):
            expected = None if action == 'start' else 'paused'
            if who in active or (states.get(who) != expected and not (action == 'start' and states.get(who) == 'ended')):
                raise ValueError('Invalid active review interval transition')
            active[who] = moment
            states[who] = 'active'
        elif action in ('pause', 'end'):
            if who not in active:
                if action != 'end' or states.get(who) != 'paused':
                    raise ValueError('Review interval cannot stop before it starts')
            else:
                total += moment - active.pop(who)
            states[who] = 'paused' if action == 'pause' else 'ended'
        else:
            raise ValueError('Unknown review event')
    if accepted and (active or any(state != 'ended' for state in states.values())):
        raise ValueError('An accepted observation requires a complete ended ledger')
    total += sum(cutoff - start for start in active.values())
    return {'expert_active_seconds': total, 'time_to_acceptance_seconds': total if accepted else None,
            'right_censored': not accepted, 'censoring_duration_seconds': total if not accepted else None,
            'open_intervals_at_cutoff': len(active), 'missing_reason': None,
            'acceptance_standard_digest': acceptance_standard_digest}


def paired_task_analysis(records, *, task_ids, replicate_ids, metric, conditions=('B', 'C')):
    """Replicates aggregate within tasks; incomplete task pairs remain explicit.

    This returns descriptive values only. It does not treat replicates as independent
    tasks or calculate significance from a synthetic engineering pilot.
    """
    if len(conditions) != 2 or len(set(conditions)) != 2 or not task_ids or not replicate_ids:
        raise ValueError('Two distinct conditions and a frozen task/replicate schedule are required')
    if len(set(task_ids)) != len(task_ids) or len(set(replicate_ids)) != len(replicate_ids):
        raise ValueError('Duplicate scheduled task or replicate')
    indexed = {}
    for record in records:
        if record['condition'] not in conditions:
            continue
        key = (record['task_id'], record['condition'], record['replicate'])
        if key in indexed:
            raise ValueError('Duplicate logical observation; select a phase and frozen run batch first')
        if key[0] not in task_ids or key[2] not in replicate_ids:
            raise ValueError('Observation falls outside the frozen schedule')
        indexed[key] = record
    rows = []
    for task in task_ids:
        means, missing = {}, defaultdict(list)
        for condition in conditions:
            values = []
            for replicate in replicate_ids:
                record = indexed.get((task, condition, replicate))
                value = record.get('metrics', {}).get(metric, {}).get('value') if record else None
                if type(value) not in (int, float) or not math.isfinite(value):
                    missing[condition].append(replicate)
                else:
                    values.append(value)
            means[condition] = sum(values) / len(values) if values and not missing[condition] else None
        difference = None if any(v is None for v in means.values()) else means[conditions[1]] - means[conditions[0]]
        rows.append({'task_id': task, 'condition_means': means, 'paired_difference': difference,
                     'missing_replicates': dict(missing)})
    differences = [r['paired_difference'] for r in rows if r['paired_difference'] is not None]
    return {'analysis': 'descriptive_task_paired', 'metric': metric, 'difference_order': list(conditions),
            'resampling_unit': 'task', 'scheduled_tasks': len(task_ids), 'complete_task_pairs': len(differences),
            'incomplete_task_pairs': len(task_ids) - len(differences), 'tasks': rows,
            'mean_paired_difference': sum(differences) / len(differences) if differences else None,
            'inferential_claim': None}


def paired_task_bootstrap(tasks, *, seed, minimum_tasks=6, resamples=10_000,
                          confidence_level=.95, missingness_policy='require_complete'):
    """Optional percentile interval over already aggregated, independent task pairs.

    Pass paired_task_analysis(...)["tasks"], not replicate observations. Each task
    has one difference in the frozen condition order; None denotes an incomplete
    pair. The six-task floor is this project's policy, not a statistical guarantee.
    The caller must establish task independence and freeze the analysis beforehand.
    This helper never runs automatically on the synthetic engineering pilot.
    """
    if type(seed) is not int:
        raise ValueError('Supply a fixed integer seed')
    if type(minimum_tasks) is not int or minimum_tasks < 6:
        raise ValueError('minimum_tasks must be an integer at least 6')
    if type(resamples) is not int or not 1000 <= resamples <= 100_000:
        raise ValueError('resamples must be an integer from 1000 to 100000')
    if (type(confidence_level) not in (int, float)
            or not 0 < confidence_level < 1):
        raise ValueError('confidence_level must be finite and strictly between zero and one')
    if missingness_policy not in ('require_complete', 'complete_case'):
        raise ValueError('Choose require_complete or explicitly opt into complete_case')

    rows, seen = [], set()
    for task in tasks:
        if (not isinstance(task, dict) or not isinstance(task.get('task_id'), str)
                or not task['task_id'].strip() or 'paired_difference' not in task):
            raise ValueError('Each row needs a nonempty task_id and paired_difference')
        task_id, value = task['task_id'], task['paired_difference']
        if task_id in seen:
            raise ValueError('Duplicate task identity; replicates are not independent tasks')
        seen.add(task_id)
        if value is not None:
            try:
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError('Each observed difference must be finite numeric data')
                value = float(value)
            except OverflowError as exc:
                raise ValueError('Each observed difference must be finite numeric data') from exc
        rows.append({'task_id': task_id, 'paired_difference': value})
    # Ordering is part of the reproducible sampler contract, independent of input row order.
    rows.sort(key=lambda row: row['task_id'])
    differences = [row['paired_difference'] for row in rows if row['paired_difference'] is not None]
    missing = [row['task_id'] for row in rows if row['paired_difference'] is None]
    count = len(differences)
    result = {
        'method': 'paired_task_percentile_bootstrap_v1', 'status': 'not_estimated',
        'reason': None, 'resampling_unit': 'task', 'statistic': 'mean_paired_difference',
        'scheduled_tasks': len(rows), 'complete_task_pairs': count,
        'incomplete_task_pairs': len(missing), 'incomplete_task_ids': missing,
        'task_differences': rows, 'missingness_policy': missingness_policy,
        'minimum_tasks': minimum_tasks, 'seed': seed, 'resamples_requested': resamples,
        'resamples_performed': 0, 'resample_size_tasks': count,
        'confidence_level': confidence_level, 'confidence_interval': None,
        'mean_paired_difference': math.fsum(value / count for value in differences) if count else None,
        'quantile_rule': 'linear interpolation at (resamples - 1) * probability',
        'rng': 'python.random.Random.randrange', 'python_version': platform.python_version(),
        'bootstrap_distribution_sha256': None, 'inferential_claim': None,
        'limitations': [
            'Independent, representative task pairs must be established externally.',
            'Six to ten tasks yield exploratory, potentially unstable percentile intervals.',
            'The task minimum is a project guardrail, not an adequate-power or coverage guarantee.',
            'Freeze exclusions, metric, condition order and analysis before collecting study data.',
            'Complete-case estimates describe observed pairs and may be biased by missing outcomes.',
        ],
    }
    if missing and missingness_policy == 'require_complete':
        result['reason'] = 'incomplete_task_pairs'
        return result
    if count < minimum_tasks:
        result['reason'] = 'insufficient_complete_tasks'
        return result
    if min(differences) == max(differences):
        result['reason'] = 'no_between_task_variation'
        return result

    rng = random.Random(seed)
    # Sampling an already paired difference is equivalent to taking the same task
    # index from both condition means; conditions and replicates never resample apart.
    means = [math.fsum(differences[rng.randrange(count)] / count for _ in range(count))
             for _ in range(resamples)]
    result['bootstrap_distribution_sha256'] = hashlib.sha256(
        json.dumps(means, allow_nan=False, separators=(',', ':')).encode('utf-8')).hexdigest()
    means.sort()

    def quantile(probability):
        position = (resamples - 1) * probability
        left = math.floor(position)
        weight = position - left
        return math.fsum((means[left] * (1 - weight), means[min(left + 1, resamples - 1)] * weight))

    tail = (1 - confidence_level) / 2
    result.update(status='estimated', resamples_performed=resamples,
                  confidence_interval={'lower': quantile(tail), 'upper': quantile(1 - tail)})
    return result
