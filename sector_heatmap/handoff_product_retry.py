"""One narrowly classified product correction, never a generic rejection retry."""
EXPLICIT_REASONS={
 'this instrument is allowed only for intraday trading.',
 'this scrip is allowed only for intraday trading.',
 'overnight product is not allowed. only intraday product is allowed.',
}
def restriction(row):
    # Only exact broker-origin rejection fields are inspected. Unknown wording
    # fails closed; no fuzzy substring classification or user prose authorizes it.
    return row.get('rejectReasonCode')=='INTRADAY_ONLY' or str(row.get('message') or row.get('rejectReason') or '').strip().lower() in EXPLICIT_REASONS
def eligible(preview,result,book,positions):
    if result.get('status')!='REJECTED' or preview.get('order_policy',{}).get('product_type') not in ('MARGIN','CNC'):return False
    contracts=preview.get('instrument',{}).get('contracts',[]);ids=result.get('order_ids',[])
    if len(contracts)!=1 or len(ids)!=1 or book.get('s')!='ok' or positions.get('s')!='ok':return False
    leg=contracts[0];rows=[r for r in book.get('orderBook',[]) if str(r.get('id'))==str(ids[0])]
    if len(rows)!=1:return False
    row=rows[0]
    try:
        if row.get('status')!=5 or float(row.get('filledQty',-1))!=0 or float(row.get('remainingQuantity',-1))!=0 or row.get('symbol')!=leg['symbol'] or row.get('productType')!=preview['order_policy']['product_type'] or float(row.get('qty',-1))!=leg['quantity'] or row.get('side')!=(1 if leg['action']=='BUY' else -1):return False
        if not restriction(row):return False
        if any(r.get('symbol')==leg['symbol'] and float(r.get('netQty',0))!=0 for r in positions.get('netPositions',[])):return False
        if any(r.get('symbol')==leg['symbol'] and r.get('status') in (3,4,6) for r in book.get('orderBook',[])):return False
    except (ValueError,TypeError,KeyError):return False
    return True
