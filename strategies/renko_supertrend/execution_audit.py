"""Display owned fills against a candidate's candle, retaining the first assessment."""

def entry_orders(event, orders, seconds):
    matches=[]
    for row in orders:
        if row.get('run_id')!=event.get('run_id') or not row.get('is_entry',row.get('side')=='BUY'):continue
        stamp=row.get('entry_event_at')
        if event.get('provisional'):
            direction=((row.get('indicator_snapshot') or {}).get('indicators') or {}).get('direction')
            direction=direction or {'CE':'BULLISH','PE':'BEARISH','Call':'BULLISH','Put':'BEARISH'}.get(row.get('option_type'))
            if row.get('entry_mode')!='INTRABAR' or stamp is None or int(stamp//seconds)*seconds!=event.get('timestamp') or direction!=event.get('direction'):continue
        elif stamp!=event.get('event_at'):continue
        matches.append(row)
    return matches
