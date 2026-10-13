import unittest
from datetime import datetime
from sector_heatmap.dhan_execution import IST
from sector_heatmap import dhan_mcx as mcx

class McxDiscovery(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,13,12,tzinfo=IST).timestamp()
        def row(id,kind,expiry,option='XX'):
            return dict(SEM_EXM_EXCH_ID='MCX',SEM_SEGMENT='M',SEM_INSTRUMENT_NAME=kind,
                SEM_STRIKE_PRICE='7750',SEM_OPTION_TYPE=option,SEM_SMST_SECURITY_ID=id,SM_SYMBOL_NAME='CRUDEOIL',
                SEM_TRADING_SYMBOL='CRUDEOIL-'+id,SEM_CUSTOM_SYMBOL='Crude '+id,
                SEM_EXPIRY_DATE=expiry+' 23:30:00')
        self.rows=[row('oct','FUTCOM','2026-10-19'),row('nov','FUTCOM','2026-11-19'),
            row('oc','OPTFUT','2026-10-15','CE'),row('op','OPTFUT','2026-10-15','PE'),
            row('nc','OPTFUT','2026-11-16','CE'),row('np','OPTFUT','2026-11-16','PE')]
    def test_discovery_uses_native_exact_expiry_hosts(self):
        self.assertEqual([r['symbol'] for r in mcx.search(self.rows,self.now)],['MCX:CRUDEOIL-OCT','MCX:CRUDEOIL-NOV'])
    def test_all_market_search_includes_spaced_commodity_query(self):
        from sector_heatmap.dhan_strategy_broker import Broker
        broker=Broker(None,clock=lambda:self.now)
        broker._rows=lambda:self.rows
        for query in ('crude oil','CRUDEOIL','crude  oil'):
            with self.subTest(query=query):
                self.assertEqual([r['symbol'] for r in broker.search(query,'ALL')],
                    ['MCX:CRUDEOIL-OCT','MCX:CRUDEOIL-NOV'])
                self.assertEqual(len(broker.search(query,'MCX')),2)
        self.assertEqual(broker.search('crude oil','NSE_INDEX'),[])
        self.assertEqual(broker.search('crude oil'),[])

    def test_host_matches_form_normalized_case_without_changing_expiry(self):
        self.assertEqual(mcx.host(self.rows,'MCX:CRUDEOIL-OCT',self.now)['SEM_SMST_SECURITY_ID'],'oct')

    def test_option_series_does_not_cross_future_month(self):
        self.assertEqual({r['SEM_SMST_SECURITY_ID'] for r in mcx.option_series(self.rows,self.rows[0],self.now)},{'oc','op'})
    def test_missing_or_expired_host_never_rolls(self):
        with self.assertRaises(ValueError):mcx.host(self.rows,'MCX:CRUDEOIL-missing',self.now)
        with self.assertRaises(ValueError):mcx.host(self.rows,'MCX:CRUDEOIL-OCT',datetime(2026,10,20,tzinfo=IST).timestamp())
    def test_no_call_put_pair_is_excluded(self):
        self.assertEqual(mcx.search(self.rows[:3],self.now),[])
    def test_cross_exchange_rows_are_excluded(self):
        self.rows[0]['SEM_EXM_EXCH_ID']='NSE'
        self.assertEqual(len(mcx.search(self.rows,self.now)),1)

    def test_different_strikes_are_not_a_pair(self):
        self.rows[3]['SEM_STRIKE_PRICE']='7800'
        self.assertEqual([r['symbol'] for r in mcx.search(self.rows,self.now)],['MCX:CRUDEOIL-NOV'])
    def test_invalid_strike_is_excluded(self):
        for value in ('NaN','Infinity','0','bad'):
            with self.subTest(value=value):
                self.rows[3]['SEM_STRIKE_PRICE']=value
                self.assertEqual(len(mcx.search(self.rows,self.now)),1)

class McxValuation(unittest.TestCase):
    def row(self,family,expiry='2026-10-15'):
        return dict(SM_SYMBOL_NAME=family,SEM_EXM_EXCH_ID='MCX',SEM_SEGMENT='M',
                    SEM_LOT_UNITS='1',SEM_EXPIRY_DATE=expiry+' 23:30:00')
    def test_point_values_are_not_api_lots(self):
        for family,value in {'CRUDEOIL':100,'CRUDEOILM':10,'NATURALGAS':1250,'NATGASMINI':250,
                             'GOLD':100,'GOLDM':10,'SILVER':30,'SILVERM':5,'COPPER':2500,'ZINC':5000}.items():
            with self.subTest(family=family):
                self.assertEqual(mcx.valuation(self.row(family))['quantity_multiplier'],value)
    def test_bulldex_contract_revision(self):
        self.assertEqual(mcx.valuation(self.row('MCXBULLDEX'))['quantity_multiplier'],30)
        self.assertEqual(mcx.valuation(self.row('MCXBULLDEX','2026-11-25'))['quantity_multiplier'],15)
        dt=datetime.fromtimestamp(mcx.expiry_at(self.row('MCXBULLDEX')),IST)
        self.assertEqual((dt.hour,dt.minute),(17,0))
    def test_changed_api_lot_or_unknown_family_fails_closed(self):
        row=self.row('CRUDEOIL');row['SEM_LOT_UNITS']='100'
        with self.assertRaises(ValueError):mcx.valuation(row)
        with self.assertRaises(ValueError):mcx.valuation(self.row('UNKNOWN'))
    def test_dst_and_preexpiry_cutoff(self):
        summer=datetime(2026,10,13,12,tzinfo=IST).timestamp()
        winter=datetime(2026,11,9,12,tzinfo=IST).timestamp()
        self.assertEqual(mcx.session(summer)['master_regular_session'],'0900-2330')
        self.assertEqual(mcx.session(winter)['master_regular_session'],'0900-2355')
        cutoff=datetime.fromtimestamp(mcx.entry_cutoff(self.row('CRUDEOIL','2026-10-19')),IST)
        self.assertEqual(cutoff.strftime('%Y-%m-%d %H:%M'),'2026-10-16 23:00')

class McxCosts(unittest.TestCase):
    def test_premium_turnover_tax_and_brokerage(self):
        from strategies.renko_supertrend.dhan_costs import order_cost
        row=dict(filled=2,average_price=100,quantity_multiplier=100,dhan_exchange_rate=.000418,side='SELL')
        cost=order_cost(row)
        self.assertEqual(cost['premium_turnover'],20000)
        self.assertEqual(cost['ctt'],10)
        self.assertEqual(cost['stt'],0)
        self.assertEqual(cost['exchange'],8.36)
        self.assertEqual(cost['brokerage'],20)
        row['side']='BUY';cost=order_cost(row)
        self.assertEqual(cost['ctt'],0)
        self.assertEqual(cost['stamp'],1)

class McxCalendar(unittest.TestCase):
    def stamp(self,date,hour=12):return datetime.fromisoformat(date).replace(hour=hour,tzinfo=IST).timestamp()
    def test_holiday_sessions(self):
        self.assertFalse(mcx.session_open(self.stamp('2026-10-02')))
        self.assertFalse(mcx.session_open(self.stamp('2026-10-20')))
        self.assertTrue(mcx.session_open(self.stamp('2026-10-20',18)))
        self.assertFalse(mcx.session_open(self.stamp('2026-01-01',18)))
        self.assertTrue(mcx.session_open(self.stamp('2026-01-01',12)))
    def test_expiry_preceded_by_closed_day(self):
        cutoff=mcx.entry_cutoff(dict(SM_SYMBOL_NAME='CRUDEOIL',SEM_EXPIRY_DATE='2026-10-05'))
        self.assertEqual(datetime.fromtimestamp(cutoff,IST).strftime('%Y-%m-%d %H:%M'),'2026-10-01 23:00')
    def test_unknown_calendar_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'calendar'):mcx.trading_bounds(self.stamp('2027-01-04'))
