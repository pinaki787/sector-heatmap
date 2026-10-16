import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('configure_server', ROOT / 'scripts/configure_server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class ServerInstallationTests(unittest.TestCase):
    def test_domain_validation_rejects_config_injection(self):
        for value in ('https://example.com', 'example.com:443', 'example.com\nListen 1234', 'a..example.com', '*.example.com'):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                server.domain_name(value)
        self.assertEqual(server.domain_name('Trading.Example.com.'), 'trading.example.com')

    def test_managed_writes_preserve_previous_config_and_are_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / 'trading.conf'
            config.write_text('previous')
            self.assertTrue(server.write_managed(config, 'new', backups=root / 'backups'))
            self.assertEqual(next((root / 'backups').iterdir()).read_text(), 'previous')
            timestamp = config.stat().st_mtime_ns
            self.assertFalse(server.write_managed(config, 'new', backups=root / 'backups'))
            self.assertEqual(config.stat().st_mtime_ns, timestamp)
            symlink = root / 'linked.conf'
            symlink.symlink_to(config)
            with self.assertRaises(RuntimeError):
                server.write_managed(symlink, 'bad', backups=root / 'backups')
            self.assertEqual(config.read_text(), 'new')

    def test_native_setup_preserves_existing_admin_and_credentials(self):
        with patch.object(server, 'run') as run:
            server.native_login('desktop', 'trading.example.com')
            code = run.call_args.args[-2]
        compile(code, '<native-bootstrap>', 'exec')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / '.fyers.env'
            config.write_text('FYERS_APP_ID=fake-test-app\n')
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            command = [sys.executable, '-c', code, 'trading.example.com']
            subprocess.run(command, cwd=root, env=env, check=True, capture_output=True)
            private = root / '.private'
            credentials = private / 'initial-dashboard-login.txt'
            initial = credentials.read_bytes()
            self.assertEqual(json.loads((private / 'server-settings.json').read_text()),
                             {'public_origin': 'https://trading.example.com'})
            subprocess.run(command, cwd=root, env=env, check=True, capture_output=True)
            self.assertEqual(credentials.read_bytes(), initial)
            self.assertEqual(config.read_text(), 'FYERS_APP_ID=fake-test-app\n')
            self.assertEqual(credentials.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
