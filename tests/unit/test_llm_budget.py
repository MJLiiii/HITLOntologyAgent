"""Budget tests catch undercharging, lost reservations and cross-process overbooking."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from oe_studio import llm_budget


def configured(tmp_path, **overrides):
    now = datetime.now(timezone.utc)
    entry = {
        'id': 'go-glm', 'revision': 'frozen', 'provider': 'openai', 'model': 'glm-5.3-flash',
        'base_url': 'https://opencode.ai/inference/go/openai/v1',
        'input_usd_per_million': '0.15', 'output_usd_per_million': '0.50',
        'source': 'https://opencode.ai/v2/docs/console/go/',
        'input_bound': {'method': 'accepted_context_limit', 'tokens': 200000,
                        'source': 'https://opencode.ai/inference/go/v1/models'},
    }
    entry.update(overrides)
    prices = tmp_path / 'prices.json'
    prices.write_text(json.dumps({'verified_at': now.isoformat(),
                                 'valid_until': (now + timedelta(hours=1)).isoformat(), 'profiles': [entry]}))
    settings = SimpleNamespace(llm_smoke_budget_file=tmp_path / 'budget.sqlite', llm_smoke_price_file=prices)
    profile = {k: entry[k] for k in ('id', 'revision', 'provider', 'model', 'base_url')}
    return settings, profile


def test_reserves_full_verified_context_and_output_before_dispatch(tmp_path):
    settings, profile = configured(tmp_path)
    reservation = llm_budget.reserve_from_settings(settings, profile, {'max_tokens': 4096, 'messages': []})
    assert reservation['reserved_usd'] == '0.032048000'
    assert llm_budget.budget_summary(settings.llm_smoke_budget_file) == {
        'attempts_reserved': 1, 'reserved_usd': '0.032048000', 'attempt_limit': 20, 'usd_limit': '1.00'}


def test_concurrent_reservations_cannot_exceed_twenty_attempts(tmp_path):
    settings, profile = configured(tmp_path, input_usd_per_million='0', output_usd_per_million='0')
    def reserve(_):
        try:
            llm_budget.reserve_from_settings(settings, profile, {'max_tokens': 1})
            return True
        except llm_budget.BudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(reserve, range(40))) == 20
    assert llm_budget.budget_summary(settings.llm_smoke_budget_file)['attempts_reserved'] == 20


def test_full_price_ceiling_is_shared_and_reservations_are_never_released(tmp_path):
    settings, profile = configured(tmp_path, input_usd_per_million='2', output_usd_per_million='0')
    for _ in range(2):
        llm_budget.reserve_from_settings(settings, profile, {'max_tokens': 1})
    with pytest.raises(llm_budget.BudgetExceeded, match='USD'):
        llm_budget.reserve_from_settings(settings, profile, {'max_tokens': 1})
    assert llm_budget.budget_summary(settings.llm_smoke_budget_file)['reserved_usd'] == '0.800000000'


@pytest.mark.parametrize('changes', [
    {'input_bound': None}, {'input_usd_per_million': '-1'}, {'input_usd_per_million': 'NaN'},
    {'source': ''}, {'input_bound': {'method': 'guess', 'tokens': 200000, 'source': 'https://example.com'}},
])
def test_unverified_or_invalid_cost_basis_fails_closed(tmp_path, changes):
    settings, profile = configured(tmp_path, **changes)
    with pytest.raises(llm_budget.BudgetExceeded):
        llm_budget.reserve_from_settings(settings, profile, {'max_tokens': 1})
    assert not settings.llm_smoke_budget_file.exists()


@pytest.mark.parametrize('mutation', ['expired', 'future', 'revision', 'endpoint', 'output'])
def test_stale_mismatched_or_overlimit_dispatch_is_rejected(tmp_path, mutation):
    settings, profile = configured(tmp_path)
    prices = json.loads(settings.llm_smoke_price_file.read_text())
    payload = {'max_tokens': 4096}
    if mutation == 'expired':
        prices['valid_until'] = '2020-01-01T00:00:00+00:00'
    elif mutation == 'future':
        prices['verified_at'] = '2099-01-01T00:00:00+00:00'
    elif mutation == 'revision':
        profile['revision'] = 'changed'
    elif mutation == 'endpoint':
        profile['base_url'] = 'https://another-provider.example/v1'
    else:
        payload['max_tokens'] = 4097
    settings.llm_smoke_price_file.write_text(json.dumps(prices))
    with pytest.raises(llm_budget.BudgetExceeded):
        llm_budget.reserve_from_settings(settings, profile, payload)
    assert not settings.llm_smoke_budget_file.exists()


def test_normal_application_is_unmetered_but_partial_smoke_config_is_rejected(tmp_path):
    assert llm_budget.reserve_from_settings(SimpleNamespace(), {}, {}) is None
    with pytest.raises(llm_budget.BudgetExceeded):
        llm_budget.reserve_from_settings(SimpleNamespace(llm_smoke_budget_file=tmp_path / 'budget.sqlite'), {}, {})


def test_shared_lock_wait_cannot_outlive_remaining_dispatch_deadline(tmp_path):
    import sqlite3
    import time
    settings, profile = configured(tmp_path)
    llm_budget.reserve_from_settings(settings, profile, {'max_tokens': 1})
    with sqlite3.connect(settings.llm_smoke_budget_file) as holder:
        holder.execute('BEGIN EXCLUSIVE')
        started = time.monotonic()
        with pytest.raises(llm_budget.BudgetExceeded):
            llm_budget.reserve_from_settings(settings, profile, {'max_tokens': 1}, timeout=0.03)
        assert time.monotonic() - started < 0.5
    assert llm_budget.budget_summary(settings.llm_smoke_budget_file)['attempts_reserved'] == 1
