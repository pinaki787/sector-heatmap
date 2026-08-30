from pathlib import Path
import json
import os
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".fyers.env"
TOKEN_FILE = Path(os.getenv("FYERS_TOKEN_FILE", Path.home() / ".fyers" / "token.json")).expanduser()

def _read_env_file(path):
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values

def _normalize_aliases(values):
    normalized = dict(values)
    if not normalized.get("FYERS_APP_ID") and normalized.get("FYERS_CLIENT_ID"):
        normalized["FYERS_APP_ID"] = normalized["FYERS_CLIENT_ID"]
    if not normalized.get("FYERS_SECRET_KEY") and normalized.get("FYERS_SECRET_ID"):
        normalized["FYERS_SECRET_KEY"] = normalized["FYERS_SECRET_ID"]
    return normalized

def _user_config_files():
    candidates = []
    if os.getenv("FYERS_CONFIG_FILE"):
        candidates.append(Path(os.environ["FYERS_CONFIG_FILE"]).expanduser())
    if os.getenv("APPDATA"):
        candidates.append(Path(os.environ["APPDATA"]) / "sector-heatmap" / "fyers.env")
    if os.getenv("XDG_CONFIG_HOME"):
        candidates.append(Path(os.environ["XDG_CONFIG_HOME"]) / "sector-heatmap" / "fyers.env")
    candidates.extend([
        Path.home() / ".config" / "sector-heatmap" / "fyers.env",
        Path.home() / "Library" / "Application Support" / "sector-heatmap" / "fyers.env",
    ])
    return list(dict.fromkeys(candidates))

def _read_token_cache():
    if not TOKEN_FILE.exists():
        return {}
    try:
        cached = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    app_id = cached.get("app_id") or cached.get("client_id")
    access_token = cached.get("access_token") or cached.get("token")
    values = {}
    if app_id:
        values["FYERS_APP_ID"] = str(app_id)
    if access_token:
        access_token = str(access_token)
        values["FYERS_ACCESS_TOKEN"] = access_token if ":" in access_token else f"{app_id}:{access_token}" if app_id else access_token
    if cached.get("refresh_token"):
        values["FYERS_REFRESH_TOKEN"] = str(cached["refresh_token"])
    return values

def load_config():
    values = _read_token_cache()
    for path in reversed(_user_config_files()):
        values.update(_normalize_aliases(_read_env_file(path)))
    values.update(_normalize_aliases(_read_env_file(ENV_FILE)))
    environment = {key: value for key, value in os.environ.items() if key.startswith("FYERS_")}
    values.update(_normalize_aliases(environment))
    values.setdefault("FYERS_REDIRECT_URI", f"http://127.0.0.1:{os.getenv('HEATMAP_PORT', '8080')}/callback")
    cached_token = values.get("FYERS_ACCESS_TOKEN", "")
    if ":" in cached_token and values.get("FYERS_APP_ID") and cached_token.split(":", 1)[0] != values["FYERS_APP_ID"]:
        values.pop("FYERS_ACCESS_TOKEN")
    return values

def _atomic_private_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
            handle.write(content)
            temporary_path = Path(handle.name)
        try:
            temporary_path.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary_path, path)
        try:
            path.chmod(0o600)
        except OSError:
            # Windows ACLs, rather than POSIX modes, control access on many systems.
            pass
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()

def save_access_token(token):
    values = load_config()
    values["FYERS_ACCESS_TOKEN"] = token
    app_id, access_token = token.split(":", 1) if ":" in token else (values.get("FYERS_APP_ID", ""), token)
    cached = {}
    try:
        if TOKEN_FILE.exists():
            cached = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cached = {}
    cached.update({"app_id": app_id, "access_token": access_token, "created_at": int(time.time())})
    _atomic_private_write(TOKEN_FILE, json.dumps(cached, indent=2) + "\n")
    if ENV_FILE.exists():
        ordered = ("FYERS_APP_ID", "FYERS_SECRET_KEY", "FYERS_REDIRECT_URI", "FYERS_ACCESS_TOKEN")
        lines = [f"{key}={values[key]}" for key in ordered if values.get(key)]
        _atomic_private_write(ENV_FILE, "\n".join(lines) + "\n")
