function spProjectRequestDependencies(statements) {
  if (!Array.isArray(statements) || !statements.length) return statements;
  const slot = n => n?.type === 'MemberExpression' && !n.computed &&
    n.object?.type === 'MemberExpression' && !n.object.computed &&
    n.object.object?.type === 'Identifier' && n.object.object.name === '$' &&
    ['let','var','const','params'].includes(n.object.property?.name) &&
    n.property?.type === 'Identifier' ? 'slot:'+n.object.property.name+'.'+n.property.name : null;
  const member = (n,object,name) => n?.type==='MemberExpression' && !n.computed &&
    n.object?.type==='Identifier' && n.object.name===object && n.property?.name===name;
  const binds = (n,out) => {
    if(!n)return;
    if(n.type==='Identifier')out.add('id:'+n.name);
    else if(n.type==='ObjectPattern')for(const p of n.properties||[])binds(p.value||p.argument,out);
    else if(n.type==='ArrayPattern')for(const p of n.elements||[])binds(p,out);
    else if(n.type==='AssignmentPattern')binds(n.left,out);
    else if(n.type==='RestElement')binds(n.argument,out);
  };
  const references = (node,out) => {
    if(!node||typeof node!=='object')return;
    const s=slot(node);if(s){out.add(s);return}
    if(node.type==='Identifier'){out.add('id:'+node.name);return}
    for(const [key,value] of Object.entries(node)){
      if(['parent','loc','range','start','end','raw'].includes(key))continue;
      if((node.type==='MemberExpression' && key==='property' && !node.computed) ||
         (node.type==='Property' && key==='key' && !node.computed))continue;
      if(Array.isArray(value))for(const v of value)references(v,out);
      else if(value&&typeof value==='object')references(value,out);
    }
  };
  const facts=statements.map(node=>({node,reads:new Set(),writes:new Set(),calls:new Set(),always:false}));
  const functions=new Map();
  const readonlyBindings=new Set(['id:$','id:$$','id:undefined','id:NaN','id:Infinity']);
  for(const statement of statements){
    if(statement.type!=='VariableDeclaration')continue;
    for(const decl of statement.declarations||[]){
      const init=decl.init;
      if(init?.type==='MemberExpression'&&!init.computed&&init.object?.type==='Identifier'&&
         init.object.name==='$'&&['data','pine'].includes(init.property?.name))binds(decl.id,readonlyBindings);
    }
  }
  const mutationTargets=new WeakMap();
  const mutation=(node,out)=>{
    const refs=new Set();references(node,refs);
    let targets=mutationTargets.get(out);if(!targets){targets=new Set();mutationTargets.set(out,targets)}
    for(const ref of refs){if(readonlyBindings.has(ref))continue;out.add(ref);targets.add(ref)}
  };
  function writes(node,out,calls,top=true){
    if(!node||typeof node!=='object')return;
    if(node.type==='FunctionDeclaration'){
      if(top&&node.id)out.add('id:'+node.id.name);
      return;
    }
    if(node.type==='VariableDeclaration')for(const d of node.declarations||[])binds(d.id,out);
    if(['AssignmentExpression','UpdateExpression'].includes(node.type)){
      const target=node.left||node.argument;
      if(target?.type==='Identifier')out.add('id:'+target.name);
      else mutation(target,out);
    }
    if(['CallExpression','OptionalCallExpression'].includes(node.type)){
      let callee=node.callee;
      while(callee?.type==='ChainExpression')callee=callee.expression;
      if(member(callee,'$','set'))mutation(node.arguments?.[0],out);
      if(member(callee,'$','call')&&node.arguments?.[0]?.type==='Identifier'){
        calls.add(node.arguments[0].name);
        for(const arg of node.arguments.slice(2)) {
          mutation(arg,out);
        }
      }
      // Instance and user-defined methods can mutate their receiver.
      // Namespace receivers are filtered by readonlyBindings in mutation().
      if(['MemberExpression','OptionalMemberExpression'].includes(callee?.type))mutation(callee.object,out);
      const mutate=new Set(['push','pop','shift','unshift','clear','set','insert','remove','fill','reverse','sort','concat']);
      if(callee?.type==='MemberExpression'&&!callee.computed&&callee.object?.type==='Identifier'&&
         callee.object.name==='array'&&mutate.has(callee.property?.name)) {
        mutation(node.arguments?.[0],out);
      }
    }
    for(const [key,value] of Object.entries(node)){
      if(['parent','loc','range','start','end','raw'].includes(key))continue;
      if(Array.isArray(value))for(const v of value)writes(v,out,calls,false);
      else if(value&&typeof value==='object')writes(value,out,calls,false);
    }
  }
  for(const f of facts){
    references(f.node,f.reads);writes(f.node,f.writes,f.calls);
    const localBindings=new Set();
    const collectLocal=node=>{
      if(!node||typeof node!=='object')return;
      if(node.type==='VariableDeclarator')binds(node.id,localBindings);
      if(node.type==='FunctionDeclaration'||node.type==='FunctionExpression'||node.type==='ArrowFunctionExpression'){
        if(node.id)binds(node.id,localBindings);
        for(const parameter of node.params||[])binds(parameter,localBindings);
      }
      for(const [key,value]of Object.entries(node)){
        if(['parent','loc','range','start','end','raw'].includes(key))continue;
        if(Array.isArray(value))for(const v of value)collectLocal(v);
        else if(value&&typeof value==='object')collectLocal(value);
      }
    };
    collectLocal(f.node);
    for(const name of localBindings)f.reads.delete(name);
    if(!['VariableDeclaration','FunctionDeclaration'].includes(f.node.type))
      for(const name of localBindings)f.writes.delete(name);

    if(f.node.type==='FunctionDeclaration'&&f.node.id){
      const effects={writes:new Set(),calls:new Set()};
      writes(f.node.body,effects.writes,effects.calls,false);
      functions.set(f.node.id.name,effects);
    }
    const e=f.node.type==='ExpressionStatement'?f.node.expression:null;
    f.always=!!(e?.type==='CallExpression'&&
      (e.callee?.type==='Identifier'&&['indicator','max_bars_back'].includes(e.callee.name)));
  }
  const aliases=new Map();
  const findAliases=node=>{
    if(!node||typeof node!=='object')return;
    if(node.type==='VariableDeclarator'&&node.init){
      const names=new Set(),refs=new Set();binds(node.id,names);references(node.init,refs);
      for(const name of names){const prior=aliases.get(name)||new Set();for(const ref of refs)prior.add(ref);aliases.set(name,prior)}
    }
    if(node.type==='ForOfStatement'||node.type==='ForInStatement'){
      const names=new Set(),refs=new Set();
      for(const d of node.left?.declarations||[])binds(d.id,names);
      references(node.right,refs);
      for(const name of names)aliases.set(name,refs);
    }
    for(const [key,value]of Object.entries(node)){
      if(['parent','loc','range','start','end','raw'].includes(key))continue;
      if(Array.isArray(value))for(const v of value)findAliases(v);
      else if(value&&typeof value==='object')findAliases(value);
    }
  };
  for(const f of facts)findAliases(f.node);
  const expand=writes=>{
    const pending=[...(mutationTargets.get(writes)||[])],seen=new Set(pending);
    while(pending.length){
      for(const ref of aliases.get(pending.pop())||[]){
        if(ref.startsWith('slot:'))writes.add(ref);
        if(!seen.has(ref)){seen.add(ref);pending.push(ref)}
      }
    }
  };
  for(const f of facts)expand(f.writes);
  for(const e of functions.values())expand(e.writes);
  for(let pass=0;pass<=functions.size;pass++){
    let changed=false;
    for(const e of functions.values())for(const name of e.calls){
      for(const w of functions.get(name)?.writes||[])if(!e.writes.has(w)){e.writes.add(w);changed=true}
    }
    if(!changed)break;
  }
  for(const f of facts)for(const name of f.calls)
    for(const w of functions.get(name)?.writes||[])if(w.startsWith('slot:'))f.writes.add(w);
  const keep=new Set([facts.length-1]),needed=new Set();
  for(const f of facts)if(f.always)keep.add(f);
  // Work to a fixed point so persistent updates after initialization remain live.
  let changed=true;
  while(changed){
    changed=false;
    for(let i=facts.length-1;i>=0;i--){
      const f=facts[i];
      if(keep.has(i)||keep.has(f)||[...f.writes].some(w=>needed.has(w))){
        if(!keep.has(i)){keep.add(i);changed=true}
        for(const r of f.reads)if(!needed.has(r)){needed.add(r);changed=true}
      }
    }
  }
  return facts.filter((f,i)=>keep.has(i)).map(f=>f.node);
}
