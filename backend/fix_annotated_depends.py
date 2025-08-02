#!/usr/bin/env python3
"""Fix Annotated CurrentUser usage with Depends."""

import os
import re
from pathlib import Path

def fix_annotated_depends(file_path):
    """Fix CurrentUser usage that has both Annotated and Depends."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Fix patterns like: current_user: CurrentUser = Depends(...)
    # Replace with just: current_user: CurrentUser
    content = re.sub(
        r'(current_user:\s*CurrentUser)\s*=\s*Depends\([^)]+\)',
        r'\1',
        content
    )
    
    # Also fix CurrentUserOptional patterns
    content = re.sub(
        r'(current_user:\s*CurrentUserOptional)\s*=\s*Depends\([^)]+\)',
        r'\1',
        content
    )
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Fixed Annotated/Depends issue in {file_path}")
        return True
    return False

def main():
    backend_dir = Path(__file__).parent
    
    # Find all Python files in api/v1/endpoints
    endpoints_dir = backend_dir / "api" / "v1" / "endpoints"
    
    print("Fixing Annotated CurrentUser with Depends issues...")
    fixed_count = 0
    
    for py_file in endpoints_dir.glob("*.py"):
        if fix_annotated_depends(py_file):
            fixed_count += 1
    
    # Also check other directories that might have this issue
    other_dirs = [
        backend_dir / "modules",
        backend_dir / "core"
    ]
    
    for dir_path in other_dirs:
        if dir_path.exists():
            for py_file in dir_path.rglob("*.py"):
                if fix_annotated_depends(py_file):
                    fixed_count += 1
    
    print(f"\nFixed {fixed_count} files!")

if __name__ == "__main__":
    main()