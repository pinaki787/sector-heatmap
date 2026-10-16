"""Optional Dhan Engine service, bound to the existing authenticated account."""
from types import SimpleNamespace
from pathlib import Path
import threading
from .service import Registry
from .runner import dhan_runner_type

class NoExternalAdoptions:
    def __init__(self):self.lock=threading.RLock();self.runners={}
    def owned_symbols(self):return set()
    def inventory(self):return dict(positions=[],managers=[],message='External Dhan position adoption is unavailable in the shared Dhan runner.')
    def apply(self,_):raise ValueError('External Dhan position adoption is unavailable')
    def control(self,_):raise ValueError('External Dhan position adoption is unavailable')

def registry(execution,root):
    if getattr(execution,'renko_engine_registry',None):return execution.renko_engine_registry
    from sector_heatmap.dhan_strategy_broker import Broker
    runner_type=dhan_runner_type()
    def factory(broker,key,instrument,folder):
        if broker!='DHAN':raise ValueError('This is an owned Dhan account')
        adapter=Broker(execution);chart=Broker(execution);runner=runner_type(adapter,folder/'state.json');runner.valuation_adapter=chart
        return SimpleNamespace(runner=runner,broker=adapter,chart_broker=chart,adoptions=NoExternalAdoptions(),wake=threading.Event(),search=lambda q:dict(matches=chart.search(q)))
    value=Registry(execution.folder/'engine-service',factory);execution.renko_engine_registry=value
    return value
