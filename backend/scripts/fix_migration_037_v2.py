#!/usr/bin/env python3
"""
Fix migration 037 - better handling of duplicate notifications table and indexes.
"""
from pathlib import Path

def fix_migration_037():
    """Fix migration 037 more carefully."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '037_notifications.py'
    
    # Read the original file
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Find where to add the index existence checks
    new_lines = []
    in_upgrade = False
    indices_section_found = False
    
    for i, line in enumerate(lines):
        # Skip duplicate sections
        if line.strip().startswith("# Check and create") and i > 0 and lines[i-1].strip().startswith("# Check and create"):
            continue
        if line.strip().startswith("connection = op.get_bind()") and i > 0 and lines[i-1].strip().startswith("connection = op.get_bind()"):
            continue
            
        # When we find the indices section, add conditional checks
        if "# Create indices" in line and not indices_section_found:
            indices_section_found = True
            new_lines.append(line)
            new_lines.append("    # Check if indexes already exist (they might have been created in migration 001)\n")
            new_lines.append("    conn = op.get_bind()\n")
            new_lines.append("    \n")
            continue
            
        # For each index creation, add existence check
        if indices_section_found and "op.create_index(" in line and "notifications" in line:
            # Extract index name
            index_name = None
            if "op.f('" in line:
                start = line.find("op.f('") + 6
                end = line.find("')", start)
                index_name = line[start:end]
            
            if index_name:
                new_lines.append(f"    # Check if {index_name} exists\n")
                new_lines.append(f"    result = conn.execute(sa.text(\n")
                new_lines.append(f'        "SELECT 1 FROM pg_indexes WHERE indexname = \'{index_name}\'"\n')
                new_lines.append(f"    ))\n")
                new_lines.append(f"    if not result.fetchone():\n")
                new_lines.append("    " + line)  # Indent the original line
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    # Write back
    with open(filepath, 'w') as f:
        f.writelines(new_lines)
    
    print("Fixed migration 037 with better index handling")

if __name__ == '__main__':
    fix_migration_037()