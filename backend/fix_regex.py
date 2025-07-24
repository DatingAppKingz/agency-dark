#!/usr/bin/env python3
import os
import re

def fix_regex_in_file(filepath):
    """Replace pattern= with pattern= in Field definitions."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Replace pattern= with pattern=
    content = re.sub(r'pattern=', 'pattern=', content)
    
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Fixed regex in: {filepath}")
        return True
    return False

def main():
    """Walk through all Python files and fix regex."""
    fixed_count = 0
    for root, dirs, files in os.walk('.'):
        # Skip venv directory
        if 'venv' in dirs:
            dirs.remove('venv')
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if fix_regex_in_file(filepath):
                    fixed_count += 1
    
    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == "__main__":
    main()