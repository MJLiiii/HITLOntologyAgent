"""Cleanup must never signal an unverified process or mismatched deployment."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location('team_browser_runtime', Path(__file__).resolve().parents[2] / 'scripts/team_browser_smoke_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def state(tmp_path, **overrides):
    value = {'owner': 'owned', 'container': 'owned-container', 'processes': [{'pid': 123, 'identity': 'start command'}], **overrides}
    (tmp_path / 'state.json').write_text(json.dumps(value))
    return value


def test_wrong_container_owner_prevents_all_process_signals(tmp_path, monkeypatch):
    state(tmp_path)
    monkeypatch.setattr(runtime, 'run', Mock(return_value=SimpleNamespace(stdout='someone-else')))
    signal = Mock()
    fingerprint = Mock()
    monkeypatch.setattr(runtime.os, 'killpg', signal)
    monkeypatch.setattr(runtime, 'process_identity', fingerprint)
    with pytest.raises(SystemExit, match='different owner'):
        runtime.stop(tmp_path)
    signal.assert_not_called()
    fingerprint.assert_not_called()


def test_stopped_and_removed_runtimes_are_idempotent(tmp_path, monkeypatch):
    state(tmp_path, stopped=True)
    signal = Mock()
    docker = Mock()
    monkeypatch.setattr(runtime.os, 'killpg', signal)
    monkeypatch.setattr(runtime, 'run', docker)
    runtime.stop(tmp_path)
    runtime.stop(tmp_path / 'already-removed')
    signal.assert_not_called()
    docker.assert_not_called()


def test_stale_pid_prevents_all_signals_and_preserves_owned_runtime(tmp_path, monkeypatch):
    state(tmp_path, processes=[{'pid': 123, 'identity': 'start command'}, {'pid': 456, 'identity': 'old process'}])
    docker = Mock(return_value=SimpleNamespace(stdout='owned'))
    monkeypatch.setattr(runtime, 'run', docker)
    monkeypatch.setattr(runtime, 'process_identity', lambda pid: 'start command' if pid == 123 else 'new unrelated process')
    signal = Mock()
    monkeypatch.setattr(runtime.os, 'killpg', signal)
    with pytest.raises(SystemExit, match='identity changed'):
        runtime.stop(tmp_path)
    signal.assert_not_called()
    assert (tmp_path / 'state.json').exists()
    assert docker.call_count == 1


def test_signals_only_matching_processes_and_skips_missing(tmp_path, monkeypatch):
    state(tmp_path, processes=[{'pid': 123, 'identity': 'start command'}, {'pid': 456, 'identity': 'gone'}])
    docker = Mock(return_value=SimpleNamespace(stdout='owned'))
    monkeypatch.setattr(runtime, 'run', docker)
    monkeypatch.setattr(runtime, 'process_identity', lambda pid: 'start command' if pid == 123 else None)
    signal = Mock()
    monkeypatch.setattr(runtime.os, 'killpg', signal)
    runtime.stop(tmp_path)
    signal.assert_called_once_with(123, runtime.signal.SIGTERM)
    assert docker.call_args.args[0] == ['docker', 'rm', '-f', 'owned-container']
    assert not tmp_path.exists()


def test_identity_captures_start_time_and_command_without_environment(monkeypatch):
    command = Mock(return_value=SimpleNamespace(returncode=0, stdout='Mon Nov 2 14:00:00 2026 /usr/bin/python worker'))
    monkeypatch.setattr(runtime.subprocess, 'run', command)
    assert runtime.process_identity(123) == 'Mon Nov 2 14:00:00 2026 /usr/bin/python worker'
    assert command.call_args.args[0] == ['ps', '-p', '123', '-o', 'lstart=', '-o', 'command=']
