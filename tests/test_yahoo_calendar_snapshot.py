import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from sector_heatmap.yahoo_snapshot import calendar_snapshot


def stamp(text, zone='Asia/Kolkata'):
    return int(datetime.fromisoformat(text).replace(tzinfo=ZoneInfo(zone)).timestamp())


class YahooCalendarSnapshot(unittest.TestCase):
    def annual(self):
        times=[stamp(f'2026-{m:02d}-01') for m in range(1,12)]
        values={'open':[100+i for i in range(11)],'high':[120+i for i in range(11)],
                'low':[90+i for i in range(11)],'close':[110+i for i in range(11)],'volume':[10]*11}
        meta={'exchangeTimezoneName':'Asia/Kolkata','regularMarketTime':stamp('2026-11-18T15:30')}
        return times,values,meta,stamp('2026-11-19')

    def test_current_annual_snapshot_includes_partial_month_and_ignores_appended_quote(self):
        t,v,m,n=self.annual();t.append(stamp('2026-11-18T15:30'))
        for key in v:v[key].append(99999)
        result=calendar_snapshot(t,v,'12M','1M',m,n)
        self.assertEqual(result['bar'],[stamp('2026-01-01'),100,130,90,120,110])
        self.assertEqual(result['as_of'],m['regularMarketTime'])
        self.assertEqual(result['close_time'],stamp('2027-01-01'))
        self.assertTrue(result['provisional']);self.assertTrue(result['history_only'])

    def test_missing_month_or_leading_partial_year_is_not_invented(self):
        for drop in (0,4):
            t,v,m,n=self.annual();t.pop(drop)
            for key in v:v[key].pop(drop)
            self.assertIsNone(calendar_snapshot(t,v,'12M','1M',m,n))

    def test_conflicting_duplicate_and_invalid_prices_fail_closed(self):
        t,v,m,n=self.annual();t.append(t[-1])
        for key in v:v[key].append(v[key][-1])
        v['close'][-1]-=1
        self.assertIsNone(calendar_snapshot(t,v,'12M','1M',m,n))
        t,v,m,n=self.annual();v['high'][4]=float('nan')
        self.assertIsNone(calendar_snapshot(t,v,'12M','1M',m,n))

    def test_historical_pages_unknown_zone_and_future_quote_do_not_gain_current_snapshot(self):
        t,v,m,n=self.annual()
        self.assertIsNone(calendar_snapshot(t,v,'12M','1M',m,n,before=stamp('2025-01-01')))
        self.assertIsNone(calendar_snapshot(t,v,'12M','1M',{**m,'regularMarketTime':n+1},n))
        self.assertIsNone(calendar_snapshot(t,v,'12M','1M',{**m,'exchangeTimezoneName':'Missing/Zone'},n))

    def test_new_york_week_uses_dst_calendar_boundary(self):
        z='America/New_York';t=[stamp('2026-03-02',z)];v={'open':[100],'high':[110],'low':[90],'close':[105],'volume':[50]}
        m={'exchangeTimezoneName':z,'regularMarketTime':stamp('2026-03-06T16:00',z)}
        result=calendar_snapshot(t,v,'1W','1W',m,stamp('2026-03-07',z))
        self.assertEqual(result['close_time'],stamp('2026-03-09',z))
        self.assertEqual(result['close_time']-result['bar'][0],167*3600)

    def test_provider_quote_timestamp_caps_snapshot_age_and_missing_volume_stays_unknown(self):
        t,v,m,n=self.annual();m['regularMarketTime']=stamp('2026-10-30T15:30');v['volume'][5]=None
        result=calendar_snapshot(t,v,'12M','1M',m,n)
        self.assertEqual(result['bar'][4],119);self.assertIsNone(result['bar'][5])
        self.assertEqual(result['as_of'],m['regularMarketTime'])



class YahooSnapshotIntegration(unittest.TestCase):
    def raw(self):
        times=[stamp(f'{year}-{month:02d}-01') for year,months in ((2025,range(1,13)),(2026,range(1,12))) for month in months]
        count=len(times)
        values={'open':[100]*count,'high':[120]*count,'low':[90]*count,'close':[110]*count,'volume':[5]*count}
        meta={'exchangeTimezoneName':'Asia/Kolkata','instrumentType':'INDEX','regularMarketTime':stamp('2026-11-18T15:30')}
        return {'chart':{'result':[{'timestamp':times,'indicators':{'quote':[values]},'meta':meta}]}}

    def test_completed_annual_rows_remain_separate_from_current_snapshot(self):
        from unittest.mock import patch,Mock
        from sector_heatmap.yahoo_chart import history
        response=Mock(status_code=200);response.json.return_value=self.raw()
        with patch('sector_heatmap.yahoo_chart.requests.get',return_value=response):
            data=history('^NSEI','12M',now=stamp('2026-11-19'))
        self.assertEqual(data['rows'],[[stamp('2025-01-01'),100,120,90,110,60]])
        snapshot=data['forming_snapshot'];self.assertEqual(snapshot['bar'],[stamp('2026-01-01'),100,120,90,110,55])
        self.assertEqual(data['close_times'][snapshot['bar'][0]],stamp('2027-01-01'))
        self.assertTrue(data['older_history'])

    def test_older_page_never_receives_present_period_snapshot(self):
        from unittest.mock import patch,Mock
        from sector_heatmap.yahoo_chart import history
        response=Mock(status_code=200);response.json.return_value=self.raw()
        with patch('sector_heatmap.yahoo_chart.requests.get',return_value=response):
            data=history('^NSEI','12M',now=stamp('2026-11-19'),before=stamp('2026-01-01'))
        self.assertNotIn('forming_snapshot',data)
        self.assertEqual(len(data['rows']),1)

if __name__=='__main__':unittest.main()
