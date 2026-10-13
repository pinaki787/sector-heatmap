"""Process-wide IPv4-only DNS policy for broker HTTP and WebSocket clients.

Installed before SDK imports. IPv6-only destinations fail closed; TLS names
and certificate verification remain unchanged. Child processes inherit this
policy through the project sitecustomize module on PYTHONPATH.
"""
import socket


def install_ipv4_only():
    """Install once, preserving the original resolver across repeated imports."""
    if getattr(socket.getaddrinfo, "_sector_pulse_ipv4_only", False):
        return
    resolver = socket.getaddrinfo

    def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if family not in (socket.AF_UNSPEC, socket.AF_INET):
            raise socket.gaierror(socket.EAI_FAMILY, "Sector Pulse requires IPv4")
        return resolver(host, port, socket.AF_INET, type, proto, flags)

    ipv4_getaddrinfo._sector_pulse_ipv4_only = True
    socket.getaddrinfo = ipv4_getaddrinfo
