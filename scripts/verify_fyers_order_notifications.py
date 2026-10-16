"""Isolated notification-only smoke check. Never creates or controls a runner."""
import argparse
import importlib.util
import json
import os
import threading
import time
from types import SimpleNamespace


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--module-file',required=True)
    parser.add_argument('--account-id',required=True)
    parser.add_argument('--seconds',type=int,default=15)
    args=parser.parse_args()
    if os.environ.get('SECTOR_PULSE_WORKSPACE_ID')!=args.account_id:
        raise SystemExit('Selected account environment required; no connection attempted.')
    spec=importlib.util.spec_from_file_location('verified_order_stream',args.module_file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    runner=SimpleNamespace(wake=threading.Event())
    stream=module.OrderNotifications(runner,threading.Event(),'/tmp')
    try:
        stream.start()
        deadline=time.monotonic()+max(1,min(args.seconds,30))
        while time.monotonic()<deadline:
            value=stream.snapshot()
            if value['connected'] and value['received_at'] is not None:break
            time.sleep(.25)
        print(json.dumps(stream.snapshot()))
    finally:
        with stream.lock:
            socket=stream.socket;stream.socket=None;stream.generation+=1
        if socket:
            def close():
                try:socket.close_connection()
                except Exception:pass
            worker=threading.Thread(target=close,daemon=True);worker.start();worker.join(2)


if __name__=='__main__':main()
