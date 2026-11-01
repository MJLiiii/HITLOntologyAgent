"""Operator probe of macOS Seatbelt network denial, independent of Python audit hooks.

Run from a normal macOS shell: .venv/bin/python tests/probes/macos_network.py
No external address is contacted. This does not install or configure engine isolation.
"""
from __future__ import annotations

import ctypes
import errno
import json
from pathlib import Path
import socket
import subprocess
import sys

PROFILE = '(version 1)(allow default)(deny network*)'


def native_network(port):
    libc = ctypes.CDLL(None, use_errno=True)
    address = (ctypes.c_ubyte * 16)(16, socket.AF_INET, port >> 8, port & 255, 127, 0, 0, 1)
    results = {}
    for name, kind in [('tcp_connect', socket.SOCK_STREAM), ('udp_sendto', socket.SOCK_DGRAM)]:
        fd = libc.socket(socket.AF_INET, kind, 0)
        if fd < 0:
            results[name] = {'operation': 'socket', 'errno': ctypes.get_errno()}
            continue
        ctypes.set_errno(0)
        if kind == socket.SOCK_STREAM:
            result = libc.connect(fd, ctypes.byref(address), 16)
        else:
            result = libc.sendto(fd, b'x', 1, 0, ctypes.byref(address), 16)
        results[name] = {'result': result, 'errno': ctypes.get_errno() if result < 0 else 0}
        libc.close(fd)
    return results


def main():
    if sys.platform != 'darwin':
        raise SystemExit('This probe requires macOS; no skipped-success result is emitted.')
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        print(json.dumps(native_network(int(sys.argv[2]))))
        return
    with socket.socket() as tcp, socket.socket(type=socket.SOCK_DGRAM) as udp:
        tcp.bind(('127.0.0.1', 0))
        tcp.listen(4)
        port = tcp.getsockname()[1]
        udp.bind(('127.0.0.1', port))
        worker = [sys.executable, '-I', str(Path(__file__).resolve()), '--worker', str(port)]
        outputs = {}
        # The shell variant proves a launched descendant retains the restriction.
        commands = {'baseline': worker,
                    'seatbelt': ['/usr/bin/sandbox-exec', '-p', PROFILE, *worker],
                    'descendant': ['/usr/bin/sandbox-exec', '-p', PROFILE,
                                   '/bin/sh', '-c', '"$@"', 'sh', *worker]}
        for label, command in commands.items():
            result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=True)
            outputs[label] = json.loads(result.stdout)
        assert all(value['errno'] == 0 for value in outputs['baseline'].values()), outputs
        for label in ('seatbelt', 'descendant'):
            assert all(value['errno'] in (errno.EPERM, errno.EACCES)
                       for value in outputs[label].values()), outputs
        print(json.dumps({'status': 'verified', 'profile': PROFILE, 'results': outputs}, indent=2))


if __name__ == '__main__':
    main()
