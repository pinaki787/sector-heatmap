"""Lossless, connection-scoped browser state updates. No trading or data truncation."""
import json
from copy import deepcopy


def wire(value):
    return json.dumps(value,allow_nan=False,separators=(',',':'))


class StateDelta:
    def __init__(self, *, take_ownership=False):
        # Producers may transfer their already isolated per-message snapshots.
        self.take_ownership=take_ownership
        self.previous=None
        self.sequence=0
        self.arrays={}

    def encode(self, frame):
        return 'event: state-delta\ndata: '+wire(self.payload(frame))+'\n\n'

    def payload(self, frame):
        self.sequence+=1
        if self.previous is None:
            result=dict(v=1,seq=self.sequence,full=frame)
        else:
            operations=[]
            arrays={}
            self._diff(self.previous,frame,[],operations,arrays)
            self.arrays=arrays
            result=dict(v=1,seq=self.sequence,base=self.sequence-1,ops=operations)
        self.previous=frame if self.take_ownership else deepcopy(frame)
        return result

    def _diff(self, before, after, path, ops, arrays):
        if type(before) is not type(after):
            ops.append(dict(op='set',path=path,value=after));return
        if isinstance(after,dict):
            for key in before.keys()-after.keys():
                ops.append(dict(op='remove',path=path+[key]))
            for key,value in after.items():
                if key not in before:ops.append(dict(op='set',path=path+[key],value=value))
                else:self._diff(before[key],value,path+[key],ops,arrays)
        elif isinstance(after,list):
            # Manager collections have stable small cardinality but large histories.
            # A price/P&L change must not replace an entire manager object.
            if len(before)==len(after)<=64 and all(isinstance(item,dict) for item in before+after):
                for index,(old,new) in enumerate(zip(before,after)):
                    self._diff(old,new,path+[index],ops,arrays)
                return
            key=tuple(path)
            old=self.arrays.get(key)
            if old is None:old=wire(before)
            new=wire(after)
            arrays[key]=new
            if old==new:return
            # Prefix/suffix preservation handles append, corrections and truncation.
            # Compare JSON representations to retain boolean/number distinctions.
            left=[wire(item) for item in before]
            right=[wire(item) for item in after]
            prefix=0
            while prefix<min(len(left),len(right)) and left[prefix]==right[prefix]:prefix+=1
            suffix=0
            while (suffix<min(len(left),len(right))-prefix
                   and left[len(left)-1-suffix]==right[len(right)-1-suffix]):suffix+=1
            ops.append(dict(op='splice',path=path,start=prefix,delete=len(left)-prefix-suffix,
                            items=after[prefix:len(right)-suffix if suffix else len(right)]))
        elif before!=after:
            ops.append(dict(op='set',path=path,value=after))


def compact_events(response):
    """Convert only opted-in state events. Preserve all other SSE events verbatim."""
    encoder=StateDelta(take_ownership=True)
    event=[]
    while True:
        line=response.readline()
        if not line:
            if event:yield b''.join(event)
            return
        event.append(line)
        if line not in (b'\n',b'\r\n'):continue
        kind=next((row[6:].strip() for row in event if row.startswith(b'event:')),b'message')
        data=[row[5:].lstrip(b' ').rstrip(b'\r\n') for row in event if row.startswith(b'data:')]
        if kind==b'state' and data:
            frame=json.loads(b'\n'.join(data))
            # Keep event IDs/retry policy, if an upstream adds them.
            for row in event:
                if row.startswith((b'id:',b'retry:')):yield row
            yield encoder.encode(frame).encode()
        else:
            yield b''.join(event)
        event=[]
