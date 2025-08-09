#!/usr/bin/env python3
"""
Script to migrate all imports from old auth systems to security_v2.
"""
import os
import re
from pathlib import Path

# Define replacement patterns
IMPORT_REPLACEMENTS = {
    # Old security imports to security_v2
    r'from core\.security import': 'from core.security_v2 import',
    r'from core\.auth_security import': 'from core.security_v2 import',
    r'from core\.auth import': 'from core.security_v2 import',
    r'from core\.auth\.': 'from core.security_v2.',
    r'from core\.permissions import': 'from core.security_v2.authorization import',
    r'from core\.rbac import': 'from core.security_v2.authorization import',
    r'from core\.websocket_auth import': 'from core.security_v2.authentication import',
    
    # Middleware imports
    r'from core\.middleware\.auth import': 'from core.security_v2.middleware import',
    r'from core\.middleware\.security import': 'from core.security_v2.middleware import',
    r'from core\.middleware\.enhanced_security import': 'from core.security_v2.middleware import',
    
    # Specific function imports that might need updating
    r'get_password_hash': 'hash_password',
    r'from core\.auth\.token_blacklist import token_blacklist_service': 'from core.security_v2 import session_manager',
    r'token_blacklist_service': 'session_manager',
}

# Directories to skip
SKIP_DIRS = {
    'venv',
    '__pycache__',
    '.git',
    'node_modules',
    'archive',
    'htmlcov',
    '.pytest_cache',
    'migrations',
    'alembic'
}

# Files to skip
SKIP_FILES = {
    'migrate_to_security_v2.py',  # Don't modify this script itself
}


def should_skip(path: Path) -> bool:
    """Check if path should be skipped."""
    # Skip directories
    for parent in path.parents:
        if parent.name in SKIP_DIRS:
            return True
    
    # Skip specific files
    if path.name in SKIP_FILES:
        return True
    
    # Skip non-Python files
    if not path.suffix == '.py':
        return True
    
    return False


def migrate_file(filepath: Path) -> bool:
    """
    Migrate a single Python file to use security_v2 imports.
    Returns True if file was modified.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply all replacements
        for pattern, replacement in IMPORT_REPLACEMENTS.items():
            content = re.sub(pattern, replacement, content)
        
        # Check if file was modified
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
    
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False


def find_python_files(root_dir: Path) -> list[Path]:
    """Find all Python files in the directory tree."""
    python_files = []
    
    for path in root_dir.rglob('*.py'):
        if not should_skip(path):
            python_files.append(path)
    
    return python_files


def main():
    """Main migration function."""
    # Get backend directory
    backend_dir = Path(__file__).parent.parent  # Go up from scripts/ to backend/
    
    print(f"Starting migration to security_v2...")
    print(f"Scanning directory: {backend_dir}")
    
    # Find all Python files
    python_files = find_python_files(backend_dir)
    print(f"Found {len(python_files)} Python files to check")
    
    # Migrate each file
    modified_files = []
    for filepath in python_files:
        relative_path = filepath.relative_to(backend_dir)
        
        if migrate_file(filepath):
            modified_files.append(relative_path)
            print(f"✓ Modified: {relative_path}")
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Migration complete!")
    print(f"Modified {len(modified_files)} files")
    
    if modified_files:
        print("\nModified files:")
        for path in sorted(modified_files):
            print(f"  - {path}")
    
    # Check for potential issues
    print(f"\n{'='*50}")
    print("Next steps:")
    print("1. Review the modified files")
    print("2. Run tests to ensure everything works")
    print("3. Fix any import errors that may occur")
    print("4. Commit the changes")


if __name__ == "__main__":
    main()