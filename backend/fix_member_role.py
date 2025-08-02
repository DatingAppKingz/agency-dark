#!/usr/bin/env python3
"""Fix AGENCY_MEMBER references to MEMBER."""

import os
import re
from pathlib import Path

def fix_agency_member(file_path):
    """Replace AGENCY_MEMBER with MEMBER in file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Replace UserRole.AGENCY_MEMBER with UserRole.MEMBER
    content = re.sub(r'UserRole\.AGENCY_MEMBER', 'UserRole.MEMBER', content)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Fixed AGENCY_MEMBER references in {file_path}")
        return True
    return False

def main():
    backend_dir = Path(__file__).parent
    
    # Files to fix
    files_to_fix = [
        "core/realtime/socketio_server.py",
        "tests/unit/test_socketio_financial.py",
        "tests/integration/test_bulk_operations.py",
        "tests/integration/test_transaction_endpoints.py",
        "api/v1/endpoints/auth.py",
        "api/v1/endpoints/bulk_operations_advanced.py",
        "api/v1/endpoints/rate_limits_advanced.py",
        "modules/chat/realtime/namespace.py",
        "modules/financial/api/endpoints.py",
        "modules/onlyfans_wrapper/api/endpoints.py",
        "modules/api_orchestration/api/endpoints.py",
        "modules/notifications/realtime/namespace.py",
        "modules/analytics/api/endpoints.py",
        "seed_test_data.py"
    ]
    
    print("Fixing AGENCY_MEMBER references...")
    for file_path in files_to_fix:
        full_path = backend_dir / file_path
        if full_path.exists():
            fix_agency_member(full_path)
    
    print("\nDone!")

if __name__ == "__main__":
    main()