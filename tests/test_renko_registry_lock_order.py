"""Exercise real nested registry readers while a runner waits for the registry."""
import ast
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

class RegistryLockTests(unittest.TestCase):
    def test_listing_releases_registry_before_runner_snapshot(self):
        tree=ast.parse(Path('sector_heatmap/web.py').read_text())
        function=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='renko_instance_rows')
        registry=threading.RLock();runner_lock=threading.Lock();entered=threading.Event();finished=threading.Event()
        class Runner:
            def snapshot(self):
                entered.set()
                with runner_lock:return {'running':False}
        flat=SimpleNamespace(snapshot=lambda:{'running':False})
        namespace={'renko_instances_lock':registry,'renko_instances':{'test':{'broker':'FYERS','instrument':'TEST','component':(Runner(),)}},'renko_default_bundle':(flat,), 'delta_default_service':SimpleNamespace(runner=flat)}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'registry-reader','exec'),namespace)
        runner_lock.acquire()
        def listing():namespace['renko_instance_rows']();finished.set()
        thread=threading.Thread(target=listing,daemon=True);thread.start()
        try:
            self.assertTrue(entered.wait(1))
            acquired=registry.acquire(timeout=.3)
            self.assertTrue(acquired,'Registry lock held while waiting for runner: deadlock')
            if acquired:registry.release()
        finally:runner_lock.release()
        self.assertTrue(finished.wait(1));thread.join(1)
