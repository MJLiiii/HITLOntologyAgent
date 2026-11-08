"""Fail-closed local engine confinement; no sandbox failure invokes a plain process."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
PROFILE = ROOT / 'config/macos-engine.sb'
SANDBOX_EXEC = Path('/usr/bin/sandbox-exec')
BWRAP = Path('/usr/bin/bwrap')


def isolation_configuration() -> dict:
    default = {'darwin': 'macos-seatbelt', 'linux': 'linux-bubblewrap'}.get(sys.platform, 'unsupported')
    mode = os.getenv('OE_ENGINE_ISOLATION', default)
    if mode == 'linux-bubblewrap':
        return {'mode': mode, 'platform': sys.platform, 'launcher': str(BWRAP),
                'profile_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'launcher_sha256': hashlib.sha256(BWRAP.read_bytes()).hexdigest() if BWRAP.is_file() else 'unavailable'}
    return {'mode': mode,
            'profile_sha256': hashlib.sha256(PROFILE.read_bytes()).hexdigest(),
            'launcher': str(SANDBOX_EXEC), 'platform': sys.platform}


def python_runtime_paths(executable: str) -> list[Path]:
    """Read only this interpreter's installation and virtual environment, never its project."""
    executable = Path(executable).absolute()
    paths = [executable.resolve().parent.parent]
    environment = executable.parent.parent
    if (environment / 'pyvenv.cfg').is_file():
        paths.append(environment)
    return paths


def isolated_command(command: list[str], *, workdir: Path, readable: list[Path]) -> tuple[list[str], dict]:
    config = isolation_configuration()
    if config['mode'] == 'linux-bubblewrap' and sys.platform == 'linux':
        return _linux_command(command, workdir, readable, config)
    if config['mode'] != 'macos-seatbelt' or sys.platform != 'darwin':
        raise ValueError('Unsupported engine isolation configuration; a verified macOS Seatbelt launcher is required')
    if not SANDBOX_EXEC.is_file():
        raise FileNotFoundError('macOS sandbox-exec is missing; engine execution is blocked')
    directory = workdir.resolve(strict=True)
    rules = []
    for path in sorted({directory, *(Path(value).resolve(strict=True) for value in readable)}):
        value = str(path)
        if any(ord(character) < 32 for character in value):
            raise ValueError('Engine runtime paths cannot contain control characters')
        kind = 'subpath' if path.is_dir() else 'literal'
        rules.append(f'({kind} {json.dumps(value, ensure_ascii=False)})')
    profile = PROFILE.read_text().replace('__RUNTIME_READ_RULES__', '(allow file-read* ' + ' '.join(rules) + ')')
    rendered = directory / 'engine-sandbox.sb'
    rendered.write_text(profile)
    metadata = {**config, 'network': 'kernel-denied',
                'filesystem': 'runtime-and-declared-inputs-read; run-directory-write',
                'rendered_profile_sha256': hashlib.sha256(profile.encode()).hexdigest(),
                'limitations': 'Deprecated macOS launcher; system resources, file metadata and IPC remain accessible. '
                               'No protection against a malicious operator who owns the server or its runtime.'}
    return [str(SANDBOX_EXEC), '-D', f'WORKDIR={directory}', '-f', str(rendered), *command], metadata


def _linux_command(command, workdir, readable, config):
    if not BWRAP.is_file():
        raise FileNotFoundError('Bubblewrap is missing; engine execution is blocked')
    directory = workdir.resolve(strict=True)
    inputs = sorted({Path(value).resolve(strict=True) for value in readable})
    for path in [directory, *inputs]:
        if path == Path('/') or any(ord(character) < 32 for character in str(path)):
            raise ValueError('Engine paths must be bounded and cannot contain control characters')
    args = [str(BWRAP), '--unshare-all', '--unshare-user', '--disable-userns',
            '--assert-userns-disabled', '--die-with-parent', '--new-session', '--cap-drop', 'ALL',
            '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8',
            '--setenv', 'HOME', str(directory), '--setenv', 'TMPDIR', str(directory)]
    # An empty root exposes only system libraries and declared inputs, never /home or /etc wholesale.
    for value in ('/usr/lib', '/usr/lib64', '/usr/share/locale', '/usr/share/zoneinfo',
                  '/etc/ld.so.cache', '/etc/localtime'):
        if Path(value).exists():
            args.extend(['--ro-bind', value, value])
    for value in ('lib', 'lib64', 'bin', 'sbin'):
        if Path('/' + value).is_symlink():
            args.extend(['--symlink', os.readlink('/' + value), '/' + value])
    args.extend(['--proc', '/proc', '--dev', '/dev'])
    for path in inputs:
        args.extend(['--ro-bind', str(path), str(path)])
    args.extend(['--bind', str(directory), str(directory), '--chdir', str(directory), '--remount-ro', '/'])
    metadata = {**config, 'network': 'kernel-denied',
                'filesystem': 'runtime-and-declared-inputs-read; run-directory-write',
                'rendered_profile_sha256': hashlib.sha256(json.dumps(args).encode()).hexdigest(),
                'limitations': 'System libraries and sandbox-local proc/dev/loopback are accessible; '
                               'host and external networking are isolated. '
                               'No protection against a malicious operator who owns the server or its runtime.'}
    return [*args, '--', *command], metadata
