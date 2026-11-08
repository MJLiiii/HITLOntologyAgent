"""Real OS boundary checks; run outside an enclosing desktop sandbox."""
import json
from pathlib import Path
import socket
import subprocess
import sys

import pytest


def test_unknown_isolation_configuration_fails_closed(monkeypatch, tmp_path):
    from oe_studio.engine_isolation import isolated_command
    monkeypatch.setenv('OE_ENGINE_ISOLATION', 'off')
    with pytest.raises(ValueError, match='Unsupported engine isolation'):
        isolated_command([sys.executable, '-V'], workdir=tmp_path, readable=[])


def test_kernel_boundary_confines_reads_writes_and_symlink_targets(tmp_path):
    from oe_studio.engine_isolation import isolated_command, python_runtime_paths
    work = tmp_path / 'run'
    work.mkdir()
    source = work / 'input.txt'
    source.write_text('declared input')
    library = tmp_path / 'read-only-library.txt'
    library.write_text('runtime dependency')
    forbidden = []
    for name in ('.data/approved-store', 'home/.ssh/private-key', 'home/.aws/credentials'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('private canary')
        forbidden.append(str(path))
        data_volume_alias = Path('/System/Volumes/Data' + str(path))
        if data_volume_alias.exists():
            forbidden.append(str(data_volume_alias))
    (work / 'escape-link').symlink_to(forbidden[0])
    script = work / 'probe.py'
    script.write_text('''import errno, json, os, pathlib, sys
denied = {errno.EPERM, errno.EACCES, errno.ENOENT, errno.EROFS, errno.EXDEV}
work = pathlib.Path(sys.argv[1])
assert (work / 'input.txt').read_text() == 'declared input'
library = pathlib.Path(sys.argv[3])
assert library.read_text() == 'runtime dependency'
try:
    library.write_text('overwrite dependency')
except OSError as error:
    assert error.errno in denied, error
else:
    raise AssertionError('Sandbox allowed a runtime dependency overwrite')
(work / 'result.txt').write_text('allowed result')
for value in json.loads(sys.argv[2]) + [str(work / 'escape-link')]:
    path = pathlib.Path(value)
    for action in (path.read_text, lambda: path.write_text('overwrite')):
        try:
            action()
        except OSError as error:
            assert error.errno in denied, error
            continue
        raise AssertionError('Sandbox allowed access to ' + value)
try:
    (work.parent / 'escape-write').write_text('outside')
except OSError as error:
    assert error.errno in denied, error
else:
    raise AssertionError('Sandbox allowed an outside write')
try:
    os.link(json.loads(sys.argv[2])[0], work / 'hardlink-escape')
    (work / 'hardlink-escape').read_text()
except OSError as error:
    assert error.errno in denied, error
else:
    raise AssertionError('Sandbox allowed an outside read through a hard link')
print(json.dumps({'status': 'verified'}))
''')
    command, isolation = isolated_command(
        [sys.executable, '-I', str(script), str(work), json.dumps(forbidden), str(library)],
        workdir=work, readable=[library, *python_runtime_paths(sys.executable)],
    )
    result = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'verified'
    assert isolation['network'] == 'kernel-denied'
    assert isolation['filesystem'] == 'runtime-and-declared-inputs-read; run-directory-write'
    assert (work / 'result.txt').read_text() == 'allowed result'
    assert all(Path(value).read_text() == 'private canary' for value in forbidden)


def test_kernel_network_denial_survives_native_calls_and_descendants(tmp_path):
    import errno
    from oe_studio.engine_isolation import isolated_command, python_runtime_paths
    probe = Path(__file__).with_name('probes') / ('linux_network.py' if sys.platform == 'linux' else 'macos_network.py')
    with socket.socket() as tcp, socket.socket(type=socket.SOCK_DGRAM) as udp:
        tcp.bind(('127.0.0.1', 0))
        tcp.listen(4)
        port = tcp.getsockname()[1]
        udp.bind(('127.0.0.1', port))
        worker = [sys.executable, '-I', str(probe), '--worker', str(port)]
        baseline = subprocess.run(worker, capture_output=True, text=True, timeout=10, check=True)
        assert all(item['errno'] == 0 for item in json.loads(baseline.stdout).values())
        tcp.settimeout(0.2)
        udp.settimeout(0.2)
        connection, _ = tcp.accept()
        connection.close()
        assert udp.recvfrom(1)[0] == b'x'
        for args in (worker, [sys.executable, '-I', '-c',
                             'import subprocess,sys; subprocess.run(sys.argv[1:], check=True)', *worker]):
            command, _ = isolated_command(args, workdir=tmp_path,
                                          readable=[probe, *python_runtime_paths(sys.executable)])
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, result.stderr
            results = json.loads(result.stdout)
            assert results['tcp_connect']['errno'] in (errno.EPERM, errno.EACCES, errno.ENETUNREACH, errno.ECONNREFUSED)
            if sys.platform == 'darwin':
                assert results['udp_sendto']['errno'] in (errno.EPERM, errno.EACCES)
            # Linux UDP can send to sandbox-local loopback, but cannot reach the host listener.
            with pytest.raises(TimeoutError):
                udp.recvfrom(1)
            with pytest.raises(TimeoutError):
                tcp.accept()


def test_missing_sandbox_launcher_never_becomes_unconfined_worker(monkeypatch, tmp_path):
    import oe_studio.engine_isolation as isolation
    monkeypatch.setattr(isolation, 'BWRAP' if sys.platform == 'linux' else 'SANDBOX_EXEC', tmp_path / 'absent')
    with pytest.raises(FileNotFoundError):
        isolation.isolated_command([sys.executable, '-V'], workdir=tmp_path, readable=[])


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux mount/environment policy')
def test_linux_root_readonly_and_environment_private(monkeypatch, tmp_path):
    from oe_studio.engine_isolation import isolated_command, python_runtime_paths
    monkeypatch.setenv('STUDIO_TEST_SECRET', 'must-not-enter-engine')
    script = '''import errno, os, pathlib
assert 'STUDIO_TEST_SECRET' not in os.environ
try:
    pathlib.Path('/outside-scratch').write_text('escape')
except OSError as error:
    assert error.errno in {errno.EROFS, errno.EACCES, errno.EPERM}
else:
    raise AssertionError('Writable sandbox root')
print('confined')
'''
    command, _ = isolated_command([sys.executable, '-I', '-c', script], workdir=tmp_path,
                                 readable=python_runtime_paths(sys.executable))
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'confined'
