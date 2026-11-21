const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8'),start=s.indexOf('  function pineDiagnosticLine('),end=s.indexOf('  function showScriptDiagnostic(',start);assert.ok(start>=0&&end>start);const line=vm.runInNewContext(s.slice(start,end)+';pineDiagnosticLine');
for(const [message,expected] of [
['Line 2: invalid indicator argument',2],
["Failed to transpile Pine Script version 6: Unexpected token EOF '' at 6:11",6],
['Failed to transpile Pine Script version 5: Unexpected token\ncontext at 42:9',42],
['ta.nonexistent is not a function',undefined],
['Expected recovery probe',undefined],
['The price at 6:11 is missing',undefined],
['Line 0: invalid location',undefined],
['Failed to transpile Pine Script version 6: error at 999999999999999999:1',undefined]
])test(message.slice(0,70),()=>assert.equal(line(message),expected));
