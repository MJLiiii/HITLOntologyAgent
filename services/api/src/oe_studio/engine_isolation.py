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


def isolation_configuration() -> dict:
    return {'mode': os.getenv('OE_ENGINE_ISOLATION', 'macos-seatbelt' if sys.platform == 'darwin' else 'unsupported'),
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
