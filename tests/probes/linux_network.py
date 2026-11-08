"""Native loopback connection attempts for the Linux namespace boundary test."""
import ctypes
import json
import socket
import struct
import sys


def native_network(port):
    libc = ctypes.CDLL(None, use_errno=True)
    address = ctypes.create_string_buffer(struct.pack('=H', socket.AF_INET)
                                         + struct.pack('!H', port) + socket.inet_aton('127.0.0.1') + bytes(8))
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


if __name__ == '__main__':
    if sys.platform != 'linux' or len(sys.argv) != 3 or sys.argv[1] != '--worker':
        raise SystemExit('Use on Linux as --worker PORT with a controlled local listener')
    print(json.dumps(native_network(int(sys.argv[2]))))
