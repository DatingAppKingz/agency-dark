#!/usr/bin/env python3
"""
Fix migration 023 - handle non-existent indexes when renaming.
"""
from pathlib import Path

def fix_migration_023():
    """Fix migration 023 to check if indexes exist before renaming."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '023_rename_model_profiles_to_models.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace the simple rename with existence checks
    old_index_section = """    # Rename indexes
    op.execute('ALTER INDEX ix_model_profiles_agency_id RENAME TO ix_models_agency_id')
    op.execute('ALTER INDEX idx_model_profiles_agency_active RENAME TO idx_models_agency_active')
    op.execute('ALTER INDEX idx_model_profiles_agency_covering RENAME TO idx_models_agency_covering')
    op.execute('ALTER INDEX idx_model_profiles_agency_id RENAME TO idx_models_agency_id_2')
    op.execute('ALTER INDEX idx_model_profiles_agency_platform RENAME TO idx_models_agency_platform')"""
    
    new_index_section = """    # Rename indexes (with existence checks)
    connection = op.get_bind()
    
    # Check and rename each index
    indexes_to_rename = [
        ('ix_model_profiles_agency_id', 'ix_models_agency_id'),
        ('idx_model_profiles_agency_active', 'idx_models_agency_active'),
        ('idx_model_profiles_agency_covering', 'idx_models_agency_covering'),
        ('idx_model_profiles_agency_id', 'idx_models_agency_id_2'),
        ('idx_model_profiles_agency_platform', 'idx_models_agency_platform')
    ]
    
    for old_name, new_name in indexes_to_rename:
        result = connection.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
            {"name": old_name}
        )
        if result.fetchone():
            op.execute(f'ALTER INDEX {old_name} RENAME TO {new_name}')
        else:
            print(f"Index {old_name} does not exist, skipping rename")"""
    
    content = content.replace(old_index_section, new_index_section)
    
    # Also need to import sa
    if "import sqlalchemy as sa" not in content:
        content = content.replace("from alembic import op", "from alembic import op\nimport sqlalchemy as sa")
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed migration 023 to check index existence before renaming")

if __name__ == '__main__':
    fix_migration_023()