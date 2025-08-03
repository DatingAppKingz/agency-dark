#!/usr/bin/env python3
"""
Phase 2: Remove duplicate APIKey and fix model conflicts
"""
import os
import re
from pathlib import Path

def remove_duplicate_apikey():
    """Remove the duplicate APIKey model from core/domain"""
    # First, let's rename it to prevent immediate import errors
    domain_apikey_file = Path(__file__).parent / "core" / "domain" / "api_key_models.py"
    if domain_apikey_file.exists():
        backup_file = domain_apikey_file.with_suffix('.py.backup')
        print(f"   📦 Moving {domain_apikey_file} to {backup_file}")
        domain_apikey_file.rename(backup_file)
        return True
    return False


def update_core_domain_models():
    """Update core/domain/models.py to use the correct APIKey"""
    domain_models_file = Path(__file__).parent / "core" / "domain" / "models.py"
    if not domain_models_file.exists():
        print(f"   ⚠️  {domain_models_file} not found")
        return False
    
    with open(domain_models_file, 'r') as f:
        content = f.read()
    
    # Check if it's importing from the duplicate location
    if 'from models.api_key import APIKey' in content:
        # Remove the import
        content = re.sub(r'from \.api_key_models import APIKey\n', '', content)
        print("   ✅ Removed duplicate APIKey import from core.domain.models")
        
        with open(domain_models_file, 'w') as f:
            f.write(content)
        return True
    
    return False


def update_apikey_imports():
    """Find and update all files importing APIKey from the wrong location"""
    backend_dir = Path(__file__).parent
    updated_files = []
    
    # Patterns to find and replace
    patterns = [
        (r'from core\.domain\.api_key_models import APIKey', 'from models.api_key import APIKey'),
        (r'from core\.domain\.api_keys import APIKey', 'from models.api_key import APIKey'),
        (r'from \.api_key_models import APIKey', 'from models.api_key import APIKey'),
    ]
    
    # Search for Python files
    for py_file in backend_dir.rglob("*.py"):
        # Skip test files and the duplicate file itself
        if any(skip in str(py_file) for skip in ['test_', '__pycache__', '.backup', 'venv/', '.pyc']):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            original_content = content
            for pattern, replacement in patterns:
                content = re.sub(pattern, replacement, content)
            
            if content != original_content:
                with open(py_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                updated_files.append(py_file.relative_to(backend_dir))
        except Exception as e:
            # Skip files we can't read
            pass
    
    return updated_files


def check_other_duplicates():
    """Check for other potential duplicate model definitions"""
    backend_dir = Path(__file__).parent
    model_definitions = {}
    
    # Pattern to find class definitions
    class_pattern = re.compile(r'^class\s+(\w+)\s*\([^)]*(?:Base|BaseModel|Base\s*,|BaseModel\s*,)', re.MULTILINE)
    
    for py_file in backend_dir.rglob("*.py"):
        # Skip test files and non-model files
        if any(skip in str(py_file) for skip in ['test_', '__pycache__', '.backup', 'venv/', '.pyc', 'alembic/']):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            matches = class_pattern.findall(content)
            for class_name in matches:
                if class_name not in model_definitions:
                    model_definitions[class_name] = []
                model_definitions[class_name].append(py_file.relative_to(backend_dir))
        except Exception:
            pass
    
    # Find duplicates
    duplicates = {name: files for name, files in model_definitions.items() if len(files) > 1}
    return duplicates


def main():
    print("Phase 2: Removing duplicate models and fixing conflicts...")
    
    # Step 1: Remove duplicate APIKey
    print("\n1. Removing duplicate APIKey model...")
    if remove_duplicate_apikey():
        print("   ✅ Moved duplicate APIKey model to backup")
    else:
        print("   ℹ️  Duplicate APIKey model not found or already removed")
    
    # Step 2: Update core/domain/models.py
    print("\n2. Updating core/domain/models.py...")
    if update_core_domain_models():
        print("   ✅ Updated core/domain/models.py")
    else:
        print("   ℹ️  No changes needed in core/domain/models.py")
    
    # Step 3: Update all APIKey imports
    print("\n3. Updating APIKey imports across the codebase...")
    updated_files = update_apikey_imports()
    if updated_files:
        print(f"   ✅ Updated {len(updated_files)} files:")
        for file in updated_files[:10]:  # Show first 10
            print(f"      - {file}")
        if len(updated_files) > 10:
            print(f"      ... and {len(updated_files) - 10} more")
    else:
        print("   ℹ️  No files needed APIKey import updates")
    
    # Step 4: Check for other duplicates
    print("\n4. Checking for other duplicate model definitions...")
    duplicates = check_other_duplicates()
    
    # Filter out known non-issues
    known_ok = ['Base', 'BaseModel', 'User', 'Session']  # These might appear in tests
    real_duplicates = {k: v for k, v in duplicates.items() 
                      if k not in known_ok and not k.startswith('Test')}
    
    if real_duplicates:
        print("   ⚠️  Found potential duplicate models:")
        for model_name, files in real_duplicates.items():
            print(f"\n   {model_name}:")
            for file in files:
                print(f"      - {file}")
    else:
        print("   ✅ No other duplicate models found")
    
    print("\n✅ Phase 2 Complete!")
    print("\n⚠️  Next steps:")
    print("1. Restart the backend to test the changes")
    print("2. If there are errors, check the model relationships")
    print("3. Proceed to fix any remaining relationship issues")


if __name__ == "__main__":
    main()