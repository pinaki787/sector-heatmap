"""Read-only release check for the private canonical V1 and picker revision badges."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / ".private/pine-unified-20261119/sector-pulse-unified.pine"
OWNERS = ["", "fd46b26f73022af571be11b1027c5291", "1b0a63fa2d371d3be413763078d21bbc",
          "b0041912d9d6f68d352814cbd24bf6da", "08823c4c2082f03de07634a51e39f9fb",
          "bf46fc364b610a0dfd338419e133cb41", "a6ef4c9bcecd21d54c4a07e2b9b137a7"]

def digest(path):
    return hashlib.sha256(path.read_text().replace("\r\n", "\n").encode()).hexdigest()

def main():
    expected = digest(CANONICAL)
    problems = []
    if digest(ROOT / "sector-pulse-v1.pine") != expected:
        problems.append("Root V1 differs from the private canonical source.")
    for owner in OWNERS:
        root = ROOT / ".private/dashboard-login/accounts" / owner / "source" if owner else ROOT
        script = (root / "chart-workspace.js").read_text()
        actual = re.search(r'canonicalV1: "([a-f0-9]{64})"', script)
        if not actual or actual[1] != expected:
            problems.append(f"{owner or 'main'}: stale canonical revision badge.")
    print(json.dumps({"canonical_sha256": expected, "maintained_sources": len(OWNERS),
                      "status": "FAIL" if problems else "PASS", "problems": problems}, indent=2))
    return bool(problems)

if __name__ == "__main__":
    raise SystemExit(main())
