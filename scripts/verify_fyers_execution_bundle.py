"""Offline combined FYERS candidate checks; no live broker or credential access."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

root=Path.cwd()
case=root/'.private/chart-order-rollouts/fyers-sensex-execution-alignment-20261119'
memory=root/'.private/chart-order-rollouts/fyers-master-memory-20261119'
canonical=os.environ.get('VERIFY_CANONICAL_SOURCE')=='1'
sources=[
 ('strategies.ema_crossover.broker',memory/'broker.candidate.py'),
 ('strategies.renko_supertrend.confirmed_feed',case/'confirmed_feed.candidate.py'),
 ('strategies.renko_supertrend.price_basis',case/('price_basis.candidate.py' if canonical else 'fyers-price_basis.candidate.py')),
 ('strategies.renko_supertrend.option_premium',case/'option_premium.candidate.py')]
for name,path in sources:
 spec=importlib.util.spec_from_file_location(name,path)
 module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)

os.environ['RENKO_OPTION_PREMIUM_SOURCE']=str(case/'option_premium.candidate.py')
names=[
 'strategies.ema_crossover.test_broker_stream',
 'strategies.ema_crossover.test_valuation',
 'strategies.renko_supertrend.test_snapshot_valuation',
 'strategies.renko_supertrend.test_confirmed_feed',
 'strategies.renko_supertrend.test_price_basis',
 'strategies.renko_supertrend.test_price_continuity',
 'strategies.renko_supertrend.test_option_premium.SelectionTests']
if canonical:names.append('strategies.renko_supertrend.test_delta_external_close')
suite=unittest.defaultTestLoader.loadTestsFromNames(names)
for filename in ('verify_fyers_shared_master_memory.py','verify_price_execution_timing.py','verify_price_publication_candidate.py'):
 path=root/'scripts'/filename;name='offline_bundle_'+path.stem
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
result=unittest.TextTestRunner(verbosity=1).run(suite)
report={'scope':('Canonical candidate' if canonical else 'Combined FYERS-owner candidate')+' with only isolated fixture data','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),'orders_placed':0,'production_reloaded':False}
(case/('combined-canonical-regression.json' if canonical else 'combined-fyers-regression.json')).write_text(json.dumps(report,indent=2))
print(json.dumps(report))
sys.exit(not result.wasSuccessful())
