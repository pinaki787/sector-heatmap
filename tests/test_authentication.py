import unittest
from unittest.mock import patch

from sector_heatmap import authentication
from sector_heatmap.market_data import is_token_error


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


if __name__ == "__main__":
    unittest.main()
