import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from sector_heatmap.network_policy import install_ipv4_only


class IPv4PolicyTests(unittest.TestCase):
    def test_all_resolver_arguments_preserved_except_family(self):
        resolver = Mock(return_value=[(socket.AF_INET, 1, 6, "", ("127.0.0.1", 443))])
        resolver._sector_pulse_ipv4_only = False
        with patch.object(socket, "getaddrinfo", resolver):
            install_ipv4_only()
            first = socket.getaddrinfo
            install_ipv4_only()
            self.assertIs(first, socket.getaddrinfo)
            result = socket.getaddrinfo("broker.example", 443, type=socket.SOCK_STREAM,
                                        proto=socket.IPPROTO_TCP, flags=socket.AI_NUMERICHOST)
            resolver.assert_called_once_with("broker.example", 443, socket.AF_INET,
                                              socket.SOCK_STREAM, socket.IPPROTO_TCP,
                                              socket.AI_NUMERICHOST)
            self.assertEqual(result[0][0], socket.AF_INET)

    def test_explicit_ipv6_fails_without_resolving(self):
        resolver = Mock()
        resolver._sector_pulse_ipv4_only = False
        with patch.object(socket, "getaddrinfo", resolver):
            install_ipv4_only()
            with self.assertRaises(socket.gaierror):
                socket.getaddrinfo("broker.example", 443, socket.AF_INET6)
            resolver.assert_not_called()

    def test_ipv6_literal_fails_and_ipv4_loopback_works(self):
        with self.assertRaises(socket.gaierror):
            socket.getaddrinfo("::1", 443)
        self.assertTrue(all(r[0] == socket.AF_INET for r in socket.getaddrinfo("localhost", 443)))

    def test_standalone_child_inherits_policy_outside_project(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root))
        code = "import socket; assert getattr(socket.getaddrinfo, '_sector_pulse_ipv4_only', False); assert all(r[0] == socket.AF_INET for r in socket.getaddrinfo('localhost', 443))"
        subprocess.run([sys.executable, "-c", code], cwd="/tmp", env=env, check=True)
