import unittest
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sector_heatmap import authentication
from sector_heatmap.market_data import configure_websocket_ca_bundle, is_token_error


class AuthenticationConfigTests(unittest.TestCase):
    def test_missing_secret_has_actionable_error(self):
        config = {"FYERS_APP_ID": "APP-100", "FYERS_REDIRECT_URI": "http://127.0.0.1:8080/callback"}
        with patch.object(authentication, "load_config", return_value=config):
            with self.assertRaisesRegex(RuntimeError, "FYERS_SECRET_KEY.*environment or a supported private config file"):
                authentication.validated_config(expected_port=8080)

    def test_dashboard_port_must_match_registered_callback(self):
        config = {"FYERS_APP_ID": "APP-100", "FYERS_SECRET_KEY": "secret", "FYERS_REDIRECT_URI": "http://127.0.0.1:8080/callback"}
        with patch.object(authentication, "load_config", return_value=config):
            with self.assertRaisesRegex(RuntimeError, r"must match the dashboard port \(9090\)"):
                authentication.validated_config(expected_port=9090)

    def test_local_callback_is_accepted(self):
        config = {"FYERS_APP_ID": "APP-100", "FYERS_SECRET_KEY": "secret", "FYERS_REDIRECT_URI": "http://localhost:8080/callback"}
        with patch.object(authentication, "load_config", return_value=config):
            self.assertEqual(authentication.validated_config(expected_port=8080), config)

    def test_documented_fyers_expiry_codes_are_detected(self):
        for code in (-8, -15, -16, -17, 401):
            with self.subTest(code=code):
                self.assertTrue(is_token_error({"code": code, "message": "request failed"}))
        self.assertTrue(is_token_error("invalid access token"))
        self.assertFalse(is_token_error({"code": 200, "s": "ok"}))

    def test_existing_websocket_ca_bundle_is_respected(self):
        with TemporaryDirectory() as directory:
            bundle = Path(directory) / "custom.pem"
            bundle.write_text("private trust bundle", encoding="utf-8")
            with patch.dict(os.environ, {"WEBSOCKET_CLIENT_CA_BUNDLE": str(bundle)}, clear=False):
                self.assertEqual(configure_websocket_ca_bundle(), str(bundle))

    def test_missing_explicit_websocket_ca_bundle_fails_closed(self):
        with patch.dict(os.environ, {"WEBSOCKET_CLIENT_CA_BUNDLE": "/missing/ca.pem"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "does not exist"):
                configure_websocket_ca_bundle()

    def test_populated_system_store_is_preferred(self):
        class Context:
            def cert_store_stats(self):
                return {"x509_ca": 1}
        with patch.dict(os.environ, {}, clear=True), patch("sector_heatmap.market_data.ssl.create_default_context", return_value=Context()):
            self.assertEqual(configure_websocket_ca_bundle(), "system")
            self.assertNotIn("WEBSOCKET_CLIENT_CA_BUNDLE", os.environ)

    def test_certifi_fallback_is_configured_for_empty_system_store(self):
        class Context:
            def __init__(self, count):
                self.count = count
            def cert_store_stats(self):
                return {"x509_ca": self.count}
        with TemporaryDirectory() as directory:
            bundle = Path(directory) / "certifi.pem"
            bundle.write_text("public CA bundle", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch("sector_heatmap.market_data.ssl.create_default_context", side_effect=[Context(0), Context(1)]), patch("certifi.where", return_value=str(bundle)):
                self.assertEqual(configure_websocket_ca_bundle(), str(bundle))
                self.assertEqual(os.environ["WEBSOCKET_CLIENT_CA_BUNDLE"], str(bundle))


if __name__ == "__main__":
    unittest.main()
