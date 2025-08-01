#!/usr/bin/env python3
"""
Verify that test logic is correct without full app imports
"""
import os
import sys
from pathlib import Path

# Set required environment variables
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/agencydark_test"
os.environ["TESTING"] = "true"

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

print("="*60)
print("UNIT TEST VERIFICATION")
print("="*60)
print("\nRunning isolated test verification...")
print("\nNote: These tests verify the logic without requiring")
print("the full application to be importable.\n")

# Import and run isolated tests
from tests.unit.test_api_key_manager_isolated import TestSecureAPIKeyManagerIsolated

test_suite = TestSecureAPIKeyManagerIsolated()
tests_passed = 0
tests_failed = 0

# Run each test
test_methods = [
    ("Hash API Key Logic", test_suite.test_hash_api_key_logic),
    ("Check Scopes Logic", test_suite.test_check_scopes_logic),
    ("Needs Rotation Logic", test_suite.test_needs_rotation_logic),
    ("Key Prefix Generation", test_suite.test_key_prefix_generation),
    ("Metadata Encryption Format", test_suite.test_metadata_encryption_format),
]

for test_name, test_method in test_methods:
    try:
        test_method()
        print(f"✅ {test_name}")
        tests_passed += 1
    except Exception as e:
        print(f"❌ {test_name}: {str(e)}")
        tests_failed += 1

# Run async test
import asyncio

async def run_async_test():
    try:
        await test_suite.test_rate_limit_check_logic()
        print("✅ Rate Limit Check Logic")
        return True
    except Exception as e:
        print(f"❌ Rate Limit Check Logic: {str(e)}")
        return False

if asyncio.run(run_async_test()):
    tests_passed += 1
else:
    tests_failed += 1

print("\n" + "="*60)
print(f"TEST SUMMARY")
print("="*60)
print(f"Tests Passed: {tests_passed}")
print(f"Tests Failed: {tests_failed}")
print(f"Total Tests: {tests_passed + tests_failed}")

if tests_failed == 0:
    print("\n✅ All test logic verified successfully!")
    print("\nNote: Full integration testing requires resolving")
    print("SQLAlchemy model import conflicts.")
else:
    print(f"\n❌ {tests_failed} tests failed!")
    sys.exit(1)