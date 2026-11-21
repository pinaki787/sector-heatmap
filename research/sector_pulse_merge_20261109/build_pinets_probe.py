"""Build the isolated PineTS 0.13.1 runtime for the V1 archive replay."""
import argparse
from hashlib import sha256
from pathlib import Path

SOURCE_SHA = 'dbc3e05a33a127e784737e90991cbb0bad85204b7e2cae167dd0f1e0678e7379'
OUTPUT_SHA = '2c10e84907f1e3f579b68e4e36ccceb84f918ac0ffdf031151ca4f4c726c9d64'

PATCHES = (
    (
        'Request tuple values',
        'function Pg(t){return(e,i,r)=>{t.params[r]||(t.params[r]=[]);let n;if(e instanceof y)n=e.get(i||0);else if(Array.isArray(e)){const s=e.some(o=>o instanceof y),a=e.every(o=>!(o instanceof y)&&!Array.isArray(o));(s||a)&&e.length>=1?n=e.map(o=>o instanceof y?o.get(0):o):n=y.from(e).get(i||0)}else n=e;return t.params[r].length===0?t.params[r].push(n):t.params[r][t.params[r].length-1]=n,t._requestParamSources||(t._requestParamSources={}),t._requestParamSources[r]=e,[n,r]}}',
        'function Pg(t){return(e,i,r)=>{t.params[r]||(t.params[r]=[]);let n;if(e instanceof y)n=e.get(i||0);else if(Array.isArray(e)){const s=e.some(o=>o instanceof y),a=e.every(o=>!(o instanceof y)&&!Array.isArray(o));(s||a)&&e.length>=1?n=e.map(o=>o instanceof y?o.get(0):o):n=y.from(e).get(i||0)}else n=e;const scalar=x=>{while(x instanceof y||x!==null&&typeof x==="object"&&"__value"in x)x=x instanceof y?x.get(0):x.__value;return x};n=Array.isArray(n)?n.map(scalar):scalar(n);return t.params[r].length===0?t.params[r].push(n):t.params[r][t.params[r].length-1]=n,t._requestParamSources||(t._requestParamSources={}),t._requestParamSources[r]=e,[n,r]}}',
    ),
    (
        'Positional request objects',
        'function Vg(t){return async(...e)=>{const i=[],r=Og(e,i),n=ye(r,gc,Rg),s=Yi(n.symbol),a=Yi(n.timeframe),o=Yi(n.expression),l=Yi(n.gaps),c=Yi(n.lookahead),u=s instanceof y?s.get(0):s,h=typeof t.tickerId=="string"&&t.tickerId.includes(":")?t.tickerId.split(":")[1]:t.tickerId,p=typeof h=="string"?$i(h):{symbol:h,modifier:null},f=p.modifier==="standard"?null:p.modifier,d=dc(u===""?t.tickerId:u),g=typeof d=="string"&&d.includes(":")?d.split(":")[1]:d,m=a instanceof y?a.get(0):a,_=m===""?t.timeframe:typeof m=="string"?m:String(m??""),v=o,E=jg("expression",gc,i,n.expression),N=l,w=c,T=N===!0||N==="gaps_on",k=w===!0||w==="lookahead_on",F=Yi(n.ignore_invalid_symbol)===!0,L=(()=>{const Re=Yi(n.calc_bars_count);return typeof Re=="number"&&Re>0?Math.min(Re,kl):void 0})();',
        'function Vg(t){return async(...e)=>{const i=[],r=Og(e,i);if(i[2]!==void 0&&r[2]!==null&&typeof r[2]==="object"&&!Array.isArray(r[2])&&!(r[2] instanceof y))r[2]=new y([r[2]]);const n=ye(r,gc,Rg),s=Yi(n.symbol),a=Yi(n.timeframe),o=Yi(n.expression),l=Yi(n.gaps),c=Yi(n.lookahead),u=s instanceof y?s.get(0):s,h=typeof t.tickerId=="string"&&t.tickerId.includes(":")?t.tickerId.split(":")[1]:t.tickerId,p=typeof h=="string"?$i(h):{symbol:h,modifier:null},f=p.modifier==="standard"?null:p.modifier,d=dc(u===""?t.tickerId:u),g=typeof d=="string"&&d.includes(":")?d.split(":")[1]:d,m=a instanceof y?a.get(0):a,_=m===""?t.timeframe:typeof m=="string"?m:String(m??""),v=o,E=jg("expression",gc,i,n.expression),N=l,w=c,T=N===!0||N==="gaps_on",k=w===!0||w==="lookahead_on",F=Yi(n.ignore_invalid_symbol)===!0,L=(()=>{const Re=Yi(n.calc_bars_count);return typeof Re=="number"&&Re>0?Math.min(Re,kl):void 0})();',
    ),
    (
        'Daily session close',
        'class Ll{constructor(e,i="openTime"){yr(this,"context"),yr(this,"dataField"),this.context=e,this.dataField=i}get __value(){return this.context.data[this.dataField]}param(e,i=0){return y.from(e).get(i)}any(...e){const i=Vl(e),r=ye(i,xy,vy),n=r.bars_back??0,s=r.timeframe||"",a=this.context.data[this.dataField],o=y.from(a).get(n);if(isNaN(o)||o==null)return NaN;let l;if(!s||ma(s)===ma(this.context.timeframe))l=o;else{const c=Ge(s);if(!c)throw new le(`Cannot parse resolution \'${s}\'. - Invalid format`,"time");const u=this.context.pine?.syminfo;l=yy(o,c,u?.timezone||"UTC",u?.session)}if(r.session!==void 0&&r.session!==""){const c=r.timezone||this.context.pine?.syminfo?.timezone||"UTC";return this._isInSession(l,r.session,c)?l:NaN}return l}',
        'class Ll{constructor(e,i="openTime"){yr(this,"context"),yr(this,"dataField"),this.context=e,this.dataField=i}get __value(){return this.context.data[this.dataField]}param(e,i=0){return y.from(e).get(i)}any(...e){const i=Vl(e),r=ye(i,xy,vy),n=r.bars_back??0,s=r.timeframe||"",a=this.context.data[this.dataField],o=y.from(a).get(n);if(isNaN(o)||o==null)return NaN;let l;if(!s||ma(s)===ma(this.context.timeframe))l=o;else{const c=Ge(s);if(!c)throw new le(`Cannot parse resolution \'${s}\'. - Invalid format`,"time");const u=this.context.pine?.syminfo;l=yy(o,c,u?.timezone||"UTC",u?.session);if(this.dataField==="closeTime"&&c.unit==="D"&&(s==="1D"||s==="D")){const zone=r.timezone||u?.timezone||"UTC";const session=r.session||u?.session;const open=y.from(this.context.data.openTime).get(n);const end=Il(session||"")?.windows.at(-1)?.end??1440;const tradeDay=_a(open,c,zone,session);const date=new Date(tradeDay+Math.floor(end/1440)*864e5).toISOString().slice(0,10);const minute=end%1440;const clock=String(Math.floor(minute/60)).padStart(2,"0")+":"+String(minute%60).padStart(2,"0");l=It(date,clock,zone)}}if(r.session!==void 0&&r.session!==""){const c=r.timezone||this.context.pine?.syminfo?.timezone||"UTC";return this._isInSession(l,r.session,c)?l:NaN}return l}',
    ),
    (
        'User-defined type fields',
        'class Ft{constructor(e,i,r){this._definition=e,this.context=i,of(this,"_udt");for(let n in e)this[n]=e[n];this._udt=r}',
        'class Ft{constructor(e,i,r){this._definition=e,this.context=i,of(this,"_udt");this._udt=r;for(const n of new Set([...(r?._definitionKeys??[]),...Object.keys(e)])){let v;Object.defineProperty(this,n,{enumerable:true,configurable:true,get:()=>v,set:x=>{while(x instanceof y||x!==null&&typeof x==="object"&&"__value"in x)x=x instanceof y?x.get(0):x.__value;v=x}});this[n]=e[n]}}',
    ),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Official PineTS 0.13.1 browser bundle")
    parser.add_argument("output", type=Path, help="New file for the patched research bundle")
    parser.add_argument("--worker", action="store_true",
                        help="Append the chart worker message handler")
    args = parser.parse_args()
    raw = args.bundle.read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA:
        parser.error("Expected the pinned PineTS 0.13.1 browser bundle")
    source = raw.decode("utf-8")
    for description, before, after in PATCHES:
        if source.count(before) != 1:
            parser.error("Could not apply patch: " + description)
        source = source.replace(before, after)
    result = source.encode("utf-8")
    if sha256(result).hexdigest() != OUTPUT_SHA:
        parser.error("Patched bundle did not match the verified output")
    if args.worker:
        result += b"\n" + Path(__file__).with_name("pine_replay_worker.js").read_bytes()
    with args.output.open("xb") as output:
        output.write(result)


if __name__ == "__main__":
    main()
