#!/usr/bin/env python3
"""Analyze and fix Alembic migration dependencies."""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import ast

def extract_migration_info(filepath: Path) -> Dict[str, Optional[str]]:
    """Extract revision and down_revision from a migration file."""
    content = filepath.read_text()
    
    # Extract revision ID - handle both assignment styles
    revision_match = re.search(r"revision\s*[:=]\s*['\"]([^'\"]+)['\"]", content)
    if not revision_match:
        # Try typed assignment style
        revision_match = re.search(r"revision:\s*str\s*=\s*['\"]([^'\"]+)['\"]", content)
    revision = revision_match.group(1) if revision_match else None
    
    # Extract down_revision - handle both styles
    down_revision_match = re.search(r"down_revision\s*[:=]\s*['\"]([^'\"]+)['\"]", content)
    if not down_revision_match:
        # Try typed assignment style
        down_revision_match = re.search(r"down_revision:\s*Union\[str,\s*Sequence\[str\],\s*None\]\s*=\s*['\"]([^'\"]+)['\"]", content)
    
    if not down_revision_match:
        # Try to match None assignment
        if re.search(r"down_revision\s*[:=]\s*None", content) or \
           re.search(r"down_revision:\s*Union\[str,\s*Sequence\[str\],\s*None\]\s*=\s*None", content):
            down_revision = None
        else:
            down_revision = "UNKNOWN"
    else:
        down_revision = down_revision_match.group(1)
    
    return {
        "filename": filepath.name,
        "revision": revision,
        "down_revision": down_revision,
        "filepath": str(filepath)
    }

def analyze_migrations(migrations_dir: Path) -> List[Dict[str, Optional[str]]]:
    """Analyze all migrations in the directory."""
    migrations = []
    
    for filepath in sorted(migrations_dir.glob("*.py")):
        if filepath.name == "__pycache__" or filepath.name.startswith("."):
            continue
            
        info = extract_migration_info(filepath)
        if info["revision"]:  # Skip files without revision
            migrations.append(info)
    
    return migrations

def find_migration_issues(migrations: List[Dict[str, Optional[str]]]) -> Dict[str, List[str]]:
    """Find issues in migration dependencies."""
    issues = {
        "missing_dependencies": [],
        "duplicate_revisions": [],
        "naming_inconsistencies": [],
        "circular_dependencies": [],
        "multiple_heads": []
    }
    
    # Create lookup maps
    revision_map = {m["revision"]: m for m in migrations}
    revision_counts = {}
    
    # Check for duplicates and build counts
    for m in migrations:
        rev = m["revision"]
        revision_counts[rev] = revision_counts.get(rev, 0) + 1
        
        # Check naming consistency
        if not (rev.startswith(('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')) or 
                len(rev) == 12):  # Alembic default hash length
            issues["naming_inconsistencies"].append(f"{m['filename']}: {rev}")
    
    # Find duplicates
    for rev, count in revision_counts.items():
        if count > 1:
            files = [m["filename"] for m in migrations if m["revision"] == rev]
            issues["duplicate_revisions"].append(f"{rev}: {files}")
    
    # Check dependencies
    for m in migrations:
        if m["down_revision"] and m["down_revision"] != "UNKNOWN":
            if m["down_revision"] not in revision_map:
                issues["missing_dependencies"].append(
                    f"{m['filename']} depends on missing revision: {m['down_revision']}"
                )
    
    # Find heads (migrations with no dependents)
    heads = []
    for m in migrations:
        if not any(other["down_revision"] == m["revision"] for other in migrations):
            heads.append(m)
    
    if len(heads) > 1:
        issues["multiple_heads"] = [f"{h['filename']} ({h['revision']})" for h in heads]
    
    return issues

def create_dependency_graph(migrations: List[Dict[str, Optional[str]]]) -> str:
    """Create a visual representation of migration dependencies."""
    lines = ["Migration Dependency Graph", "=" * 50, ""]
    
    # Group by down_revision to show tree structure
    by_parent = {}
    roots = []
    
    for m in migrations:
        parent = m["down_revision"]
        if parent is None:
            roots.append(m)
        else:
            if parent not in by_parent:
                by_parent[parent] = []
            by_parent[parent].append(m)
    
    def print_tree(migration, indent=0):
        prefix = "  " * indent + "└─ " if indent > 0 else ""
        lines.append(f"{prefix}{migration['filename']} ({migration['revision']})")
        
        children = by_parent.get(migration["revision"], [])
        for child in sorted(children, key=lambda x: x["filename"]):
            print_tree(child, indent + 1)
    
    for root in sorted(roots, key=lambda x: x["filename"]):
        print_tree(root)
        lines.append("")
    
    return "\n".join(lines)

def suggest_fixes(migrations: List[Dict[str, Optional[str]]], issues: Dict[str, List[str]]) -> str:
    """Suggest fixes for migration issues."""
    suggestions = ["Suggested Fixes", "=" * 50, ""]
    
    # Suggest a proper migration order
    suggestions.append("1. Rename migrations to use consistent numbering:")
    suggestions.append("")
    
    # Build proper dependency chain
    revision_map = {m["revision"]: m for m in migrations}
    visited = set()
    ordered = []
    
    def visit(revision):
        if revision in visited or revision not in revision_map:
            return
        visited.add(revision)
        m = revision_map[revision]
        if m["down_revision"] and m["down_revision"] in revision_map:
            visit(m["down_revision"])
        ordered.append(m)
    
    # Start from roots and traverse
    for m in migrations:
        if m["down_revision"] is None:
            visit(m["revision"])
    
    # Visit any remaining migrations
    for m in migrations:
        visit(m["revision"])
    
    # Suggest new names
    for i, m in enumerate(ordered):
        new_name = f"{i+1:03d}_{m['filename'].split('_', 1)[-1] if '_' in m['filename'] else m['filename']}"
        suggestions.append(f"  {m['filename']} -> {new_name}")
    
    suggestions.append("")
    suggestions.append("2. Fix dependency references:")
    
    for issue in issues["missing_dependencies"]:
        suggestions.append(f"  - {issue}")
    
    return "\n".join(suggestions)

def main():
    """Main analysis function."""
    migrations_dir = Path("/Users/mariuszbudzisz/SourceCode/agency-dark/backend/alembic/versions")
    
    print("Analyzing Alembic migrations...")
    print("=" * 50)
    
    migrations = analyze_migrations(migrations_dir)
    print(f"Found {len(migrations)} migration files")
    print()
    
    issues = find_migration_issues(migrations)
    
    print("Issues Found:")
    print("-" * 50)
    for issue_type, issue_list in issues.items():
        if issue_list:
            print(f"\n{issue_type.replace('_', ' ').title()}:")
            for issue in issue_list:
                print(f"  - {issue}")
    
    print("\n" + create_dependency_graph(migrations))
    print("\n" + suggest_fixes(migrations, issues))

if __name__ == "__main__":
    main()