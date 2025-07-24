#!/usr/bin/env python3
import os
import re

def fix_imports_in_file(filepath):
    """Fix imports in a single file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace all occurrences of "from " with "from "
    new_content = re.sub(r'from backend\.', 'from ', content)
    
    # Replace all occurrences of "import " with "import "
    new_content = re.sub(r'import backend\.', 'import ', new_content)
    
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Fixed imports in: {filepath}")
        return True
    return False

def main():
    """Walk through all Python files and fix imports."""
    fixed_count = 0
    for root, dirs, files in os.walk('.'):
        # Skip venv directory
        if 'venv' in dirs:
            dirs.remove('venv')
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if fix_imports_in_file(filepath):
                    fixed_count += 1
    
    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == "__main__":
    main()