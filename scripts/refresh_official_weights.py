#!/usr/bin/env python3
"""Validate and atomically install a reviewed monthly NSE weight dataset."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sector_heatmap.official_weights import DATA_DIRECTORY, latest_weight_file, load_weight_document, validate_weight_document  # noqa: E402


def install_candidate(candidate_path, destination=DATA_DIRECTORY, check_only=False):
    candidate_path = Path(candidate_path).resolve()
    destination = Path(destination).resolve()
    candidate = load_weight_document(candidate_path)
    latest_path = latest_weight_file(destination)
    latest = load_weight_document(latest_path)
    if set(candidate["indices"]) != set(latest["indices"]):
        missing = sorted(set(latest["indices"]) - set(candidate["indices"]))
        added = sorted(set(candidate["indices"]) - set(latest["indices"]))
        raise ValueError(f"sector coverage changed; missing={missing}, added={added}")
    if candidate["source_as_of"] <= latest["source_as_of"]:
        raise ValueError("candidate source_as_of must be newer than the installed dataset")
    output = destination / f"{candidate['source_as_of']}.json"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing version {output.name}")
    if check_only:
        return output
    destination.mkdir(parents=True, exist_ok=True)
    content = json.dumps(validate_weight_document(candidate), indent=2, ensure_ascii=False) + "\n"
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination, prefix=f".{output.name}.", delete=False) as handle:
            handle.write(content)
            temporary_path = Path(handle.name)
        os.replace(temporary_path, output)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", help="Reviewed JSON candidate transcribed from official NSE Indices factsheet and constituent files")
    parser.add_argument("--check-only", action="store_true", help="Validate without changing the installed dataset")
    args = parser.parse_args()
    output = install_candidate(args.candidate, check_only=args.check_only)
    verb = "Validated candidate for" if args.check_only else "Installed"
    print(f"{verb} {output}")


if __name__ == "__main__":
    main()
