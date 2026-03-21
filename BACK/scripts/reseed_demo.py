#!/usr/bin/env python3
"""
IQ PLUS — Demo Reseed Utility
==============================
Wipes and regenerates demo data in one command.

Usage:
    python scripts/reseed_demo.py small   # clear + reseed small demo (@demo.iqplus.dev)
    python scripts/reseed_demo.py large   # clear + reseed large demo (@large.iqplus.dev)
    python scripts/reseed_demo.py all     # clear + reseed both
    python scripts/reseed_demo.py         # defaults to: all
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent
PYTHON  = sys.executable


def run(script: str, *args: str) -> int:
    cmd = [PYTHON, str(SCRIPTS / script)] + list(args)
    print(f"\n  >> {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode


def reseed_small() -> bool:
    print("=" * 60)
    print("  SMALL DEMO  (@demo.iqplus.dev)")
    print("=" * 60)
    rc = run("seed_demo_data.py", "--reseed")
    return rc == 0


def reseed_large() -> bool:
    print("=" * 60)
    print("  LARGE DEMO  (@large.iqplus.dev)")
    print("=" * 60)
    rc = run("seed_large_demo.py", "--reseed")
    return rc == 0


if __name__ == "__main__":
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if target not in ("small", "large", "all"):
        print(f"  Unknown target '{target}'. Use: small | large | all")
        sys.exit(1)

    ok = True
    if target in ("small", "all"):
        ok = reseed_small() and ok
    if target in ("large", "all"):
        ok = reseed_large() and ok

    if ok:
        print("\n  All done.\n")
    else:
        print("\n  One or more steps failed. Check output above.\n")
        sys.exit(1)
