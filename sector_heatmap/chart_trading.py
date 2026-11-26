"""Account-scoped chart trading controller; broker adapters never cross sources."""
from .chart_trade_previews import ChartTradePreviews
import threading
import os

_SERVICES_LOCK=threading.Lock()

def dhan_chart_enabled():
    return os.environ.get("SECTOR_PULSE_ENABLE_DHAN_CHART_ORDERS")=="1"


def broker_active(broker):
    return broker in {"FYERS","DELTA_INDIA"} or broker=="DHAN" and dhan_chart_enabled()



class ChartTradingService:
    def __init__(self, account, path, adapter_factory, *, clock=None, conditional_factory=None):
        self.account = dict(account)
        self.adapter_factory = adapter_factory
        self.reconciliation_lock=threading.Lock()
        self.monitor=None
        self.previews = ChartTradePreviews(path, **({"clock": clock} if clock else {}))
        self.conditional=conditional_factory(self) if conditional_factory else None

    def _authorize(self, user, payload):
        if not user or not user.get("id"):
            raise PermissionError("Sign in before reviewing a chart order.")
        if self.account.get("user_id") and self.account["user_id"] != user["id"] and not user.get("admin"):
            raise PermissionError("The selected broker account belongs to another user.")
        features = set(user.get("features") or [])
        if not user.get("admin") and not {"broker", "chart-workspace"} <= features:
            raise PermissionError("Chart workspace and broker permissions are both required for chart trading.")
        if payload.get("account_id") != self.account["id"] or payload.get("broker") != self.account["broker"]:
            raise PermissionError("The requested chart order differs from the selected broker account.")
        return str(user["id"])

    def prepare(self, user, payload):
        owner = self._authorize(user, payload)
        adapter = self.adapter_factory(self.account)
        plan = adapter.prepare(payload)
        if plan.account_id != self.account["id"] or plan.broker != self.account["broker"]:
            raise PermissionError("The execution adapter returned a different broker account.")
        warm=getattr(adapter,"warm_live_feed",None)
        if warm:warm(plan)
        preview = self.previews.prepare(owner, plan)
        preview["live_submission_enabled"] = bool(self.account.get("live_enabled") and adapter.live_enabled())
        preflight = getattr(adapter, "last_preflight", None) or {}
        preview["preflight"] = {key:preflight[key] for key in ("available_funds","required_margin","settlement_currency","margin_status","quote","checked_at","notice","order_notional") if key in preflight}
        return preview

    def arm(self, user, payload):
        owner = self._authorize(user, payload)
        adapter = self.adapter_factory(self.account)
        record=self.previews.inspect(owner,payload.get("preview_id"))
        if record["plan"]["broker"]=="DHAN" and record["plan"]["entry_type"]=="STOP_LIMIT":
            if self.conditional is None:
                raise ValueError("The Dhan conditional chart controller is not activated.")
            return self.conditional.arm(owner,payload,adapter)
        return self.previews.arm(owner, payload.get("preview_id"), payload.get("confirmation"),
                                 mode=payload.get("mode"), adapter=adapter,
                                 enabled=bool(self.account.get("live_enabled") and adapter.live_enabled()))

    def cancel_condition(self,user,payload):
        owner=self._authorize(user,payload)
        if self.conditional is None:
            raise ValueError("No conditional chart controller is active.")
        return self.conditional.cancel(owner,payload.get("preview_id"))

    def status(self, user, payload):
        owner = self._authorize(user, payload)
        if not self.reconciliation_lock.acquire(blocking=False):
            return dict(self.previews.inspect(owner,payload.get("preview_id")),refresh_in_progress=True)
        try:
            return self.previews.reconcile(owner,payload.get("preview_id"),self.adapter_factory(self.account))
        except Exception:
            return self.previews.record_read_failure(owner,payload.get("preview_id"))
        finally:self.reconciliation_lock.release()

    def start_monitor(self):
        if self.monitor is None:
            from .chart_trade_monitor import ChartTradeMonitor
            self.monitor=ChartTradeMonitor(self)
        self.monitor.start()

    def close(self):
        if self.conditional:self.conditional.close()
        if self.monitor:self.monitor.close()


def handle(handler, path, payload, *, workspace_guard, fyers_execution, delta_execution=None, dhan_execution=None, dhan_tick_reader=None):
    prefix = "/api/chart-workspace/trading/"
    if not path.startswith(prefix):
        return False
    if not workspace_guard:
        raise PermissionError("Chart trading requires the selected private broker workspace.")
    from .chart_workspace import require_chart
    user, account = handler.workspace_identity
    require_chart(user, workspace_guard.store, path)
    if payload.get("account_id") != account["id"] or payload.get("broker") != account["broker"]:
        raise PermissionError("Chart trading account differs from this private workspace.")
    if not broker_active(account["broker"]):
        raise ValueError("The selected broker's chart execution adapter is not yet active. No order was prepared or sent.")
    native_dhan=dhan_execution() if account["broker"]=="DHAN" and callable(dhan_execution) else dhan_execution
    service=get_service(handler.server,workspace_guard,account,fyers_execution,delta_execution,
                        dhan_execution=native_dhan,dhan_tick_reader=dhan_tick_reader)
    service.account = dict(account)
    action = path[len(prefix):]
    actions={"prepare":"prepare","arm":"arm","status":"status"}
    if account["broker"]=="DHAN":actions["cancel-condition"]="cancel_condition"
    if action not in actions:
        raise ValueError("Unknown chart trading action.")
    handler.send_json(200, getattr(service,actions[action])(user,payload))
    return True



def get_service(server,guard,account,fyers_execution,delta_execution=None,*,dhan_execution=None,dhan_tick_reader=None):
    if not broker_active(account["broker"]):
        raise ValueError("No chart execution adapter is registered for this broker.")
    from .chart_trade_fyers import FyersChartAdapter
    from .chart_trade_delta import DeltaChartAdapter
    if account["broker"]=="DELTA_INDIA" and delta_execution is None:
        raise ValueError("The selected Delta chart execution service is unavailable.")
    conditional_factory=None
    if account["broker"]=="DHAN":
        if (dhan_execution is None or dhan_execution.account.get("id")!=account["id"]
                or dhan_execution.account.get("broker")!="DHAN" or not callable(dhan_tick_reader)):
            raise ValueError("The exact selected Dhan service and live tick reader are required.")
        from .chart_trade_dhan import DhanChartAdapter
        from .chart_trade_dhan_controller import DhanConditionalController
        from .chart_trade_dhan_sessions import conditional_expiry
        tick_reader=lambda symbol:dhan_tick_reader(dhan_execution,symbol)
        conditional_factory=lambda service:DhanConditionalController(service,tick_reader=tick_reader,
            expiry_resolver=conditional_expiry,enabled=lambda:dhan_chart_enabled() and dhan_execution.execution_allowed())
    def adapter(selected):
        if selected["broker"]=="DHAN":
            return DhanChartAdapter(selected,dhan_execution,submission_enabled=dhan_chart_enabled(),
                activation_check=dhan_chart_enabled,tick_reader=tick_reader)
        return DeltaChartAdapter(selected,delta_execution) if selected["broker"]=="DELTA_INDIA" else FyersChartAdapter(selected,fyers_execution)
    with _SERVICES_LOCK:
        if not hasattr(server,"chart_trading_services"):server.chart_trading_services={}
        service=server.chart_trading_services.get(account["id"])
        if service is None:
            service=ChartTradingService(account,guard.store.folder(account)/"chart-trading.sqlite3",adapter,
                                        conditional_factory=conditional_factory)
            if service.conditional:service.conditional.recover_waiting()
            server.chart_trading_services[account["id"]]=service
            service.start_monitor()
        elif service.account.get("broker")!=account["broker"]:
            raise PermissionError("Cached chart execution service belongs to another broker.")
        service.account=dict(account)
        return service


def resume_existing(server,guard,fyers_execution,delta_execution=None,*,dhan_execution_factory=None,dhan_tick_reader=None):
    if not guard:return
    with guard.store.db() as db:
        row=db.execute("SELECT * FROM accounts WHERE id=?",(guard.account_id,)).fetchone()
    if not row:return
    account=dict(row)
    if not broker_active(account["broker"]):return
    if (guard.store.folder(account)/"chart-trading.sqlite3").exists():
        native_dhan=dhan_execution_factory(account) if account["broker"]=="DHAN" and dhan_execution_factory else None
        get_service(server,guard,account,fyers_execution,delta_execution,
                    dhan_execution=native_dhan,dhan_tick_reader=dhan_tick_reader)


def close_services(server):
    for service in getattr(server,"chart_trading_services",{}).values():service.close()
