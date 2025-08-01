#!/usr/bin/env python3
"""
Run unit tests in isolation without loading the entire application
"""
import sys
import os
import subprocess
from pathlib import Path

# Set test environment
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/agencydark_test"

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Run tests with minimal imports
test_files = [
    "tests/unit/test_api_key_manager.py",
    "tests/unit/test_api_key_auth.py", 
    "tests/unit/test_api_audit_logger.py",
    "tests/unit/test_api_usage_middleware.py",
    "tests/unit/test_api_usage_tracker.py"
]

# Run each test file separately to avoid import conflicts
for test_file in test_files:
    print(f"\n{'='*60}")
    print(f"Running {test_file}")
    print('='*60)
    
    # Use subprocess to run each test in isolation
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short", "-p", "no:warnings"],
        cwd=backend_dir
    )
    
    if result.returncode != 0:
        print(f"\n❌ Tests failed in {test_file}")
    else:
        print(f"\n✅ Tests passed in {test_file}")