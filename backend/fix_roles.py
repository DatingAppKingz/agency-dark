#!/usr/bin/env python3
import os
import re

def fix_roles_in_file(filepath):
    """Fix user roles in a single file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Replace MANAGER with AGENCY_MEMBER
    content = re.sub(r'UserRole\.MANAGER', 'UserRole.AGENCY_MEMBER', content)
    
    # Replace ANALYST with AGENCY_MEMBER (or you could remove it from lists)
    content = re.sub(r'UserRole\.ANALYST', 'UserRole.AGENCY_MEMBER', content)
    
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Fixed roles in: {filepath}")
        return True
    return False

def main():
    """Walk through all Python files and fix roles."""
    fixed_count = 0
    for root, dirs, files in os.walk('.'):
        # Skip venv directory
        if 'venv' in dirs:
            dirs.remove('venv')
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if fix_roles_in_file(filepath):
                    fixed_count += 1
    
    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == "__main__":
    main()