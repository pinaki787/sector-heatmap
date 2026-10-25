/* Socket-free integration: rendered selector -> router -> real handler -> Dhan data adapter.
 * Broker responses are deterministic fixtures; this does not claim a live broker check.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {spawnSync} = require('node:child_process');

const backend = String.raw`
import ast, copy, json, sys, threading
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch
from tests.test_dhan_sector_analysis import DhanSectorTests
from sector_heatmap.dhan_sector_analysis import DhanSectorAnalysisService
from sector_heatmap.sectors import SECTOR_DEFINITIONS
from sector_heatmap.section_permissions import allowed

fixture = DhanSectorTests()
fixture.setUp()
try:
    request = json.loads(sys.argv[1])
    user = {'id': 'owner', 'features': ['sectors']}
    account = fixture.execution.account
    def owned(current, aid):
        if current is not user or aid != account['id']:
            raise PermissionError('Account belongs to another user.')
        return account
    tree = ast.parse(Path('sector_heatmap/web.py').read_text())
    methods = [copy.deepcopy(node) for node in ast.walk(tree)
               if isinstance(node, ast.FunctionDef) and node.name in ('dhan_service', 'dhan_sector_analysis')]
    route = next(copy.deepcopy(node) for node in ast.walk(tree)
                 if isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                 and isinstance(node.test.left, ast.Name) and node.test.left.id == 'path'
                 and isinstance(node.test.comparators[0], ast.Set)
                 and any(isinstance(e, ast.Constant) and e.value == '/api/dhan/sector-analysis'
                         for e in node.test.comparators[0].elts))
    dispatch = ast.parse('def do_GET(self):\n    path = urlparse(self.path).path\n').body[0]
    dispatch.body.append(route)
    cls = ast.ClassDef(name='Handler', bases=[], keywords=[], body=methods+[dispatch], decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    env = dict(__package__='sector_heatmap', workspace_guard=None,
               local_auth=SimpleNamespace(authorize=lambda *args: user, store=SimpleNamespace(account=owned)),
               dhan_services={account['id']: fixture.execution}, dhan_services_lock=threading.RLock(),
               dhan_sector_services={}, urlparse=urlparse, parse_qs=parse_qs)
    exec(compile(module, 'real-dhan-http-handler', 'exec'), env)
    handler = env['Handler']()
    handler.path, handler.headers, handler.command = request['url'], {}, 'GET'
    response = []
    handler.send_json = lambda status, data: response.append({'status': status, 'body': data})
    if not allowed(user, urlparse(handler.path).path):
        handler.send_json(403, {'error': 'Section not assigned'})
    else:
        with patch.object(DhanSectorAnalysisService, 'start', lambda service: service.refresh()), \
             patch('sector_heatmap.sector_service.SECTOR_DEFINITIONS', SECTOR_DEFINITIONS[:1]):
            handler.do_GET()
    result = response[0]
    result['broker_paths'] = [path for _, path, _ in fixture.client.calls]
    print(json.dumps(result))
finally:
    fixture.doCleanups()
`;

function browser(accounts) {
  const nodes = new Map(), listeners = new Map(), requests = [];
  class Element {
    constructor(tag) { this.tagName=tag.toUpperCase(); this.children=[]; this.dataset={}; this.events={}; this._value=''; }
    set id(value) { this._id=value; nodes.set(value,this); }
    get id() { return this._id; }
    append(...items) { this.children.push(...items); }
    prepend(item) { this.children.unshift(item); }
    replaceChildren() { this.children=[]; this._value=''; }
    setAttribute() {}
    addEventListener(name,fn) { (this.events[name] ||= []).push(fn); }
    get value() { return this._value || this.children.find(n=>n.selected)?.value || this.children[0]?.value || ''; }
    set value(value) { this._value=value; }
    get selectedOptions() { return this.children.filter(n=>n.value===this.value); }
    closest() { return this.label; }
  }
  const bandLimit = new Element('input');
  bandLimit.id='ema-band-max-trades'; bandLimit.label={hidden:true};
  const filter = new Element('select');
  filter.label = {before() {}};
  const document = {
    body:{}, head:{append(){}}, createElement:tag=>new Element(tag),
    getElementById:id=>nodes.get(id), querySelectorAll:()=>[],
    querySelector:selector=>selector==='#sector-filter'?filter:null,
  };
  const location={href:'https://portal.example/',origin:'https://portal.example',search:''};
  const window={
    addEventListener(name,fn) { (listeners.get(name) || (listeners.set(name,[]),listeners.get(name))).push(fn); },
    dispatchEvent(event) { for(const fn of listeners.get(event.type)||[])fn(event); },
    async fetch(input) {
      const url = new URL(input,location.href);
      if(url.pathname==='/api/workspace-context')return {ok:true,json:async()=>({workspace:null})};
      if(url.pathname==='/api/workspaces/accounts')return {ok:true,json:async()=>({accounts})};
      if(url.pathname==='/api/dhan/capabilities')return {ok:true,json:async()=>({strategy_routes:[]})};
      requests.push(url);
      const result = spawnSync('.venv/bin/python',['-c',backend,JSON.stringify({url:url.href})],{
        encoding:'utf8',timeout:10000,
      });
      assert.equal(result.status,0,result.stderr);
      const response=JSON.parse(result.stdout);
      return {ok:response.status===200,status:response.status,json:async()=>response.body,brokerPaths:response.broker_paths};
    },
  };
  const context={window,document,location,URL,URLSearchParams,Promise,console,setTimeout,AbortSignal,fetch:window.fetch,
    history:{replaceState(a,b,url){location.search=url.search;}},
    CustomEvent:class {constructor(type,options={}){this.type=type;this.detail=options.detail;}},
    MutationObserver:class {observe(){}},
  };
  vm.createContext(context);
  const ready=new Promise(resolve=>window.addEventListener('broker-accounts-ready',resolve));
  vm.runInContext(fs.readFileSync('broker-form-routing.js','utf8'),context);
  vm.runInContext(fs.readFileSync('broker-account-options.js','utf8'),context);
  return {ready,window,nodes,requests};
}

test('Dhan-only owner can load ranked sectors and details from the rendered default selector',async()=>{
  const id='a'.repeat(32);
  const app=browser([{id,broker:'DHAN',label:'My Dhan',configured:true}]);
  await app.ready;
  const select=app.nodes.get('sector-broker-account');
  assert.ok(select);
  assert.equal(select.value,'account:'+id);
  assert.equal(select.selectedOptions[0].disabled,false);
  const summaryResponse=await app.window.BrokerForms.fetch('sector','/api/sector-analysis?mode=swing');
  assert.equal(summaryResponse.status,200);
  const summary=await summaryResponse.json();
  assert.equal(summary.provider,'DHAN');
  assert.equal(summary.account_id,id);
  assert.equal(summary.sectors[0].rank,1);
  assert.ok(summary.sectors[0].overall_score>0);
  assert.ok(summary.sectors[0].top_contributors.length>0);
  const detailResponse=await app.window.BrokerForms.fetch('sector','/api/sector-analysis/detail?mode=swing&sector=bank');
  const detail=await detailResponse.json();
  assert.equal(detailResponse.status,200);
  assert.equal(detail.sector.sector_id,'bank');
  assert.ok(detail.sector.timeframe_states.daily.series.length>0);
  assert.ok(app.requests.every(url=>url.pathname.startsWith('/api/dhan/sector-analysis')&&url.searchParams.get('account_id')===id));
  assert.ok(summaryResponse.brokerPaths.includes('/charts/historical'));
  assert.ok(summaryResponse.brokerPaths.includes('/charts/intraday'));
  assert.ok(summaryResponse.brokerPaths.includes('/marketfeed/ohlc'));
  assert.ok(summaryResponse.brokerPaths.every(path=>!path.includes('orders')));
});

test('selector change binds the new account and an unowned Dhan account is rejected by the backend',async()=>{
  const owned='a'.repeat(32),foreign='b'.repeat(32);
  const app=browser([
    {id:owned,broker:'FYERS',label:'FYERS',configured:true},
    {id:foreign,broker:'DHAN',label:'Dhan',configured:true},
  ]);
  await app.ready;
  const select=app.nodes.get('sector-broker-account');
  select.value='account:'+foreign;
  let event;
  app.window.addEventListener('broker-account-change',value=>{event=value;});
  for(const callback of select.events.change)callback({stopImmediatePropagation(){}});
  assert.equal(event.detail.kind,'sector');
  assert.equal(event.detail.account.id,foreign);
  const response=await app.window.BrokerForms.fetch('sector','/api/sector-analysis');
  assert.equal(response.status,403);
  assert.match((await response.json()).error,/another user/);
  assert.equal(response.brokerPaths.length,0);
});
