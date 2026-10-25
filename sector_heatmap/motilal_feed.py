"""Native MO broadcast packets with independent exchange/receipt freshness."""
from datetime import datetime
import math
import struct
import threading
import time
from zoneinfo import ZoneInfo
from .motilal_api import EXCHANGES

QUOTE_SOCKET='wss://ws1feed.motilaloswal.com/jwebsocket/jwebsocket'
ORDER_SOCKET='wss://openapi.motilaloswal.com/ws'
EPOCH_1980=datetime(1980,1,1,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
EXCHANGE_CODES={'NSE':b'N','NSEFO':b'N','BSE':b'B','BSEFO':b'G','NSECD':b'C','MCX':b'M'}


def login_packet(client_id):
    raw=client_id.encode('ascii');version=b'VER 2.0'
    if not 2<=len(raw)<=15:raise ValueError('Broadcast client code must fit the documented login packet.')
    return struct.pack('<cHB15sB30sBBBB10sBBBBB45s',b'Q',111,len(raw),raw.ljust(15,b' '),len(raw),raw.ljust(30,b' '),1,1,1,len(version),version.ljust(10,b' '),0,0,0,0,1,b' '*45)


def subscription_packet(exchange,token,subscribe=True):
    if exchange not in EXCHANGES:raise ValueError('Unsupported market-data exchange.')
    token=int(token)
    if not 0<token<2**31:raise ValueError('Invalid native scrip code.')
    return struct.pack('<cHcciB',b'D',7,EXCHANGE_CODES[exchange],b'C' if exchange in {'NSE','BSE'} else b'D',token,int(subscribe))


def decode_packet(packet):
    if len(packet)!=30:raise ValueError('MO broadcast frame must contain thirty bytes.')
    exchange,token,stamp,kind=struct.unpack('<cii c',packet[:10])
    stamp+=EPOCH_1980
    if kind in {b'A',b'H'}:
        price=struct.unpack_from('<f',packet,10)[0]
        if not math.isfinite(price) or price<=0:raise ValueError('Invalid native market price.')
        result=dict(code=exchange,token=token,exchange_at=stamp,kind='INDEX_LTP' if kind==b'H' else 'LTP',ltp=price)
        if kind==b'A':
            cumulative=struct.unpack_from('<i',packet,18)[0]
            if cumulative>=0:result['cumulative_volume']=cumulative
            interest=struct.unpack_from('<i',packet,26)[0]
            if interest>=0:result['open_interest']=interest
        return result
    if kind==b'B':
        bid,bid_qty,bid_orders,ask,ask_qty,ask_orders=struct.unpack('<fihfih',packet[10:])
        if not all(math.isfinite(v) and v>0 for v in [bid,ask]) or ask<bid or bid_qty<0 or ask_qty<0:
            raise ValueError('Invalid native market depth.')
        return dict(code=exchange,token=token,exchange_at=stamp,kind='DEPTH',bid=bid,ask=ask,bid_quantity=bid_qty,ask_quantity=ask_qty)
    return None


class QuoteFeed:
    def __init__(self, client, *, clock=time.time, socket_factory=None, on_tick=None, on_disconnect=None):
        self.client=client;self.clock=clock;self.socket_factory=socket_factory
        self.on_tick=on_tick;self.on_disconnect=on_disconnect;self.coverage_since=None
        self.lock=threading.RLock();self.start_lock=threading.Lock();self.callback_lock=threading.RLock()
        self.subscriptions={};self.indices={};self.index_coverage={};self.subscription_coverage={};self.quotes={};self.buffer=b''
        self.socket=None;self.connected=False;self.generation=0;self.lifecycle=0;self.error=None
        self.closed=threading.Event();self.thread=None

    def _send_subscription(self,socket,generation,exchange,token):
        import websocket
        socket.send(subscription_packet(exchange,token),opcode=websocket.ABNF.OPCODE_BINARY)
        with self.lock:
            if generation==self.generation and self.socket is socket and self.connected:
                self.subscription_coverage[(EXCHANGE_CODES[exchange],int(token))]=self.clock()

    def subscribe(self,exchange,token):
        subscription_packet(exchange,token)
        key=(EXCHANGE_CODES[exchange],int(token))
        with self.lock:
            previous=self.subscriptions.get(key)
            if previous and previous!=exchange:raise ValueError('Ambiguous native exchange/scrip identity; subscription blocked.')
            self.subscriptions[key]=exchange
            socket=self.socket if self.connected and key not in self.subscription_coverage else None
            generation=self.generation
        if socket:self._send_subscription(socket,generation,exchange,token)

    def subscribe_index(self,exchange,token):
        if exchange not in {'NSE','BSE'} or not 0<int(token)<2**31:raise ValueError('Invalid native index.')
        with self.lock:
            key=(EXCHANGE_CODES[exchange],int(token))
            if key not in self.indices:self.index_coverage[key]=self.clock()
            self.indices[key]=exchange

    def price(self,exchange,token,index=False):
        key=(EXCHANGE_CODES[exchange],int(token),'INDEX') if index else (EXCHANGE_CODES[exchange],int(token))
        with self.lock:item=dict(self.quotes.get(key) or {});connected=self.connected
        if not connected or any(not 0<=self.clock()-item.get(k,0)<=15 for k in ('ltp_exchange_at','ltp_received_at')):
            raise ValueError('Fresh native Motilal last price is unavailable.')
        return item['ltp'],item['ltp_exchange_at']

    def ingest(self,message,generation=None):
        if not isinstance(message,(bytes,bytearray)):return
        callbacks=[];heartbeats=0
        with self.lock:
            if generation is not None and generation!=self.generation:return
            self.buffer+=bytes(message)
            if len(self.buffer)>300000:
                self.buffer=b'';self.error='Broadcast buffer exceeded its limit.';return
            while len(self.buffer)>=30:
                packet,self.buffer=self.buffer[:30],self.buffer[30:]
                if packet[9:10]==b'1':heartbeats+=1;continue
                try:item=decode_packet(packet)
                except ValueError:self.error='Malformed market-data packet.';continue
                if not item:continue
                key=(item['code'],item['token']);is_index=item['kind']=='INDEX_LTP'
                exchange=(self.indices if is_index else self.subscriptions).get(key)
                if not exchange:continue
                coverage_key=key
                if is_index:key=(*key,'INDEX')
                now=self.clock()
                if not 0<=now-item['exchange_at']<=15:
                    self.error='Stale or future exchange timestamp; quote rejected.';continue
                snapshot=self.quotes.setdefault(key,{})
                field='depth' if item['kind']=='DEPTH' else 'ltp'
                if item['exchange_at']<snapshot.get(field+'_exchange_at',0):continue
                if field=='depth':snapshot.update(bid=item['bid'],ask=item['ask'],depth_exchange_at=item['exchange_at'],depth_received_at=now)
                else:snapshot.update(ltp=item['ltp'],ltp_exchange_at=item['exchange_at'],ltp_received_at=now,
                    cumulative_volume=item.get('cumulative_volume'),open_interest=item.get('open_interest'))
                self.error=None
                if field=='ltp':callbacks.append(dict(symbol=f'MO:{"INDEX:" if is_index else ""}{exchange}:{item["token"]}',ltp=item['ltp'],exch_feed_time=item['exchange_at'],
                    cumulative_volume=item.get('cumulative_volume'),is_index=is_index,
                    coverage_since=max(self.coverage_since or now,self.subscription_coverage.get(coverage_key,now) if not is_index else self.index_coverage.get(coverage_key,now))))
            socket=self.socket if self.connected else None;accepted_generation=self.generation
        if socket and heartbeats:
            import websocket
            for _ in range(heartbeats):socket.send(struct.pack('<cH',b'1',0),opcode=websocket.ABNF.OPCODE_BINARY)
        if self.on_tick:
            for item in callbacks:
                with self.callback_lock:
                    with self.lock:
                        if accepted_generation!=self.generation:return
                    self.on_tick(item)

    def _disconnected(self,generation):
        with self.lock:
            if generation!=self.generation:return
            was_connected=self.connected
            self.connected=False;self.coverage_since=None;self.subscription_coverage={};self.quotes={};self.buffer=b''
            self.error='Market-data connection closed; awaiting reconnect.'
        if was_connected and self.on_disconnect:
            with self.callback_lock:self.on_disconnect()

    def start(self):
        # Profile HTTP must not hold the quote lock or stall status/Stop readers.
        with self.start_lock:
            with self.lock:
                if self.thread and self.thread.is_alive():return
                lifecycle=self.lifecycle
            self.client.profile()
            with self.lock:
                if self.lifecycle!=lifecycle:return
                self.closed.clear();self.lifecycle+=1;lifecycle=self.lifecycle
            def run():
                import websocket
                factory=self.socket_factory or websocket.WebSocketApp;delay=1
                while not self.closed.is_set() and lifecycle==self.lifecycle:
                    with self.lock:self.generation+=1;generation=self.generation
                    def opened(socket,generation=generation):
                        with self.lock:
                            if generation!=self.generation or lifecycle!=self.lifecycle:return
                        socket.send(login_packet(self.client.client_id),opcode=websocket.ABNF.OPCODE_BINARY)
                        with self.lock:
                            if generation!=self.generation or lifecycle!=self.lifecycle:return
                            self.connected=True;self.coverage_since=self.clock();self.subscription_coverage={};self.quotes={};self.buffer=b''
                            subscriptions=list(self.subscriptions.items())
                        for (_,token),exchange in subscriptions:self._send_subscription(socket,generation,exchange,token)
                    def disconnected(*args,generation=generation):self._disconnected(generation)
                    def error(*args,generation=generation):
                        with self.lock:
                            if generation==self.generation:self.error='Motilal market-data transport error.'
                    socket=factory(QUOTE_SOCKET,on_open=opened,on_message=lambda ws,msg,generation=generation:self.ingest(msg,generation),on_close=disconnected,on_error=error)
                    with self.lock:
                        if lifecycle!=self.lifecycle:return
                        self.socket=socket
                    try:socket.run_forever(ping_interval=20,ping_timeout=10)
                    except Exception:error()
                    disconnected()
                    if self.closed.wait(delay):break
                    delay=min(delay*2,60)
            self.thread=threading.Thread(target=run,name='motilal-market-feed',daemon=True);self.thread.start()

    def quote(self,exchange,token):
        key=(EXCHANGE_CODES[exchange],int(token));now=self.clock()
        with self.lock:
            item=dict(self.quotes.get(key) or {});connected=self.connected
        if not connected:raise ValueError('Motilal market feed is disconnected.')
        if not all(0<=now-item.get(field,0)<=15 for field in ['depth_exchange_at','depth_received_at']):raise ValueError('Fresh Motilal market depth is unavailable.')
        return {**item,'source':'MOTILAL_NATIVE_DEPTH','received_at':item['depth_received_at'],'exchange_at':item['depth_exchange_at']}

    def stop(self):
        with self.lock:
            self.lifecycle+=1;self.generation+=1;self.closed.set();socket=self.socket
            self.socket=None;self.connected=False;self.coverage_since=None;self.subscription_coverage={};self.quotes={};self.buffer=b''
        if self.on_disconnect:
            with self.callback_lock:self.on_disconnect()
        if socket:threading.Thread(target=socket.close,name='motilal-feed-close',daemon=True).start()
