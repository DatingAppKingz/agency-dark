#!/usr/bin/env python3
"""
Check migration files for issues.
"""
import os
import re
import importlib.util
from pathlib import Path

def check_migration(filepath):
    """Check a single migration file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Extract revision info using regex - handle both old and new format
    revision_match = re.search(r"revision\s*(?::\s*str\s*)?=\s*['\"]([^'\"]+)['\"]", content)
    down_revision_match = re.search(r"down_revision\s*(?::\s*Union\[str,\s*Sequence\[str\],\s*None\]\s*)?=\s*['\"]([^'\"]+)['\"]", content)
    
    # Handle None case
    if not down_revision_match:
        down_revision_match = re.search(r"down_revision\s*[:=]\s*None", content)
        down_revision = None if down_revision_match else "NOT FOUND"
    else:
        down_revision = down_revision_match.group(1)
    
    revision = revision_match.group(1) if revision_match else "NOT FOUND"
    
    filename = os.path.basename(filepath)
    
    return {
        'file': filename,
        'revision': revision,
        'down_revision': down_revision
    }

def main():
    """Check all migration files."""
    versions_dir = Path(__file__).parent.parent / 'alembic' / 'versions'
    
    # Get all Python files that follow the numbering convention
    migration_files = sorted([
        f for f in versions_dir.glob('*.py')
        if re.match(r'^\d{3}_.*\.py$', f.name)
    ])
    
    print(f"Checking {len(migration_files)} migration files:\n")
    print(f"{'File':<50} {'Revision':<15} {'Down Revision':<15}")
    print("-" * 80)
    
    revisions = {}
    issues = []
    
    for filepath in migration_files:
        info = check_migration(filepath)
        print(f"{info['file']:<50} {info['revision']:<15} {str(info['down_revision']):<15}")
        
        # Check for issues
        if info['revision'] in revisions:
            issues.append(f"Duplicate revision '{info['revision']}' in {info['file']} and {revisions[info['revision']]}")
        revisions[info['revision']] = info['file']
        
        # Check if down_revision exists (except for first migration)
        if info['down_revision'] and info['down_revision'] != 'None':
            if info['down_revision'] not in revisions and info['down_revision'] != "NOT FOUND":
                # Will check this after all files are processed
                pass
    
    # Check for missing down_revisions
    for filepath in migration_files:
        info = check_migration(filepath)
        if info['down_revision'] and info['down_revision'] != 'None' and info['down_revision'] != "NOT FOUND":
            if info['down_revision'] not in revisions:
                issues.append(f"Missing down_revision '{info['down_revision']}' referenced in {info['file']}")
    
    if issues:
        print(f"\n\n⚠️  Found {len(issues)} issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n\n✅ All migrations look good!")

if __name__ == '__main__':
    main()