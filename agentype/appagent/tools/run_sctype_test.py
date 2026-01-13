#!/usr/bin/env python3
"""
agentype - Standalone tester for scType annotation
Author: cuilei
Version: 1.0
"""

import argparse
import os
import sys
import json
from pathlib import Path


def check_rscript():
    """Return a short Rscript version string or a warning text."""
    import subprocess
    try:
        out = subprocess.check_output(["Rscript", "--version"], stderr=subprocess.STDOUT, text=True)
        return out.strip().splitlines()[0]
    except Exception as e:
        return f"Rscript not available: {e}"


def main():
    parser = argparse.ArgumentParser(description="Run scType on a single file for diagnostics.")
    parser.add_argument("--data", required=True, help="Path to input data (.rds or .h5). scType does not support .h5ad.")
    parser.add_argument("--tissue", default="Immune system", help="scType tissue type (default: Immune system)")
    parser.add_argument("--out", default=None, help="Optional explicit output json path.")
    args = parser.parse_args()

    data_path = os.path.abspath(args.data)
    if not os.path.exists(data_path):
        print(f"[ERROR] File not found: {data_path}")
        sys.exit(2)

    ext = Path(data_path).suffix.lower()
    print("=== scType Test ===")
    print(f"Rscript: {check_rscript()}")
    print(f"Input: {data_path}")
    print(f"Ext: {ext}")
    print(f"Tissue: {args.tissue}")

    if ext == ".h5ad":
        print("[FAIL] .h5ad is not supported by scType. Convert to RDS or easySCF .h5 first.")
        sys.exit(3)

    if ext not in (".rds", ".h5"):
        print(f"[FAIL] Unsupported extension for scType: {ext}. Expected .rds or .h5")
        sys.exit(3)

    # Defer import until after basic checks to give clearer messages
    try:
        # Import from the same package where the MCP server sources it
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from sctype_simple import sctype_annotate  # type: ignore
    except Exception as e:
        print(f"[ERROR] Failed to import sctype_annotate: {e}")
        sys.exit(4)

    try:
        result = sctype_annotate(data_path=data_path, tissue_type=args.tissue, output_path=args.out)
        # Normalize output
        if isinstance(result, dict):
            print("\n[OK] scType finished.")
            print(f"Method: {result.get('method')}")
            print(f"Output: {result.get('output_file')}")
            print(f"Total clusters: {result.get('total_clusters')}")
            # Also dump the dict for detailed inspection
            print("\nFull result (JSON):")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("\n[WARN] Unexpected return type from sctype_annotate.")
            print(repr(result))
    except Exception as e:
        # The underlying function wraps R errors into RuntimeError with stderr.
        msg = str(e)
        print("\n[ERROR] scType run failed.")
        print("---- Error details ----")
        print(msg)
        print("-----------------------")

        # Quick hints based on common failure modes
        if "there is no package called 'easySCFr'" in msg or "package 'easySCFr'" in msg:
            print("Hint: The R package 'easySCFr' is required for .h5 input. Install it in R or use an .rds input.")
        if "cannot open the connection" in msg and ext == ".h5":
            print("Hint: Ensure the .h5 is in easySCF format (saved via easySCFpy::saveH5 or R easySCFr::saveH5).")
        if "sctype_wrapper.R" in msg or "source(\"https://raw.githubusercontent.com/kris-nader/sc-type" in msg:
            print("Hint: Network is required to fetch sctype_wrapper.R unless you vendor a local copy.")

        sys.exit(5)


if __name__ == "__main__":
    main()

