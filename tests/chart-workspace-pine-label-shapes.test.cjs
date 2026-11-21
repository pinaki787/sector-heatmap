
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../chart-workspace.js'),'utf8');
const markers=source.slice(source.indexOf('  const pineMarkerPolygons'),source.indexOf('  function isPineArrowPlot'));
const renderers=source.slice(source.indexOf('  function drawPineMarker'),source.indexOf('  function drawPinePolyline'));
const scope={pineDrawingTextSizes:{normal:14}};
vm.createContext(scope);vm.runInContext(markers+renderers+';globalThis.styles=Object.keys(pineNativeLabelMarkers);',scope);
test('native Pine shape labels render without text and preserve shape and text colors',()=>{
  for(const style of scope.styles) {
    const paints=[],text=[];
    const ctx=new Proxy({fillStyle:'',strokeStyle:'',save(){},restore(){},fill(){paints.push(this.fillStyle)},
      stroke(){paints.push(this.strokeStyle)},fillRect(){throw Error('native marker became a rectangular label')},
      fillText(value){text.push({value,color:this.fillStyle})},measureText:value=>({width:value.length*8})},
      {get:(target,key)=>key in target?target[key]:(()=>{})});
    const label={style,color:'#123456',textcolor:'#fedcba',size:'normal'};
    const empty=scope.drawPineLabel(ctx,label,100,100);
    assert.ok(paints.includes('#123456'),style+' must paint its shape color');
    assert.ok(empty.left<100 && empty.top<100 && empty.left+empty.width>100 && empty.top+empty.height>100);
    const caption=scope.drawPineLabel(ctx,{...label,text:'signal'},100,100);
    assert.deepEqual(text,[{value:'signal',color:'#fedcba'}]);
    assert.ok(caption.top<empty.top,style+' tooltip includes the caption');
  }
});

