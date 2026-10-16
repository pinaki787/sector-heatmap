from pathlib import Path
from types import SimpleNamespace
import unittest
from tests import test_dhan_strategy_broker as fixtures
from sector_heatmap.dhan_strategy_service import Service
from sector_heatmap.dhan_form_routes import read,write,config

class FormTests(unittest.TestCase):
    setUp=fixtures.Tests.setUp
    def form(self,strategy):
        form=Service(self.service,Path(self.temp.name),'default',strategy)
        form.broker.clock=lambda:self.now;form.chart_broker.clock=lambda:self.now
        form.runner.clock=lambda:self.now
        return form
    def test_existing_forms_search_only_private_dhan_master_and_return_expected_fields(self):
        for strategy in ('band','kama','rsi'):
            form=self.form(strategy)
            result=read(form,'underlying-search',{'q':['NIFTY']})
            self.assertTrue(result['status']['usable'])
            self.assertEqual(result['matches'][0]['symbol'],'NSE:NIFTY')
            self.assertIn('underlying_kind',result['matches'][0])
            self.assertEqual(read(form,'runner',{})['broker'],'DHAN')
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))
    def test_existing_chart_reads_do_not_activate_or_order(self):
        for strategy in ('band','kama','rsi'):
            form=self.form(strategy)
            value=read(form,'chart',{'symbol':['NSE:NIFTY'],'timeframe':['1 minute']})
            self.assertEqual(value['broker'],'DHAN')
            self.assertEqual(len(value['candles']),3)
            self.assertIn('kama' if strategy=='kama' else 'ema_high',value['candles'][0])
            self.assertFalse(form.runner.snapshot()['running'])
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))
    def test_unsupported_protection_never_silently_ignored(self):
        band=self.form('band')
        for key,value in (('entry_session','0915-2330'),):
            with self.assertRaises(ValueError):config(band,dict(underlying='NSE:NIFTY',mode='PAPER',**{key:value}))
        kama=self.form('kama')
        with self.assertRaises(ValueError):write(kama,'runner-start',dict(mode='LIVE',execution_mode='OPTIONS'))
        with self.assertRaises(ValueError):config(kama,dict(execution_mode='EQUITY'))
        self.assertEqual(self.client.calls,[])
    def test_existing_preview_binds_broker_without_starting(self):
        form=self.form('band')
        result=write(form,'preview',dict(underlying='NSE:NIFTY',timeframe='1 minute',lots='1',mode='PAPER',entry_session='0915-1510'))
        self.assertEqual(result['config']['broker'],'DHAN')
        self.assertFalse(form.runner.snapshot()['running'])
        self.assertFalse(any(m=='POST' and p=='/orders' for m,p,_ in self.client.calls))
if __name__=='__main__':unittest.main()
