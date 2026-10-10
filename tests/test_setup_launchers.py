import unittest
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATES = (
    "SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS",
    "SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS",
    "SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS",
)


class SetupLauncherTests(unittest.TestCase):
    def test_posix_setup_repairs_copied_environment_and_reuses_it(self):
        python312 = shutil.which("python3.12")
        if not python312:
            self.skipTest("Python 3.12 is needed for the installer integration check")
        source = (ROOT / "setup_and_run.sh").read_text(encoding="utf-8")
        # Exercise the real environment bootstrap without downloading UI packages.
        bootstrap = source.split("npm_cache_dir=", 1)[0]
        with tempfile.TemporaryDirectory(prefix="heatmap setup ") as folder:
            root = Path(folder)
            (root / "setup_and_run.sh").write_text(bootstrap)
            (root / "requirements.lock").write_text("")
            old = root / ".venv"
            (old / "bin").mkdir(parents=True)
            (old / "bin/python").symlink_to("/missing/mac/python3.13")
            (old / "copied-marker").write_text("preserve me")
            commands = root / "test-bin"
            commands.mkdir()
            for name in ("node", "npx"):
                executable = commands / name
                executable.write_text("#!/bin/sh\nexit 0\n")
                executable.chmod(0o755)
            env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"],
                       PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
            def run_setup():
                result = subprocess.run(["sh", str(root / "setup_and_run.sh")],
                                        env=env, capture_output=True, text=True, timeout=90)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            run_setup()
            backups = list((root / ".private").glob("venv-backup.*/venv"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "copied-marker").read_text(), "preserve me")
            version = subprocess.check_output([str(old / "bin/python"), "-c",
                                               "import sys; print(sys.version_info[:2])"], text=True)
            self.assertEqual(version.strip(), "(3, 12)")
            created = (old / "pyvenv.cfg").stat().st_mtime_ns
            run_setup()
            self.assertEqual((old / "pyvenv.cfg").stat().st_mtime_ns, created)
            self.assertEqual(list((root / ".private").glob("venv-backup.*/venv")), backups)

    def test_runtime_template_is_fail_closed(self):
        template = (ROOT / ".env.example").read_text(encoding="utf-8")
        for gate in GATES:
            self.assertIn(f"{gate}=0", template)

    def test_all_launchers_load_and_validate_the_same_live_gates(self):
        for filename in ("setup_and_run.sh", "run_live_heatmap.sh", "setup_and_run.bat", "run_live_heatmap.bat"):
            source = (ROOT / filename).read_text(encoding="utf-8")
            with self.subTest(filename=filename):
                self.assertIn(".env", source)
                self.assertIn("Live-order switches must each be 0 or 1.", source)
                for gate in GATES:
                    self.assertIn(gate, source)


if __name__ == "__main__":
    unittest.main()
