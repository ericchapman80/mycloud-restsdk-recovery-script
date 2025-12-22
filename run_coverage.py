#!/usr/bin/env python3
"""
Run pytest with coverage for restsdk_public.py to check current coverage level.
"""
import subprocess
import sys

# Run pytest with coverage
result = subprocess.run([
    sys.executable, "-m", "pytest",
    "tests/test_restsdk_high_value.py",
    "tests/test_restsdk_core_functions.py", 
    "tests/test_restsdk_public.py",
    "tests/test_db_flows.py",
    "--cov=restsdk_public",
    "--cov-report=term-missing",
    "-v"
], capture_output=False)

sys.exit(result.returncode)
