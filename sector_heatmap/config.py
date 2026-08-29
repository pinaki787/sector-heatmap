from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".fyers.env"

def load_config():
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    values.update({key: value for key, value in os.environ.items() if key.startswith("FYERS_")})
    return values

def save_access_token(token):
    values = load_config()
    values["FYERS_ACCESS_TOKEN"] = token
    ordered = ("FYERS_APP_ID", "FYERS_SECRET_KEY", "FYERS_REDIRECT_URI", "FYERS_ACCESS_TOKEN")
    lines = [f"{key}={values[key]}" for key in ordered if values.get(key)]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
