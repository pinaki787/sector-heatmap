const test=require("node:test"),assert=require("node:assert/strict"),vm=require("node:vm"),fs=require("node:fs"),acorn=require("acorn");
const ctx=vm.createContext({});vm.runInContext(fs.readFileSync("scripts/pine_request_guard_projection.js","utf8"),ctx);
function project(code){const ast=acorn.parse(code,{ecmaVersion:"latest"});return ctx.spProjectRequestGuards(ast.body);}
const error="const p=runtime.param(\"guard\",undefined,\"p1\");const temp=runtime.error(p);temp;";
test("independent read-only top-level chart guard is omitted from request projection",()=>assert.equal(project(`if(barstate.isfirst && !timeframe.isintraday){${error}}`).length,0));
test("nested guard and timeframe calls are omitted",()=>assert.equal(project(`if(barstate.isfirst){if(!timeframe.isintraday || timeframe.in_seconds()>$.get(ref,0)){${error}}}`).length,0));
test("guard inside requested function remains intact",()=>assert.equal(project(`function requested(){if(!timeframe.isintraday){${error}}return high;}`).length,1));
test("state mutation in a guard is preserved",()=>assert.equal(project(`if(!timeframe.isintraday){state++;${error}}`).length,1));
test("unknown condition function is preserved",()=>assert.equal(project(`if(check()){${error}}`).length,1));
test("side-effectful error argument is preserved",()=>assert.equal(project(`if(!timeframe.isintraday){const p=runtime.param(changeState());const t=runtime.error(p);t;}`).length,1));
test("requested expression branch is preserved",()=>assert.equal(project(`if(!timeframe.isintraday){${error}}else{const value=request.security(a,b,c);}`).length,1));
test("original host AST is not mutated",()=>{const ast=acorn.parse(`if(!timeframe.isintraday){${error}}`,{ecmaVersion:"latest"});const before=JSON.stringify(ast);ctx.spProjectRequestGuards(ast.body);assert.equal(JSON.stringify(ast),before)});
test("compiler comparison helpers and timeframe arguments remain pure",()=>assert.equal(project(`if($.pine.math.__gt(timeframe.in_seconds(),timeframe.in_seconds(timeframe.param(ref,undefined,"p")))){${error}}`).length,0));
