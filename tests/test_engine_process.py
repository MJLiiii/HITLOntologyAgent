"""Disposable real processes exercise aggregate limits and cleanup, without engines or model calls."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux /proc process-tree probes')


def run(tmp_path, program, **limits):
    from oe_studio.engine_process import run_engine
    options = {'timeout': 3, 'max_rss_bytes': 128 * 1024 * 1024,
               'max_tasks': 32, 'max_output_bytes': 128 * 1024}
    options.update(limits)
    return run_engine([sys.executable, '-I', '-c', program], cwd=tmp_path,
                      env={'PATH': str(Path(sys.executable).parent)}, **options)


def assert_stopped(pid):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            state = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0]
        except FileNotFoundError:
            return
        if state == 'Z':  # The host init may defer collecting an orphan; it cannot execute.
            return
        time.sleep(0.01)
    os.kill(pid, signal.SIGKILL)
    pytest.fail(f'Worker descendant {pid} was still running after supervisor cleanup')


def test_small_result_retains_exit_status_and_both_output_streams(tmp_path):
    result = run(tmp_path, 'import sys; print("result"); print("diagnostic", file=sys.stderr); sys.exit(3)')
    assert (result.returncode, result.stdout, result.stderr) == (3, 'result\n', 'diagnostic\n')


def test_timeout_kills_descendant_that_started_another_session(tmp_path):
    child_file = tmp_path / 'child.pid'
    program = f'''import os, time
pid = os.fork()
if pid == 0:
    os.setsid()
    open({str(child_file)!r}, 'w').write(str(os.getpid()))
time.sleep(10)
'''
    with pytest.raises(subprocess.TimeoutExpired):
        run(tmp_path, program, timeout=0.4)
    assert_stopped(int(child_file.read_text()))


def test_cancellation_kills_and_reaps_launcher_and_stops_descendant(monkeypatch, tmp_path):
    import oe_studio.engine_process as supervisor
    child_file = tmp_path / 'child.pid'
    parent_file = tmp_path / 'parent.pid'
    original_sleep = time.sleep
    cancelled = False

    def cancel_when_child_exists(seconds):
        nonlocal cancelled
        if child_file.exists() and not cancelled:
            cancelled = True
            raise KeyboardInterrupt('controlled cancellation')
        original_sleep(seconds)

    program = f'''import os, time
open({str(parent_file)!r}, 'w').write(str(os.getpid()))
if os.fork() == 0:
    open({str(child_file)!r}, 'w').write(str(os.getpid()))
time.sleep(10)
'''
    with monkeypatch.context() as patch:
        patch.setattr(supervisor.time, 'sleep', cancel_when_child_exists)
        with pytest.raises(KeyboardInterrupt, match='controlled cancellation'):
            run(tmp_path, program)
    assert not Path(f'/proc/{parent_file.read_text()}').exists(), 'Direct child must be reaped'
    assert_stopped(int(child_file.read_text()))


@pytest.mark.parametrize('workload', [
    'children = [os.fork() for _ in range(2)]; time.sleep(5)',
    'threads = [threading.Thread(target=time.sleep, args=(5,), daemon=True) for _ in range(12)]; '
    '[thread.start() for thread in threads]; time.sleep(5)',
])
def test_task_limit_counts_child_processes_and_threads(tmp_path, workload):
    from oe_studio.engine_process import EngineResourceLimit
    with pytest.raises(EngineResourceLimit, match='task limit') as failure:
        run(tmp_path, 'import os, threading, time; ' + workload, max_tasks=3)
    assert failure.value.code == 'process_limit'


def test_rss_limit_sums_small_launcher_and_large_child(tmp_path):
    from oe_studio.engine_process import EngineResourceLimit
    child_file = tmp_path / 'child.pid'
    program = f'''import os, time
if os.fork() == 0:
    open({str(child_file)!r}, 'w').write(str(os.getpid()))
    memory = bytearray(80 * 1024 * 1024)
time.sleep(5)
'''
    with pytest.raises(EngineResourceLimit, match='resident-memory limit') as failure:
        run(tmp_path, program, max_rss_bytes=48 * 1024 * 1024)
    assert failure.value.code == 'memory_limit'
    assert_stopped(int(child_file.read_text()))


@pytest.mark.parametrize('program', [
    'import os; os.write(1, b"x" * 9000); os.write(2, b"y" * 9000)',
    'from pathlib import Path; Path("report.json").write_bytes(b"x" * 18000)',
])
def test_output_limit_includes_combined_streams_and_report_files(tmp_path, program):
    from oe_studio.engine_process import EngineResourceLimit
    with pytest.raises(EngineResourceLimit, match='output limit') as failure:
        run(tmp_path, program, max_output_bytes=16000, output_paths=[tmp_path / 'report.json'])
    assert failure.value.code == 'output_limit'


def test_normal_launcher_exit_still_stops_leftover_group_members(tmp_path):
    child_file = tmp_path / 'child.pid'
    program = f'''import os, time
if os.fork() == 0:
    open({str(child_file)!r}, 'w').write(str(os.getpid()))
    time.sleep(10)
else:
    time.sleep(0.1)
'''
    assert run(tmp_path, program).returncode == 0
    assert_stopped(int(child_file.read_text()))


def test_macos_thread_rows_count_memory_once_per_process(monkeypatch):
    """Darwin ps -M adds default columns, even when custom -o fields are supplied."""
    import oe_studio.engine_process as supervisor
    monkeypatch.setattr(supervisor.sys, 'platform', 'darwin')
    sample = ('                  USER TT %CPU STAT PRI STIME UTIME COMMAND\n'
              '100 1 100 4096 user ?? 0.0 S 31 0:00 0:00 worker\n'
              '100 1 100 4096          0.0 S 31 0:00 0:00\n'
              '101 100 100 2048 user ?? 0.0 S 31 0:00 0:00 child\n')
    def sample_processes(command, **kwargs):
        assert command.index('-M') > command.index('-axo'), 'Numeric columns must precede -M defaults'
        return subprocess.CompletedProcess(command, 0, stdout=sample)

    monkeypatch.setattr(supervisor.subprocess, 'run', sample_processes)
    members = supervisor._members(100, supervisor._process_table(), {})
    assert sum(row.rss for row in members.values()) == 6 * 1024 * 1024
    assert sum(row.tasks for row in members.values()) == 3


def test_bubblewrap_timeout_stops_worker_in_nested_session(tmp_path):
    from oe_studio.engine_isolation import isolated_command, python_runtime_paths
    from oe_studio.engine_process import run_engine
    marker = tmp_path / 'nested-session-started'
    program = f'''import os, time
if os.fork() == 0:
    os.setsid()
    open({str(marker)!r}, 'w').write('started')
time.sleep(10)
'''
    command, _ = isolated_command([sys.executable, '-I', '-c', program], workdir=tmp_path,
                                  readable=python_runtime_paths(sys.executable))
    with pytest.raises(subprocess.TimeoutExpired):
        run_engine(command, cwd=tmp_path, env={}, timeout=0.4,
                   max_rss_bytes=128 * 1024 * 1024, max_tasks=32, max_output_bytes=128 * 1024)
    assert marker.read_text() == 'started'
    # Namespace PIDs cannot identify host processes. The unique path in argv can.
    leftovers = []
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            try:
                if str(marker).encode() in (entry / 'cmdline').read_bytes():
                    leftovers.append(int(entry.name))
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
    for pid in leftovers:
        assert_stopped(pid)
