"""Exercise real Pine worker request guards without network or production changes."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
worker=sys.argv[1]
cases={
 "valid_host_guard":(Path("tests/fixtures/pine/chart-guard-secondary-request.pine").read_text(),None),
 "invalid_host_guard":("//@version=6\nindicator(\"Invalid host\")\nif barstate.isfirst and timeframe.isintraday\n    runtime.error(\"Invalid host remains rejected\")\nplot(request.security(syminfo.tickerid,\"1D\",high[1]))\n","Invalid host remains rejected"),
 "requested_function_guard":("//@version=6\nindicator(\"Requested function\")\nf() =>\n    if not timeframe.isintraday\n        runtime.error(\"Requested function remains rejected\")\n    high\nplot(request.security(syminfo.tickerid,\"1D\",f()))\n","Requested function remains rejected"),
 "mutation_branch_guard":("//@version=6\nindicator(\"Mutation branch\")\nvar int counter=0\nif not timeframe.isintraday\n    counter+=1\n    runtime.error(\"Mutation branch retained\")\nplot(request.security(syminfo.tickerid,\"1D\",high[1]))\n","Mutation branch retained")
}
results=[]
with tempfile.TemporaryDirectory(prefix="pine-request-guards-") as directory:
 for name,(source,error) in cases.items():
  path=Path(directory)/f"{name}.pine";path.write_text(source)
  env=dict(os.environ,PINE_PROFILE_NATIVE_CONTEXT="1",PINE_PROFILE_COUNTS="100",PINE_PROFILE_CAPTURE_ERROR="1",PINE_PROFILE_SOURCE=str(path))
  run=subprocess.run(["node","scripts/profile_chart_pine_startup.cjs",worker],env=env,capture_output=True,text=True,timeout=90)
  data=json.loads(run.stdout)
  if error is None: assert run.returncode==0 and data.get("runs"), (name,data)
  else: assert run.returncode==1 and data.get("message")==error, (name,data)
  results.append({"case":name,"status":"PASS","expected_error":error,"actual_error":data.get("message")})
print(json.dumps({"status":"PASS","results":results},indent=2))
