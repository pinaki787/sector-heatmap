import tempfile,threading,unittest
from pathlib import Path
from .runner import Broker,Runner

class SocketStopTests(unittest.TestCase):
    def test_sdk_join_does_not_hold_runner_lock_against_tick_callback(self):
        with tempfile.TemporaryDirectory() as folder:
            broker=Broker(folder,lambda *args:[],lambda *args:None)
            runner=Runner(broker,Path(folder)/'state.json')
            started=threading.Event();message_done=threading.Event();closed=threading.Event()
            def callback():
                started.set()
                broker.on_tick({'symbol':'S','ltp':1})
                message_done.set()
            class Socket:
                def close_connection(self):
                    if message_done.wait(1):closed.set()
            broker.socket=Socket();broker.connected=True
            with runner.lock:
                worker=threading.Thread(target=callback,daemon=True);worker.start()
                self.assertTrue(started.wait(1))
                runner.stop()
                self.assertTrue(message_done.wait(1))
                self.assertIsNone(broker.socket)
                self.assertFalse(broker.connected)
            self.assertTrue(message_done.wait(1));self.assertTrue(closed.wait(1))
            worker.join(1);broker.close_thread.join(1);runner.release()
