/* One maintained Sector Pulse program. The chart evaluator projects its sections
   onto their verified clock domains (completed Renko / regular broker candles).
   These are internal evaluation passes, not separately installed indicators. */
(function(root){'use strict';
const marker='SP_UNIFIED_SECTOR_PULSE_20261128';
function body(source){return source.replace(/^\/\/@version=.*\n/,'').replace(/^indicator\([^\n]*\)\s*\n/m,'');}
function section(source,name){
 const a=source.indexOf('// SP_BEGIN_'+name+'\n'),b=source.indexOf('// SP_END_'+name,a);
 if(a<0||b<a)throw Error('Sector Pulse source section is missing: '+name);
 return source.slice(a+('// SP_BEGIN_'+name+'\n').length,b);
}
function header(source){return source.match(/^indicator\([^\n]*\)/m)?.[0]||'indicator("Sector Pulse", overlay=true)';}
function supertrend(source){
 if(!source.includes(marker))return source;
 return '//@version=6\n'+section(source,'SUPERTREND').replace(/^\/\/ SP_COMPONENT_DECLARATION (.*)\n/,'$1\n');
}
function references(source){
 if(!source.includes(marker))throw Error('A unified Sector Pulse program is required.');
 return '//@version=6\n'+section(source,'REFERENCES').replace(/^\/\/ SP_COMPONENT_DECLARATION (.*)\n/,'$1\n');
}
const native=String.raw`
string sp_nativeGroup="Sector Pulse — Midline / RSI"
int sp_period=input.int(123,"Gaussian period",minval=5,maxval=500,group=sp_nativeGroup)
int sp_rsiLength=input.int(14,"RSI period",minval=1,maxval=500,group=sp_nativeGroup)
int sp_maLength=input.int(14,"RSI SMA period",minval=1,maxval=500,group=sp_nativeGroup)
bool sp_midVisible=input.bool(true,"Midline",group=sp_nativeGroup)
bool sp_rsiVisible=input.bool(true,"RSI Zones (Candles)",group=sp_nativeGroup)
float sp_beta=(1-math.cos(2*math.pi/sp_period))/(math.pow(2,1.0/3)-1)
float sp_alpha=-sp_beta+math.sqrt(sp_beta*sp_beta+2*sp_beta)
var float sp_g1=na
var float sp_g2=na
var float sp_g3=na
var int sp_trend=0
sp_g1 := na(sp_g1[1]) ? close : sp_alpha*close+(1-sp_alpha)*sp_g1[1]
sp_g2 := na(sp_g2[1]) ? close : sp_alpha*sp_g1+(1-sp_alpha)*sp_g2[1]
sp_g3 := na(sp_g3[1]) ? close : sp_alpha*sp_g2+(1-sp_alpha)*sp_g3[1]
sp_trend := not na(sp_g3[1]) and sp_g3!=sp_g3[1] ? (sp_g3>sp_g3[1]?1:-1) : sp_trend
float sp_rsi=ta.rsi(close,sp_rsiLength)
float sp_rsiMa=ta.sma(sp_rsi,sp_maLength)
plot(sp_midVisible?sp_g3:na,"Market Min Midline",color=sp_trend>0?#2ea043:sp_trend<0?#e53935:#ffb84d,linewidth=2,force_overlay=true)
bool sp_showRsi=sp_rsiVisible and chart.is_standard
plot(sp_showRsi?sp_rsi:na,"RSI",color=#7e57c2,linewidth=2)
plot(sp_showRsi?sp_rsiMa:na,"RSI SMA",color=#ff0000,linewidth=2)
sp_z0=plot(sp_showRsi?0:na,"0",color=na)
sp_z40=plot(sp_showRsi?40:na,"40",color=#000000)
sp_z60=plot(sp_showRsi?60:na,"60",color=#000000)
sp_z80=plot(sp_showRsi?80:na,"80",color=#000000)
sp_z100=plot(sp_showRsi?100:na,"100",color=na)
fill(sp_z0,sp_z40,color=#ff000059)
fill(sp_z40,sp_z60,color=#80808059)
fill(sp_z60,sp_z80,color=#00800059)
fill(sp_z80,sp_z100,color=#00800059)
fill(sp_z80,sp_z100,color=#ff000040)
`;
function baseCleanReference(source){
 return source.split('\n').map(line=>line.trim().startsWith('string caption = rzLabels ?')&&line.includes('rzSourceTf')&&line.includes('str.tostring(z.lo')
  ?line.slice(0,line.length-line.trimStart().length)+'string caption = rzLabels ? (z.side == 1 ? "DEMAND" : "SUPPLY")+" OB · "+(z.state == 2 ? "Invalidated" : z.touching ? "Retesting" : z.tests > 0 ? "Retested" : "Fresh") : ""':line).join('\n');
}
function extendReferenceGrid(source){
 if(source.includes('SP_UNBOUNDED_TARGET_GRID_V1'))return source;
 if(!source.includes('type TargetSession')||!source.includes('f_targetSegment('))return source;
 return source.replace('type TargetSession',"// SP_UNBOUNDED_TARGET_GRID_V1\ntype SPXTarget\n    float hi\n    float lo\n    int key\n    int n\n    bool upper\n    int reveal\n    int hit\n    int finish\nvar array<SPXTarget> spxTargets=array.new<SPXTarget>()\nvar int spxUpMax=0\nvar int spxDnMax=0\n"+'\n'+'type TargetSession').replace('f_targetSegment(int left',"// Logical grid indices are unbounded; retain only nearby drawing evidence.\nif newSession\n    spxUpMax := 0\n    spxDnMax := 0\nif active and array.size(targetSessions)>0\n    TargetSession spxRec=array.last(targetSessions)\n    float spxSpan=spxRec.hi-spxRec.lo\n    if spxSpan>0\n        spxUpMax := math.max(spxUpMax,int(math.floor((high-spxRec.hi)/spxSpan)))\n        spxDnMax := math.max(spxDnMax,int(math.floor((spxRec.lo-low)/spxSpan)))\n        for spxSide=0 to 1\n            bool spxUpper=spxSide==0\n            int spxAchieved=spxUpper ? spxUpMax : spxDnMax\n            if (spxUpper or bothDirections) and spxAchieved>=targetCount-forward\n                int spxFirst=math.max(targetCount+1,spxAchieved-8)\n                int spxLast=math.max(spxFirst,spxAchieved+forward)\n                if array.size(spxTargets)>0\n                    for spxJ=array.size(spxTargets)-1 to 0\n                        SPXTarget spxOld=array.get(spxTargets,spxJ)\n                        if spxOld.key==spxRec.key and spxOld.upper==spxUpper and spxOld.n<spxFirst\n                            array.remove(spxTargets,spxJ)\n                for spxN=spxFirst to spxLast\n                    SPXTarget spxFound=na\n                    for spxItem in spxTargets\n                        if spxItem.key==spxRec.key and spxItem.upper==spxUpper and spxItem.n==spxN\n                            spxFound:=spxItem\n                    float spxPrice=spxUpper ? spxRec.hi+spxN*spxSpan : spxRec.lo-spxN*spxSpan\n                    bool spxHit=spxUpper ? high>=spxPrice : low<=spxPrice\n                    if na(spxFound)\n                        spxFound:=SPXTarget.new(spxRec.hi,spxRec.lo,spxRec.key,spxN,spxUpper,time,spxHit ? time : na,time)\n                        array.push(spxTargets,spxFound)\n                    else\n                        spxFound.finish:=time\n                        if spxHit and na(spxFound.hit)\n                            spxFound.hit:=time\n                while array.size(spxTargets)>120\n                    array.shift(spxTargets)\n"+'\n'+'f_targetSegment(int left').replace('// Shared TradingView object budget: keep newest targetLines.',"// Render the retained window using the original anchor and span.\nif barstate.islast and showTargets and targetMode!=\"OFF\"\n    for spxItem in spxTargets\n        float spxSpan=spxItem.hi-spxItem.lo\n        float spxPrice=spxItem.upper ? spxItem.hi+spxItem.n*spxSpan : spxItem.lo-spxItem.n*spxSpan\n        color spxReached=spxItem.upper ? upperColor : lowerColor\n        if na(spxItem.hit)\n            f_targetSegment(spxItem.reveal,spxItem.finish,spxPrice,spxSpan,pendingColor)\n        else\n            if spxItem.hit>spxItem.reveal\n                f_targetSegment(spxItem.reveal,spxItem.hit,spxPrice,spxSpan,pendingColor)\n            f_targetSegment(math.max(spxItem.reveal,spxItem.hit),spxItem.finish,spxPrice,spxSpan,spxReached)\n        if targetLabels\n            array.push(targetText,label.new(spxItem.finish,spxPrice,\"T\"+str.tostring(spxItem.n),xloc=xloc.bar_time,style=label.style_label_left,color=color.new(color.black,100),textcolor=na(spxItem.hit) ? pendingColor : spxReached,size=size.tiny,force_overlay=true))\n"+'\n'+'// Shared TradingView object budget: keep newest targetLines.');
}
function cleanReference(source){return extendReferenceGrid(baseCleanReference(source));}
function build(superSource,referenceSource){
 const rawReference=referenceSource.split('// RSI Zones — separate indicator pane.')[0];
 if(superSource.includes(marker)){
  const prior=references(superSource).trimEnd();
  // Upgrade our unchanged maintained reference body; preserve imported edits.
  if(prior!==rawReference.trimEnd()&&prior!==baseCleanReference(rawReference).trimEnd()&&prior!==cleanReference(rawReference).trimEnd())return superSource;
  if(section(superSource,'NATIVE').trim()!==native.trim())return superSource;
  superSource=supertrend(superSource);
 }
 const ref=cleanReference(rawReference);
 // One declaration; all Supertrend price plots explicitly target the main pane.
 const priceBody=body(superSource).trimEnd().replace(/\bplot(?:shape)?\([^\n]*\)/g,call=>call.includes('force_overlay=')?call:call.replace(/\)$/,', force_overlay=true)'));
 return '//@version=6\nindicator("Sector Pulse", overlay=false, behind_chart=true, precision=2, max_lines_count=500, max_labels_count=500, max_boxes_count=500, max_bars_back=5000)\n// '+marker+
 '\n// One indicator. Runtime broker-clock projections and historical viewport/cache are browser infrastructure.\n'+
 '// SP_BEGIN_SUPERTREND\n// SP_COMPONENT_DECLARATION '+header(superSource)+'\n'+priceBody+'\n// SP_END_SUPERTREND\n'+
 '// SP_BEGIN_REFERENCES\n// SP_COMPONENT_DECLARATION '+header(ref)+'\n'+body(ref).trimEnd()+'\n// SP_END_REFERENCES\n'+
 '// SP_BEGIN_NATIVE\n'+native+'\n// SP_END_NATIVE\n';
}
root.SectorPulseUnifiedSource={marker,build,supertrend,references,native,section,cleanReference};
})(typeof window==='undefined'?globalThis:window);
