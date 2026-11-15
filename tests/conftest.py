import socket

import pytest

LOCAL = ("127.0.0.1", "::1", "localhost")


@pytest.fixture(autouse=True)
def no_network(monkeypatch, request):
    """Hard rule H06: a unit test never touches the network.
    A test marked `integration` may reach this machine (127.0.0.1) and nothing else."""
    allow_local = request.node.get_closest_marker("integration") is not None
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def host_of(address):
        return address[0] if isinstance(address, tuple) else address

    def guarded_connect(self, address, *args, **kwargs):
        if allow_local and host_of(address) in LOCAL:
            return real_connect(self, address, *args, **kwargs)
        raise RuntimeError(f"network call blocked in a unit test: {address}")

    def guarded_getaddrinfo(host, *args, **kwargs):
        if allow_local and host in LOCAL:
            return real_getaddrinfo(host, *args, **kwargs)
        raise RuntimeError(f"name lookup blocked in a unit test: {host}")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
