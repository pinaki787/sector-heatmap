import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sector_heatmap import config


class ConfigTests(unittest.TestCase):
    def test_shared_token_cache_is_discovered_and_normalized(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            token_file = root / "token.json"
            token_file.write_text(json.dumps({"app_id": "APP-100", "access_token": "token-value"}), encoding="utf-8")
            with patch.object(config, "TOKEN_FILE", token_file), patch.object(config, "ENV_FILE", root / ".fyers.env"), patch.object(config, "_user_config_files", return_value=[]), patch.dict(os.environ, {"HEATMAP_PORT": "8765"}, clear=True):
                values = config.load_config()
            self.assertEqual(values["FYERS_APP_ID"], "APP-100")
            self.assertEqual(values["FYERS_ACCESS_TOKEN"], "APP-100:token-value")
            self.assertEqual(values["FYERS_REDIRECT_URI"], "http://127.0.0.1:8765/callback")

    def test_environment_aliases_override_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project_env = root / ".fyers.env"
            project_env.write_text("FYERS_APP_ID=file-app\nFYERS_SECRET_KEY=file-secret\n", encoding="utf-8")
            environment = {"FYERS_CLIENT_ID": "env-app", "FYERS_SECRET_ID": "env-secret", "FYERS_APP_ID": "", "FYERS_SECRET_KEY": ""}
            with patch.object(config, "TOKEN_FILE", root / "missing.json"), patch.object(config, "ENV_FILE", project_env), patch.object(config, "_user_config_files", return_value=[]), patch.dict(os.environ, environment, clear=True):
                values = config.load_config()
            self.assertEqual(values["FYERS_APP_ID"], "env-app")
            self.assertEqual(values["FYERS_SECRET_KEY"], "env-secret")

    def test_token_for_a_different_app_is_not_reused(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            token_file = root / "token.json"
            token_file.write_text(json.dumps({"app_id": "OLD-100", "access_token": "old-token"}), encoding="utf-8")
            with patch.object(config, "TOKEN_FILE", token_file), patch.object(config, "ENV_FILE", root / ".fyers.env"), patch.object(config, "_user_config_files", return_value=[]), patch.dict(os.environ, {"FYERS_CLIENT_ID": "NEW-100"}, clear=True):
                values = config.load_config()
            self.assertEqual(values["FYERS_APP_ID"], "NEW-100")
            self.assertNotIn("FYERS_ACCESS_TOKEN", values)

    def test_save_access_token_updates_private_shared_cache(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            token_file = root / "token.json"
            token_file.write_text(json.dumps({"refresh_token": "keep-me"}), encoding="utf-8")
            with patch.object(config, "TOKEN_FILE", token_file), patch.object(config, "ENV_FILE", root / ".fyers.env"), patch.object(config, "_user_config_files", return_value=[]), patch.dict(os.environ, {}, clear=True):
                config.save_access_token("APP-100:new-token")
            cached = json.loads(token_file.read_text(encoding="utf-8"))
            self.assertEqual(cached["app_id"], "APP-100")
            self.assertEqual(cached["access_token"], "new-token")
            self.assertEqual(cached["refresh_token"], "keep-me")
            if os.name != "nt":
                self.assertEqual(token_file.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
