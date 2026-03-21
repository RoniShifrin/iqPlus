#!/usr/bin/env python3
"""
Convenience script to run database seeding from the BACK directory
This is a wrapper that runs the main seed script from INFRA/scripts/
"""
import subprocess
import sys
import os

# Get the path to the main seed script
script_dir = os.path.dirname(os.path.abspath(__file__))
seed_script = os.path.join(script_dir, '..', 'INFRA', 'scripts', 'seed_database.py')

try:
    result = subprocess.run([sys.executable, seed_script], cwd=script_dir)
    sys.exit(result.returncode)
except FileNotFoundError:
    print(f"❌ Error: Could not find seed script at {seed_script}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error running seed script: {e}")
    sys.exit(1)
