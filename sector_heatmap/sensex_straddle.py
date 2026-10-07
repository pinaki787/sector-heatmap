"""Guarded process bridge for the external SENSEX long-straddle runner."""

from collections import deque
from datetime import datetime
import ast
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock, Thread


DEFAULT_SCRIPT_PATH = Path("/Users/pinaki/trading/SENSEX/sensex_straddle.py")


class SensexStraddleService:
    """Inspect and control one dry-run process without granting live authority."""

    CONFIG_NAMES = {
        "LOT_SIZE", "NUM_LOTS", "DAILY_COOLDOWN", "VOL_PERCENTILE",
        "SUPER_TREND_PERIOD", "SUPER_TREND_MULTIPLIER",
        "SUPER_TREND_ACTIVATION_POINTS", "EOD_SQUARE_OFF_TIME",
        "STOPLOSS_POINTS", "ENTRY_WINDOW_START_TIME", "ENTRY_WINDOW_END_TIME",
        "MAX_REENTRIES_PER_DAY",
    }

    def __init__(self, script_path=None, credential_provider=None, process_factory=None, runtime_dir=None):
        configured = script_path or os.getenv("SECTOR_PULSE_SENSEX_STRADDLE_SCRIPT")
        self.script_path = Path(configured or DEFAULT_SCRIPT_PATH).expanduser().resolve()
        self.credential_provider = credential_provider or (lambda: "")
        self.process_factory = process_factory or subprocess.Popen
        self.runtime_dir = Path(runtime_dir or self.script_path.parent).expanduser().resolve()
        self.process = None
        self.started_at = None
        self.active_mode = None
        self.active_exit_mode = None
        self.active_lots = None
        self.active_entry_start = None
        self.active_entry_end = None
        self.last_exit_code = None
        self.output = deque(maxlen=80)
        self.lock = Lock()

    @property
    def state_path(self):
        return self.runtime_dir / "live_position_state.json"

    @property
    def trades_path(self):
        return self.runtime_dir / "live_trade_log.csv"

    @property
    def chart_path(self):
        return self.runtime_dir / "live_premium_chart.json"

    def _read_json(self, path):
        try:
            with path.open(encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else None
        except (FileNotFoundError, OSError, ValueError):
            return None

    def _read_config(self):
        if not self.script_path.is_file():
            return {}
        try:
            tree = ast.parse(self.script_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            return {}
        values = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            name = node.targets[0].id
            if name not in self.CONFIG_NAMES:
                continue
            try:
                values[name] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                if name in {"EOD_SQUARE_OFF_TIME", "ENTRY_WINDOW_START_TIME", "ENTRY_WINDOW_END_TIME"} and isinstance(node.value, ast.Call):
                    values[name] = ":".join(f"{ast.literal_eval(arg):02d}" for arg in node.value.args[:2])
        return values

    def _interpreter(self):
        """Honor an absolute Python shebang; otherwise use the server runtime."""
        try:
            with self.script_path.open(encoding="utf-8") as handle:
                first_line = handle.readline().strip()
        except OSError:
            return Path(sys.executable)
        if first_line.startswith("#!"):
            candidate = Path(first_line[2:].strip())
            if candidate.is_absolute() and candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
        return Path(sys.executable)

    def _recent_trades(self):
        try:
            with self.trades_path.open(newline="", encoding="utf-8") as handle:
                return list(csv.DictReader(handle))[-5:][::-1]
        except (FileNotFoundError, OSError, csv.Error):
            return []

    def _refresh_process(self):
        if self.process is not None:
            code = self.process.poll()
            if code is not None:
                self.last_exit_code = code
                self.process = None

    def snapshot(self):
        with self.lock:
            self._refresh_process()
            running = self.process is not None
            config = self._read_config()
            displayed_lots = self.active_lots if running and self.active_lots is not None else (config.get("NUM_LOTS") or 1)
            entry_start = self.active_entry_start if running and self.active_entry_start is not None else config.get("ENTRY_WINDOW_START_TIME", "09:15")
            entry_end = self.active_entry_end if running and self.active_entry_end is not None else config.get("ENTRY_WINDOW_END_TIME", "11:30")
            position = self._read_json(self.state_path)
            return {
                "name": "Sensex Long Straddle",
                "available": self.script_path.is_file(),
                "running": running,
                "mode": self.active_mode or "STOPPED",
                "live_control_available": True,
                "pid": self.process.pid if running else None,
                "started_at": self.started_at,
                "last_exit_code": self.last_exit_code,
                "script_path": str(self.script_path),
                "interpreter": str(self._interpreter()),
                "runtime_dir": str(self.runtime_dir),
                "strategy": {
                    "entry": f"SENSEX completed 5-minute realized volatility below percentile {config.get('VOL_PERCENTILE', '—')}",
                    "instrument": "Nearest-expiry ATM SENSEX CE + PE",
                    "exit": f"Supertrend({config.get('SUPER_TREND_PERIOD', '—')}, {config.get('SUPER_TREND_MULTIPLIER', '—')}) after +{config.get('SUPER_TREND_ACTIVATION_POINTS', '—')} points",
                    "hard_stop": f"-{config.get('STOPLOSS_POINTS', 15)} combined-premium points",
                    "eod": config.get("EOD_SQUARE_OFF_TIME", "—"),
                    "quantity": (config.get("LOT_SIZE") or 0) * displayed_lots,
                    "lot_size": config.get("LOT_SIZE"),
                    "default_lots": config.get("NUM_LOTS") or 1,
                    "selected_lots": displayed_lots,
                    "entry_window_start": entry_start,
                    "entry_window_end": entry_end,
                    "daily_reentry_limit": config.get("MAX_REENTRIES_PER_DAY", 1),
                },
                "position": position,
                "premium_chart": self._read_json(self.chart_path) if position else None,
                "paper_capital":self._read_json(self.runtime_dir/"paper-capital.json") if self.active_mode=="PAPER" else None,
                "recent_trades": self._recent_trades(),
                "output": list(self.output)[-20:],
                "updated_at": datetime.now().astimezone().isoformat(),
            }

    def _capture_output(self, process):
        stream = getattr(process, "stdout", None)
        if stream is None:
            return
        for line in stream:
            with self.lock:
                self.output.append(line.rstrip())

    def start(self, mode="live", exit_mode="supertrend", lots=1, entry_start="09:15", entry_end="11:30", confirmation="", paper_capital_inr=100000):
        mode = str(mode or "").strip().lower()
        exit_mode = str(exit_mode or "").strip().lower()
        try:
            requested_lots = int(lots)
        except (TypeError, ValueError):
            raise ValueError("Lots must be a whole number.") from None
        if requested_lots != lots and str(requested_lots) != str(lots).strip():
            raise ValueError("Lots must be a whole number.")
        if requested_lots < 1 or requested_lots > 20:
            raise ValueError("Lots must be between 1 and 20.")
        if mode not in {"paper", "live"}:
            raise ValueError("Mode must be paper or live.")
        exit_flags = {
            "supertrend": "--supertrend-trail",
            "fixed": "--fixed-target",
            "trail": "--trail-profit",
        }
        if exit_mode not in exit_flags:
            raise ValueError("Exit mode must be supertrend, fixed, or trail.")
        try:
            parsed_entry_start = datetime.strptime(str(entry_start), "%H:%M").strftime("%H:%M")
            parsed_entry_end = datetime.strptime(str(entry_end), "%H:%M").strftime("%H:%M")
        except ValueError:
            raise ValueError("Entry window times must use HH:MM IST.") from None
        if parsed_entry_start > parsed_entry_end:
            raise ValueError("Entry-window start must be no later than entry-window end.")
        if mode == "live" and confirmation != "YES":
            raise PermissionError("Type YES to authorize this live FYERS runner start.")

        with self.lock:
            self._refresh_process()
            if self.process is not None:
                return self.snapshot_unlocked(f"{self.active_mode.title()} runner is already active.")
            if not self.script_path.is_file():
                raise FileNotFoundError(f"SENSEX runner not found: {self.script_path}")
            env = os.environ.copy()
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            env["SENSEX_STRADDLE_RUNTIME_DIR"] = str(self.runtime_dir)
            token = str(self.credential_provider() or "")
            if token and ":" in token:
                app_id, access_token = token.split(":", 1)
                env["FYERS_APP_ID"] = app_id
                env["FYERS_ACCESS_TOKEN"] = access_token
            self.output.clear()
            script=self.script_path
            if mode=="paper":
                from .straddle_paper import prepare
                script=prepare(self.script_path,self.runtime_dir,paper_capital_inr,requested_lots)
            command = [
                str(self._interpreter()), "-u", str(script),
                exit_flags[exit_mode], "--lots", str(requested_lots),
                "--entry-start", parsed_entry_start, "--entry-end", parsed_entry_end,
            ]
            if mode == "live":
                command.append("--live")
            self.process = self.process_factory(
                command,
                cwd=str(self.runtime_dir), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE if mode == "live" else None,
                text=True, bufsize=1,
            )
            if mode == "live" and self.process.stdin is not None:
                self.process.stdin.write("YES\n")
                self.process.stdin.flush()
                self.process.stdin.close()
            self.started_at = datetime.now().astimezone().isoformat()
            self.active_mode = mode.upper()
            self.active_exit_mode = exit_mode
            self.active_lots = requested_lots
            self.active_entry_start = parsed_entry_start
            self.active_entry_end = parsed_entry_end
            self.last_exit_code = None
            Thread(target=self._capture_output, args=(self.process,), daemon=True, name="sensex-straddle-output").start()
            label = {"supertrend": "Supertrend trail", "fixed": "fixed target", "trail": "profit trail"}[exit_mode]
            return self.snapshot_unlocked(f"{mode.title()} runner started with {label} using {requested_lots} lot(s) in the {parsed_entry_start}-{parsed_entry_end} IST entry window.")

    def start_paper(self):
        """Compatibility entry point for existing callers."""
        return self.start(mode="paper", exit_mode="supertrend")

    def snapshot_unlocked(self, message=None):
        running = self.process is not None and self.process.poll() is None
        result = {
            "running": running, "mode": self.active_mode or "STOPPED", "live_control_available": True,
            "pid": self.process.pid if running else None, "started_at": self.started_at,
            "exit_mode": self.active_exit_mode,
            "lots": self.active_lots,
        }
        if message:
            result["message"] = message
        return result

    def stop(self):
        with self.lock:
            self._refresh_process()
            process = self.process
            if process is None:
                return self.snapshot_unlocked("Runner is already stopped.")
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        with self.lock:
            self.last_exit_code = process.returncode
            self.process = None
            mode = self.active_mode or "Strategy"
            self.active_mode = None
            self.active_exit_mode = None
            self.active_lots = None
            self.active_entry_start = None
            self.active_entry_end = None
            return self.snapshot_unlocked(f"{mode.title()} runner stopped.")
