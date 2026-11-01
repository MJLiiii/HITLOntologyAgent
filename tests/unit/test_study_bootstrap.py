"""Mathematical fixtures verify analysis code; these are not study observations."""
import random

import pytest

from research.study import paired_task_analysis, paired_task_bootstrap


def task_rows(values):
    return [{'task_id': f'task-{i:02d}', 'paired_difference': value}
            for i, value in enumerate(values)]


def test_known_binomial_bootstrap_has_expected_task_mean_and_percentiles():
    # Each ten-task resample has Binomial(10, .5) ones: exact .025/.975
    # quantiles of its mean are .2 and .8. This oracle predates the sampler.
    result = paired_task_bootstrap(task_rows([0.] * 5 + [1.] * 5), seed=19)
    assert result['status'] == 'estimated'
    assert result['mean_paired_difference'] == .5
    assert result['confidence_interval'] == {'lower': .2, 'upper': .8}
    assert result['resampling_unit'] == 'task'
    assert result['complete_task_pairs'] == result['resample_size_tasks'] == 10
    assert result['resamples_performed'] == 10_000
    assert result['method'] == 'paired_task_percentile_bootstrap_v1'
    assert result['inferential_claim'] is None


def test_seed_reproducibility_order_invariance_and_global_rng_unchanged():
    tasks = task_rows([-.4, -.1, .15, .7, .3, 1.2])
    before = random.getstate()
    result = paired_task_bootstrap(tasks, seed=31, resamples=1001)
    assert random.getstate() == before
    assert result == paired_task_bootstrap(list(reversed(tasks)), seed=31, resamples=1001)
    assert result['bootstrap_distribution_sha256'] != paired_task_bootstrap(
        tasks, seed=32, resamples=1001)['bootstrap_distribution_sha256']


def test_replicates_aggregate_before_resampling_and_cannot_inflate_task_count():
    def analyse(repeats):
        records = []
        for task in range(6):
            for replicate in range(2 * repeats):
                baseline = 1000 * task + 100 * (replicate % 2)
                for condition, value in [('B', baseline), ('C', baseline + task / 4)]:
                    records.append({'task_id': str(task), 'replicate': replicate,
                                    'condition': condition, 'metrics': {'value': {'value': value}}})
        return paired_task_analysis(records, task_ids=list(map(str, range(6))),
                                    replicate_ids=list(range(2 * repeats)), metric='value')

    few, many = analyse(1), analyse(10)
    assert paired_task_bootstrap(few['tasks'], seed=9) == paired_task_bootstrap(many['tasks'], seed=9)
    assert paired_task_bootstrap(many['tasks'][:1], seed=9)['confidence_interval'] is None


def test_missing_pairs_require_explicit_complete_case_choice_and_preserve_denominator():
    tasks = task_rows([0., .1, .2, .3, .4, .5, None])
    result = paired_task_bootstrap(tasks, seed=4)
    assert result['status'] == 'not_estimated'
    assert result['reason'] == 'incomplete_task_pairs'
    assert result['confidence_interval'] is None and result['resamples_performed'] == 0
    assert result['scheduled_tasks'] == 7 and result['complete_task_pairs'] == 6
    assert result['incomplete_task_ids'] == ['task-06']
    complete = paired_task_bootstrap(tasks, seed=4, missingness_policy='complete_case')
    assert complete['status'] == 'estimated'
    assert complete['scheduled_tasks'] == 7 and complete['incomplete_task_pairs'] == 1
    assert complete['task_differences'][-1]['paired_difference'] is None
    assert complete['confidence_interval'] == paired_task_bootstrap(tasks[:-1], seed=4)['confidence_interval']


@pytest.mark.parametrize('values,minimum,reason', [
    ([], 6, 'insufficient_complete_tasks'),
    ([.1], 6, 'insufficient_complete_tasks'),
    ([0., .1, .2, .3, .4], 6, 'insufficient_complete_tasks'),
    ([0., .1, .2, .3, .4, .5], 7, 'insufficient_complete_tasks'),
    ([.5] * 6, 6, 'no_between_task_variation'),
])
def test_small_or_degenerate_sample_never_produces_an_interval(values, minimum, reason):
    result = paired_task_bootstrap(task_rows(values), seed=0, minimum_tasks=minimum)
    assert result['status'] == 'not_estimated' and result['reason'] == reason
    assert result['confidence_interval'] is None and result['resamples_performed'] == 0


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf'), True, '.5', 10 ** 1000])
def test_nonfinite_or_non_numeric_difference_is_invalid_not_silently_missing(bad):
    with pytest.raises(ValueError, match='finite numeric'):
        paired_task_bootstrap(task_rows([0., .1, .2, .3, .4, bad]), seed=0)


def test_duplicate_task_identity_cannot_pose_as_more_independent_tasks():
    tasks = task_rows([0., .1, .2, .3, .4, .5])
    with pytest.raises(ValueError, match='Duplicate task'):
        paired_task_bootstrap([*tasks, tasks[0]], seed=0)
    with pytest.raises(ValueError, match='task_id'):
        paired_task_bootstrap([{'paired_difference': .5}], seed=0)


@pytest.mark.parametrize('kwargs', [
    {'seed': True}, {'seed': 1.2}, {'minimum_tasks': 5}, {'minimum_tasks': True},
    {'resamples': 999}, {'resamples': 100_001}, {'resamples': 1000.5},
    {'confidence_level': 1.}, {'confidence_level': 0.}, {'confidence_level': float('nan')},
    {'confidence_level': True}, {'missingness_policy': 'drop'},
])
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        paired_task_bootstrap(task_rows([0., .1, .2, .3, .4, .5]), **{'seed': 0, **kwargs})
