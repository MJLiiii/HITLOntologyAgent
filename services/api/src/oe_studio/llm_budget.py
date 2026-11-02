"""Append-only shared smoke reservations, made at the HTTP dispatch boundary.

A reservation is an upper bound, never a claim of an actual provider charge. No
refund API exists: timeouts, transport errors and interrupted callers retain it.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4


class BudgetExceeded(ValueError):
    """A smoke call cannot be safely reserved; no HTTP request may follow."""


def _usd(nanodollars):
    return f'{Decimal(nanodollars) / Decimal(1_000_000_000):.9f}'


def _absolute_file(value):
    path = Path(value)
    if not path.is_absolute():
        raise BudgetExceeded('Smoke budget and price paths must be absolute')
    return path


def _cost_basis(path, profile, payload):
    try:
        artifact = json.loads(path.read_text())
        verified = datetime.fromisoformat(artifact['verified_at'])
        expires = datetime.fromisoformat(artifact['valid_until'])
        now = datetime.now(timezone.utc)
        if not verified <= now < expires or (expires - verified).total_seconds() > 86400:
            raise ValueError('Price verification must be current and valid for at most 24 hours')
        keys = ('id', 'revision', 'provider', 'model', 'base_url')
        entries = [entry for entry in artifact['profiles']
                   if all(entry.get(key) == profile.get(key) and profile.get(key) for key in keys)]
        if len(entries) != 1:
            raise ValueError('No exact verified profile/endpoint/revision price match')
        entry = entries[0]
        bound = entry['input_bound']
        if (not entry['source'].startswith('https://')
                or bound['method'] != 'accepted_context_limit'
                or not bound['source'].startswith('https://')
                or type(bound['tokens']) is not int or bound['tokens'] <= 0):
            raise ValueError('Missing verified accepted-context input bound')
        output = payload.get('max_completion_tokens', payload.get('max_tokens'))
        if type(output) is not int or not 1 <= output <= 4096:
            raise ValueError('Smoke output limit must be 1..4096 tokens')
        input_price = Decimal(entry['input_usd_per_million'])
        output_price = Decimal(entry['output_usd_per_million'])
        if any(not price.is_finite() or price < 0 for price in (input_price, output_price)):
            raise ValueError('Invalid full-price rate')
        # Reserve the entire verified accepted context, including provider framing;
        # this is conservative even when tokenizer/envelope details are unknown.
        cost = (bound['tokens'] * input_price + output * output_price) * 1000
        return int(cost.to_integral_value(rounding=ROUND_CEILING))
    except (OSError, KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise BudgetExceeded('Unverified or invalid smoke cost basis') from exc


def budget_summary(path):
    """Read durable totals without creating a new budget campaign."""
    path = _absolute_file(path)
    count, total = 0, 0
    if path.exists():
        with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as connection:
            count, total = connection.execute(
                'SELECT COUNT(*), COALESCE(SUM(nanodollars), 0) FROM llm_smoke_reservations').fetchone()
    return {'attempts_reserved': count, 'reserved_usd': _usd(total), 'attempt_limit': 20, 'usd_limit': '1.00'}


def reserve_from_settings(settings, profile, payload, *, timeout=None):
    """Atomically reserve one attempt and conservative full-price cost.

    Studio and every TrustGraph worker must mount the same physical SQLite file.
    Unconfigured ordinary application calls remain unmetered; partial smoke
    configuration fails closed. Never replace/delete the file to reset a run.
    """
    budget_file = getattr(settings, 'llm_smoke_budget_file', None)
    price_file = getattr(settings, 'llm_smoke_price_file', None)
    if not budget_file and not price_file:
        return None
    if not budget_file or not price_file:
        raise BudgetExceeded('Both shared smoke budget and verified prices are required')
    if timeout is not None and timeout <= 0:
        raise BudgetExceeded('Smoke dispatch deadline exhausted')
    deadline = time.monotonic() + timeout if timeout is not None else None
    budget_path, price_path = _absolute_file(budget_file), _absolute_file(price_file)
    cost = _cost_basis(price_path, profile, payload)
    reservation_id = uuid4().hex
    payload_sha = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    budget_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_timeout = min(max(deadline - time.monotonic(), 0), 30) if deadline is not None else 30
        if lock_timeout <= 0:
            raise BudgetExceeded('Smoke dispatch deadline exhausted')
        with sqlite3.connect(budget_path, timeout=lock_timeout, isolation_level=None) as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('''CREATE TABLE IF NOT EXISTS llm_smoke_reservations (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, profile_id TEXT NOT NULL,
                revision TEXT NOT NULL, payload_sha256 TEXT NOT NULL, nanodollars INTEGER NOT NULL
                CHECK (nanodollars >= 0))''')
            count, total = connection.execute(
                'SELECT COUNT(*), COALESCE(SUM(nanodollars), 0) FROM llm_smoke_reservations').fetchone()
            if count >= 20:
                raise BudgetExceeded('Smoke attempt ceiling of 20 reached')
            if total + cost > 1_000_000_000:
                raise BudgetExceeded('Smoke USD 1 full-price reservation ceiling reached')
            connection.execute('INSERT INTO llm_smoke_reservations VALUES (?, ?, ?, ?, ?, ?)',
                               (reservation_id, datetime.now(timezone.utc).isoformat(), profile['id'],
                                profile['revision'], payload_sha, cost))
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BudgetExceeded('Smoke dispatch deadline exhausted')
                connection.execute(f'PRAGMA busy_timeout = {int(min(remaining, 30) * 1000)}')
            connection.execute('COMMIT')
    except sqlite3.Error as exc:
        raise BudgetExceeded('Cannot atomically reserve shared smoke budget') from exc
    return {'id': reservation_id, 'reserved_usd': _usd(cost)}
