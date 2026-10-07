"""Guarded process bridge for the external NIFTY long-straddle runner."""

from datetime import datetime
import os
from pathlib import Path
import subprocess
from threading import Thread

from .sensex_straddle import SensexStraddleService


LEGACY_SCRIPT_PATH = Path("/Users/pinaki/trading/NIFTY/nifty_straddle.py")
BUNDLED_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "strategies" / "long_straddle" / "nifty_straddle.py"
DEFAULT_SCRIPT_PATH = LEGACY_SCRIPT_PATH if LEGACY_SCRIPT_PATH.is_file() else BUNDLED_SCRIPT_PATH


class NiftyStraddleService(SensexStraddleService):
    """Inspect and control the NIFTY runner while preserving its own CLI contract."""

    CONFIG_NAMES = {
        "NUM_LOTS", "VOL_PERCENTILE", "VOL_LOOKBACK_DAYS", "REALIZED_VOL_WINDOW_BARS",
        "STOPLOSS_POINTS", "TARGET_POINTS", "EOD_SQUARE_OFF_TIME", "SUPER_TREND_PERIOD",
        "SUPER_TREND_MULTIPLIER", "SUPER_TREND_ACTIVATION_POINTS", "ENTRY_WINDOW_START_TIME",
        "ENTRY_WINDOW_END_TIME", "MAX_REENTRIES_PER_DAY",
    }

    def __init__(self, script_path=None, credential_provider=None, process_factory=None, runtime_dir=None):
        configured = script_path or os.getenv("SECTOR_PULSE_NIFTY_STRADDLE_SCRIPT")
        super().__init__(
            configured or DEFAULT_SCRIPT_PATH,
            credential_provider=credential_provider,
            process_factory=process_factory,
            runtime_dir=runtime_dir or (Path(__file__).resolve().parents[1] / ".private" / "nifty-straddle" if Path(configured or DEFAULT_SCRIPT_PATH).resolve() == BUNDLED_SCRIPT_PATH.resolve() else None),
        )
        self.active_stoploss = None
        self.active_target = None

    @property
    def state_path(self):
        return (self.runtime_dir if self.active_mode=="PAPER" or self.script_path == BUNDLED_SCRIPT_PATH.resolve() else self.script_path.parent) / "live_position_state.json"

    @property
    def trades_path(self):
        return (self.runtime_dir if self.active_mode=="PAPER" or self.script_path == BUNDLED_SCRIPT_PATH.resolve() else self.script_path.parent) / "live_trade_log.csv"

    @property
    def chart_path(self):
        return (self.runtime_dir if self.active_mode=="PAPER" or self.script_path == BUNDLED_SCRIPT_PATH.resolve() else self.script_path.parent) / "live_premium_chart.json"

    def snapshot(self):
        with self.lock:
            self._refresh_process()
            running = self.process is not None
            config = self._read_config()
            lots = self.active_lots if running and self.active_lots is not None else (config.get("NUM_LOTS") or 1)
            stoploss = self.active_stoploss if running and self.active_stoploss is not None else config.get("STOPLOSS_POINTS", 15)
            target = self.active_target if running and self.active_target is not None else config.get("TARGET_POINTS", 30)
            entry_start = self.active_entry_start if running and self.active_entry_start is not None else config.get("ENTRY_WINDOW_START_TIME", "09:15")
            entry_end = self.active_entry_end if running and self.active_entry_end is not None else config.get("ENTRY_WINDOW_END_TIME", "11:30")
            position = self._read_json(self.state_path)
            lot_size = position.get("lot_size") if position else None
            return {
                "name": "NIFTY Long Straddle",
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
                    "entry": f"NIFTY 5-minute realised volatility below percentile {config.get('VOL_PERCENTILE', '—')} over {config.get('VOL_LOOKBACK_DAYS', '—')} days",
                    "instrument": "Nearest-weekly ATM NIFTY CE + PE",
                    "exit": (f"Supertrend({config.get('SUPER_TREND_PERIOD', 7)}, {config.get('SUPER_TREND_MULTIPLIER', 3)}) after +{config.get('SUPER_TREND_ACTIVATION_POINTS', 10)} points" if (self.active_exit_mode or "supertrend") == "supertrend" else f"Fixed combined-premium target +{target:g} points"),
                    "hard_stop": f"-{stoploss:g} combined-premium points",
                    "eod": config.get("EOD_SQUARE_OFF_TIME", "—"),
                    "quantity": lot_size * lots if lot_size else None,
                    "lot_size": lot_size,
                    "default_lots": config.get("NUM_LOTS") or 1,
                    "selected_lots": lots,
                    "stoploss_points": stoploss,
                    "target_points": target,
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

    def start(self, mode="live", lots=1, stoploss=15, target=30, exit_mode="supertrend", entry_start="09:15", entry_end="11:30", confirmation="", paper_capital_inr=100000):
        mode = str(mode or "").strip().lower()
        try:
            requested_lots = int(lots)
        except (TypeError, ValueError):
            raise ValueError("Lots must be a whole number.") from None
        if requested_lots != lots and str(requested_lots) != str(lots).strip():
            raise ValueError("Lots must be a whole number.")
        if requested_lots < 1 or requested_lots > 20:
            raise ValueError("Lots must be between 1 and 20.")
        try:
            requested_stoploss, requested_target = float(stoploss), float(target)
        except (TypeError, ValueError):
            raise ValueError("Stoploss and target must be numeric point values.") from None
        if requested_stoploss <= 0 or requested_target <= 0:
            raise ValueError("Stoploss and target must be greater than zero.")
        if mode not in {"paper", "live"}:
            raise ValueError("Mode must be paper or live.")
        if exit_mode not in {"supertrend", "fixed"}:
            raise ValueError("Exit mode must be supertrend or fixed.")
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
                raise FileNotFoundError(f"NIFTY runner not found: {self.script_path}")
            env = os.environ.copy()
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            env["NIFTY_STRADDLE_RUNTIME_DIR"] = str(self.runtime_dir)
            token = str(self.credential_provider() or "")
            if token and ":" in token:
                app_id, access_token = token.split(":", 1)
                env["FYERS_APP_ID"] = app_id
                env["FYERS_ACCESS_TOKEN"] = access_token
            script=self.script_path
            if mode=="paper":
                from .straddle_paper import prepare
                script=prepare(self.script_path,self.runtime_dir,paper_capital_inr,requested_lots)
            command = [
                str(self._interpreter()), "-u", str(script),
                "--lots", str(requested_lots), "--stoploss", str(requested_stoploss),
                "--target", str(requested_target),
                "--entry-start", parsed_entry_start, "--entry-end", parsed_entry_end,
                "--supertrend-trail" if exit_mode == "supertrend" else "--fixed-target",
            ]
            if mode == "live":
                command.append("--live")
            self.output.clear()
            self.process = self.process_factory(
                command, cwd=str(self.runtime_dir), env=env,
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
            self.active_lots = requested_lots
            self.active_exit_mode = exit_mode
            self.active_stoploss = requested_stoploss
            self.active_target = requested_target
            self.active_entry_start = parsed_entry_start
            self.active_entry_end = parsed_entry_end
            self.last_exit_code = None
            Thread(target=self._capture_output, args=(self.process,), daemon=True, name="nifty-straddle-output").start()
            return self.snapshot_unlocked(
                f"{mode.title()} runner started with {requested_lots} lot(s), {requested_stoploss:g}-point stop and {requested_target:g}-point target in the {parsed_entry_start}-{parsed_entry_end} IST entry window."
            )

    def stop(self):
        result = super().stop()
        if not result.get("running"):
            self.active_stoploss = None
            self.active_target = None
            self.active_entry_start = None
            self.active_entry_end = None
        return result
