const {test}=require('node:test');const assert=require('node:assert/strict');
const {chartSelectionForInstrument}=require('../renko-supertrend.js');
test('switching displayed instrument replaces stale single chart selection',()=>assert.deepEqual(chartSelectionForInstrument('MCX:CRUDEOIL26OCTFUT',['BSE:SENSEX-INDEX']),['MCX:CRUDEOIL26OCTFUT']));
test('intentional multi-instrument batch keeps its independent selection',()=>assert.deepEqual(chartSelectionForInstrument('MCX:CRUDEOIL26OCTFUT',['BSE:SENSEX-INDEX','NSE:NIFTY50-INDEX']),['BSE:SENSEX-INDEX','NSE:NIFTY50-INDEX']));
test('empty displayed selection produces no fallback chart',()=>assert.deepEqual(chartSelectionForInstrument('',[]),[]));
