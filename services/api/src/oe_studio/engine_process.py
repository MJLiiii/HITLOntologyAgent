"""File-backed engine supervision with aggregate process-tree watchdog limits.

RSS, task counts and output are sampled, not instantaneous kernel quotas. Linux
isolation additionally owns a PID namespace: killing its launcher stops even a
descendant that changes session between samples. Do not use this as a sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

POLL_SECONDS = 0.05
ENFORCEMENT = ('Parent watchdog samples aggregate process-tree RSS, tasks (including threads), '
               'and output at approximately 50 ms intervals; not instantaneous kernel quotas.')


class EngineResourceLimit(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _Process:
    parent: int
    group: int
    rss: int
    tasks: int
    identity: int = 0


def _process_table() -> dict[int, _Process]:
    if sys.platform == 'linux':
        table = {}
        page_bytes = os.sysconf('SC_PAGE_SIZE')
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():
                continue
            try:
                # The comm field can itself contain spaces or closing parentheses.
                fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
                table[int(entry.name)] = _Process(
                    int(fields[1]), int(fields[2]), max(0, int(fields[21])) * page_bytes,
                    int(fields[17]), int(fields[19]),
                )
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue  # Processes may exit during the snapshot.
        return table
    if sys.platform == 'darwin':
        # Put numeric fields first: -M also appends its default headed columns.
        # It emits each thread, so RSS is retained once per process, not per row.
        sample = subprocess.run(['/bin/ps', '-axo', 'pid=,ppid=,pgid=,rss=', '-M'],
                                capture_output=True, text=True, timeout=1, check=True,
                                env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
        table = {}
        for row in sample.stdout.splitlines()[1:]:
            pid, parent, group, rss = map(int, row.split(maxsplit=4)[:4])
            previous = table.get(pid)
            table[pid] = _Process(parent, group, rss * 1024, 1 + (previous.tasks if previous else 0))
        return table
    raise RuntimeError('Cannot verify engine process-tree resource use on this platform')


def _members(root: int, table: dict[int, _Process], known: dict[int, int]) -> dict[int, _Process]:
    selected = {pid for pid, row in table.items()
                if pid == root or row.group == root or known.get(pid) == row.identity}
    while True:
        children = {pid for pid, row in table.items() if row.parent in selected}
        if children <= selected:
            break
        selected.update(children)
    return {pid: table[pid] for pid in selected}


def _stop(process: subprocess.Popen, known: dict[int, int]) -> None:
    try:
        members = _members(process.pid, _process_table(), known)
        # Kill tracked descendants that changed group before killing the launcher.
        for pid in members:
            if pid != process.pid:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        finally:
            process.wait(timeout=2)


def run_engine(command: list[str], *, cwd: Path, env: dict[str, str], timeout: float,
               max_rss_bytes: int, max_tasks: int, max_output_bytes: int,
               output_paths: list[Path] | tuple[Path, ...] = ()) -> subprocess.CompletedProcess:
    """Run an already-confined command; always stop its group and reap the child.

    Stdout and stderr never accumulate in pipes or unbounded Python strings.
    Output limits include both streams and the caller's declared report artifacts,
    including files produced just before process exit. Cancellation propagates
    only after cleanup; resource failures never return a partial success.
    """
    started = time.monotonic()
    with tempfile.TemporaryFile(dir=cwd) as stdout, tempfile.TemporaryFile(dir=cwd) as stderr:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr, start_new_session=True)
        known = {}

        def check_output():
            total = os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size
            for path in output_paths:
                try:
                    total += path.stat().st_size
                except FileNotFoundError:
                    continue
            if total > max_output_bytes:
                raise EngineResourceLimit('output_limit', 'Engine exceeded its aggregate output limit')

        try:
            while True:
                if time.monotonic() - started > timeout:
                    raise subprocess.TimeoutExpired(command, timeout)
                members = _members(process.pid, _process_table(), known)
                known.update({pid: row.identity for pid, row in members.items()})
                if sum(row.rss for row in members.values()) > max_rss_bytes:
                    raise EngineResourceLimit('memory_limit', 'Engine exceeded its aggregate resident-memory limit')
                if sum(row.tasks for row in members.values()) > max_tasks:
                    raise EngineResourceLimit('process_limit', 'Engine exceeded its process/thread task limit')
                check_output()
                if process.poll() is not None:
                    break
                if process.pid not in members:
                    raise RuntimeError('Cannot verify engine process-tree resource use; execution is blocked')
                time.sleep(POLL_SECONDS)
        finally:
            _stop(process, known)
        check_output()
        stdout.seek(0)
        stderr.seek(0)
        output, errors = stdout.read(max_output_bytes + 1), stderr.read(max_output_bytes + 1)
        if len(output) + len(errors) > max_output_bytes:
            raise EngineResourceLimit('output_limit', 'Engine exceeded its aggregate output limit')
        return subprocess.CompletedProcess(command, process.returncode,
                                           output.decode('utf-8', errors='replace'),
                                           errors.decode('utf-8', errors='replace'))
