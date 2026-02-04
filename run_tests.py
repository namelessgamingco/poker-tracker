#!/usr/bin/env python
"""
Run all tests for the Diamond+ engine.

Usage (from repo root):
    python run_tests.py
"""

import subprocess
import sys
import os

def main():
    # Get the repo root (where this script lives)
    repo_root = os.path.dirname(os.path.abspath(__file__))
    
    # Run the engine tests
    test_file = os.path.join(repo_root, "tests", "test_engine.py")
    
    if not os.path.exists(test_file):
        print(f"ERROR: Test file not found at {test_file}")
        print("Make sure tests/test_engine.py exists.")
        sys.exit(1)
    
    print("=" * 60)
    print("Running Engine Tests...")
    print("=" * 60)
    print()
    
    # Run the tests
    result = subprocess.run([sys.executable, test_file], cwd=repo_root)
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()