#!/usr/bin/env python3
"""Minimal test runner that bypasses ML model loading."""
import subprocess
import os
import sys

# Set minimal environment
os.environ['TESTING'] = 'true'
os.environ['ML_MODELS_ENABLED'] = 'false'
os.environ['EMAIL_ENABLED'] = 'false'

# Add more test-specific environment variables
os.environ.update({
    'DATABASE_URL': 'postgresql://postgres:postgres@localhost/agencydark_test',
    'REDIS_URL': 'redis://localhost:6379/1',
    'SECRET_KEY': 'test-secret-key',
    'ENVIRONMENT': 'test',
    'LOG_LEVEL': 'WARNING',  # Reduce log noise during tests
})

# Run only unit tests, excluding integration tests
cmd = [
    "poetry", "run", "pytest", 
    "tests/unit/",
    "-v",
    "--tb=short",
    "-k", "not integration and not ml_models",
    "--no-cov",  # Disable coverage temporarily for faster runs
]

# Add any command line arguments passed to this script
if len(sys.argv) > 1:
    cmd.extend(sys.argv[1:])

print(f"Running: {' '.join(cmd)}")
result = subprocess.run(cmd)
sys.exit(result.returncode)