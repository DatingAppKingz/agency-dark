#!/usr/bin/env python3
"""Fix Alembic migration naming and dependencies."""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Manual mapping of what should be fixed
MIGRATION_FIXES = {
    # Map of current_revision -> (new_filename, fixed_down_revision)
    "cd0086df175e": ("001_initial_migration", None),
    "0faccbbf85a4": ("002_add_analytics_tables", "001_initial_migration"),
    "ab6eda48e947": ("003_add_financial_tables", "002_add_analytics_tables"),
    "004_database_optimization": ("004_database_optimization", "001_initial_migration"),
    "005_add_api_key_tables": ("005_add_api_key_tables", "004_database_optimization"),
    "006_add_rate_limiting_tables": ("006_add_rate_limiting_tables", "005_add_api_key_tables"),
    "007": ("007_add_whitelabel_tables", "003_add_financial_tables"),
    "007_add_fraud_detection_tables": ("008_add_fraud_detection_tables", "006_add_rate_limiting_tables"),
    "007_performance_indexes": ("009_performance_indexes", "006_add_rate_limiting_tables"),
    "008": ("010_add_security_tables", "007_add_whitelabel_tables"),
    "008_ab_testing_framework": ("011_ab_testing_framework", "009_performance_indexes"),
    "008_add_bulk_operations_tables": ("012_add_bulk_operations_tables", "008_add_fraud_detection_tables"),
    "008_webhook_tables": ("013_webhook_tables", "009_performance_indexes"),
    "009_add_reporting_tables": ("014_add_reporting_tables", "012_add_bulk_operations_tables"),
    "009_analytics_dashboard": ("015_analytics_dashboard", "013_webhook_tables"),
    "010_add_ml_analytics_tables": ("016_add_ml_analytics_tables", "014_add_reporting_tables"),
    "011_add_monitoring_tables": ("017_add_monitoring_tables", "016_add_ml_analytics_tables"),
    "015_add_performance_indexes": ("018_add_performance_indexes", "017_add_monitoring_tables"),  # Fixed dependency
    "add_webhook_dead_letter_queue": ("019_add_webhook_dead_letter_queue", "017_add_monitoring_tables"),
    "add_user_profile_fields": ("020_add_user_profile_fields", "019_add_webhook_dead_letter_queue"),
}

def backup_migrations(migrations_dir: Path):
    """Create a backup of the migrations directory."""
    backup_dir = migrations_dir.parent / "versions_backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.copytree(migrations_dir, backup_dir)
    print(f"Created backup at: {backup_dir}")
    return backup_dir

def extract_migration_info(filepath: Path) -> Dict[str, Optional[str]]:
    """Extract revision and down_revision from a migration file."""
    content = filepath.read_text()
    
    # Extract revision ID - handle both assignment styles
    revision_match = re.search(r"revision\s*[:=]\s*['\"]([^'\"]+)['\"]", content)
    if not revision_match:
        revision_match = re.search(r"revision:\s*str\s*=\s*['\"]([^'\"]+)['\"]", content)
    revision = revision_match.group(1) if revision_match else None
    
    return {
        "filename": filepath.name,
        "revision": revision,
        "filepath": filepath,
        "content": content
    }

def fix_migration_file(migration_info: Dict, new_filename: str, new_down_revision: Optional[str]) -> str:
    """Fix a single migration file."""
    content = migration_info["content"]
    old_revision = migration_info["revision"]
    
    # Update revision to match new filename (without extension)
    new_revision = new_filename
    content = re.sub(
        r"(revision\s*[:=]\s*['\"])([^'\"]+)(['\"])",
        f"\\g<1>{new_revision}\\g<3>",
        content
    )
    content = re.sub(
        r"(revision:\s*str\s*=\s*['\"])([^'\"]+)(['\"])",
        f"\\g<1>{new_revision}\\g<3>",
        content
    )
    
    # Update down_revision
    if new_down_revision is not None:
        # Replace existing down_revision
        content = re.sub(
            r"(down_revision\s*[:=]\s*['\"])([^'\"]+)(['\"])",
            f"\\g<1>{new_down_revision}\\g<3>",
            content
        )
        content = re.sub(
            r"(down_revision:\s*Union\[str,\s*Sequence\[str\],\s*None\]\s*=\s*['\"])([^'\"]+)(['\"])",
            f"\\g<1>{new_down_revision}\\g<3>",
            content
        )
    else:
        # Set to None
        content = re.sub(
            r"(down_revision\s*[:=]\s*)(['\"])([^'\"]+)(['\"])",
            "\\g<1>None",
            content
        )
        content = re.sub(
            r"(down_revision:\s*Union\[str,\s*Sequence\[str\],\s*None\]\s*=\s*)(['\"])([^'\"]+)(['\"])",
            "\\g<1>None",
            content
        )
    
    # Update the docstring revision ID
    content = re.sub(
        r"(Revision ID:\s*)(\S+)",
        f"\\g<1>{new_revision}",
        content
    )
    
    return content, old_revision, new_revision

def main():
    """Main function to fix migrations."""
    migrations_dir = Path("/Users/mariuszbudzisz/SourceCode/agency-dark/backend/alembic/versions")
    
    print("Fixing Alembic migrations...")
    print("=" * 50)
    
    # Create backup
    backup_dir = backup_migrations(migrations_dir)
    
    # Read all migrations
    migrations = {}
    for filepath in migrations_dir.glob("*.py"):
        if filepath.name == "__pycache__" or filepath.name.startswith("."):
            continue
        info = extract_migration_info(filepath)
        if info["revision"]:
            migrations[info["revision"]] = info
    
    # Track revision mapping for updating references
    revision_mapping = {}
    
    # Process each migration
    fixed_count = 0
    for old_revision, (new_filename, new_down_revision) in MIGRATION_FIXES.items():
        if old_revision not in migrations:
            print(f"Warning: Migration {old_revision} not found")
            continue
        
        migration = migrations[old_revision]
        old_filepath = migration["filepath"]
        
        # Fix the content
        fixed_content, _, new_revision = fix_migration_file(
            migration, new_filename, new_down_revision
        )
        
        # Save to new filename
        new_filepath = migrations_dir / f"{new_filename}.py"
        new_filepath.write_text(fixed_content)
        
        # Remove old file if different
        if old_filepath != new_filepath:
            old_filepath.unlink()
        
        revision_mapping[old_revision] = new_revision
        fixed_count += 1
        print(f"Fixed: {migration['filename']} -> {new_filename}.py")
    
    # Second pass: Update any references to old revisions
    print("\nUpdating revision references...")
    for filepath in migrations_dir.glob("*.py"):
        if filepath.name == "__pycache__" or filepath.name.startswith("."):
            continue
            
        content = filepath.read_text()
        updated = False
        
        for old_rev, new_rev in revision_mapping.items():
            if old_rev != new_rev and old_rev in content:
                content = content.replace(f'"{old_rev}"', f'"{new_rev}"')
                content = content.replace(f"'{old_rev}'", f"'{new_rev}'")
                updated = True
        
        if updated:
            filepath.write_text(content)
            print(f"Updated references in: {filepath.name}")
    
    print(f"\nFixed {fixed_count} migrations")
    print(f"Backup saved at: {backup_dir}")
    print("\nNext steps:")
    print("1. Check the alembic_version table in your database")
    print("2. You may need to manually update the version in the database")
    print("3. Run: alembic current")
    print("4. Run: alembic check")

if __name__ == "__main__":
    main()