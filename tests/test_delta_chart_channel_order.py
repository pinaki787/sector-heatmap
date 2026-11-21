"""Candle channels keep independent ordering; executable ticks remain monotonic."""
import importlib.util
import os
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from strategies.renko_supertrend.delta_broker import Broker as ActiveBroker

def broker_type():
 path=os.environ.get('DELTA_CHART_BROKER_SOURCE')
 if not path:return ActiveBroker
 spec=importlib.util.spec_from_file_location('strategies.renko_supertrend.chart_order_candidate',path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module.Broker

class ChartChannelOrder(unittest.TestCase):
 def setUp(self):
  self.b=broker_type().__new__(broker_type())
  self.b.delta=SimpleNamespace(clock=lambda:1802.0)
  self.b.lock=threading.RLock();self.b.symbols={'PAXGUSD'}
  self.b.candle_resolutions={60:'1m',1800:'30m'}
  self.b.ticks={};self.b.quotes={};self.b.forming_bars={}
  self.callbacks=[];self.b.on_tick=self.callbacks.append
 def send(self,res,stamp,close=101,received=1802):
  self.b.ingest(dict(type='candlestick_'+res,res=res,sy='PAXGUSD',ts=stamp*1e6,cst=1800*1e6,o=100,h=105,l=99,c=close,v=5),received)
 def test_later_channel_keeps_own_candle_without_rewinding_tick_or_callback(self):
  self.send('1m',1802,102);self.send('30m',1801,101)
  self.assertEqual(self.b.forming_bars['PAXGUSD',1800,1800]['close'],101)
  self.assertEqual(self.b.ticks['PAXGUSD']['ltp'],102)
  self.assertEqual([x['ltp'] for x in self.callbacks],[102])
 def test_same_channel_older_revision_cannot_replace_newer_candle(self):
  self.send('30m',1802,102);self.send('30m',1801,101)
  self.assertEqual(self.b.forming_bars['PAXGUSD',1800,1800]['close'],102)
  self.assertEqual(len(self.callbacks),1)
 def test_fresh_newer_revision_updates_tick_and_notifies_once(self):
  self.send('1m',1801,101);self.send('30m',1802,102)
  self.assertEqual(self.b.ticks['PAXGUSD']['ltp'],102)
  self.assertEqual([x['ltp'] for x in self.callbacks],[101,102])
 def test_old_feed_timestamps_are_still_rejected(self):
  self.send('30m',1801,101,received=1820)
  self.assertFalse(self.b.forming_bars);self.assertFalse(self.callbacks)

if __name__=='__main__':unittest.main()
