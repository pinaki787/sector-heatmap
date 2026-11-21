"""Reproduce broad-suite pre-existing failures using the saved pre-change runner."""
from pathlib import Path
import sys,types,unittest
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
name='strategies.renko_supertrend.runner'
module=types.ModuleType(name);module.__package__='strategies.renko_supertrend'
module.__file__=str(root/'.private/confirmed-feed-backup-1792679287/strategies/renko_supertrend/runner.py')
sys.modules[name]=module
exec(compile(Path(module.__file__).read_bytes(),module.__file__,'exec'),module.__dict__)
tests=[
'strategies.renko_supertrend.test_manual_brick_inputs.Inputs.test_selected_period_for_all_categories',
'strategies.renko_supertrend.test_delta_integration.ConcurrentRulesTests.test_exact_signal_formula_is_shared',
'strategies.renko_supertrend.test_delta_perpetual.PerpetualBoundaryTests.test_explicit_route_and_fyers_scope',
'strategies.renko_supertrend.test_sideways.RangeRulesTests.test_negative_loss_and_host_candle_bucket_window']
result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(tests))
print('Pre-change baseline failures:',len(result.failures),'errors:',len(result.errors))
if len(result.failures)!=3 or len(result.errors)!=1:raise SystemExit('Baseline changed; investigate.')
