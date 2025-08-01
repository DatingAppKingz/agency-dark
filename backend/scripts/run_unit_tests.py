#!/usr/bin/env python3
"""
Run unit tests without full database setup
"""
import sys
import os
import pytest
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/agencydark_test"

if __name__ == "__main__":
    # Run tests with minimal setup
    sys.exit(pytest.main([
        "tests/unit/",
        "-v",
        "--tb=short",
        "--no-header",
        "-p", "no:warnings"
    ]))