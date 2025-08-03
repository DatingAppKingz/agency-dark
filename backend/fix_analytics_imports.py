#!/usr/bin/env python3
"""
Fix duplicate analytics models by updating imports to use models from models/analytics.py.
"""

import os
import re
from pathlib import Path
from typing import List

def get_files_to_update() -> List[str]:
    """Get all Python files that import from modules analytics domain models."""
    files = []
    backend_dir = Path('.')
    
    for file_path in backend_dir.rglob('*.py'):
        if file_path.is_file():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'from modules.analytics.domain.models import' in content:
                        files.append(str(file_path))
            except Exception:
                pass
    
    return files

def update_analytics_imports(file_path: str) -> bool:
    """Update analytics model imports in a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Map of models that should come from models.analytics instead
    model_mapping = {
        'MetricSnapshot': 'models.analytics',
    }
    
    # Models that are unique to modules/analytics/domain/models.py
    unique_models = [
        'AggregationPeriod', 'Analytics', 'AnalyticsCache', 'AnalyticsEvent',
        'CategoryPerformance', 'ContentPerformance', 'FanSpendingHistory', 
        'RevenueTransaction'
    ]
    
    # Process multiline imports
    import_pattern = r'from\s+modules\.analytics\.domain\.models\s+import\s*\(([^)]+)\)'
    
    def process_imports(match):
        imports_str = match.group(1)
        imports = [imp.strip() for imp in imports_str.split(',')]
        
        # Separate imports by source
        models_analytics = []
        modules_analytics = []
        
        for imp in imports:
            imp = imp.strip()
            if imp in model_mapping:
                models_analytics.append(imp)
            elif imp in unique_models:
                modules_analytics.append(imp)
            else:
                # Unknown model, keep in modules for now
                modules_analytics.append(imp)
        
        # Build new import statements
        new_imports = []
        
        if models_analytics:
            if len(models_analytics) == 1:
                new_imports.append(f'from models.analytics import {models_analytics[0]}')
            else:
                imports_str = ', '.join(models_analytics)
                new_imports.append(f'from models.analytics import {imports_str}')
        
        if modules_analytics:
            if len(modules_analytics) == 1:
                new_imports.append(f'from modules.analytics.domain.models import {modules_analytics[0]}')
            else:
                imports_str = ', '.join(modules_analytics)
                if len(imports_str) > 80:
                    imports_formatted = ',\\n    '.join(modules_analytics)
                    new_imports.append(f'from modules.analytics.domain.models import \\n    {imports_formatted}\\n')
                else:
                    new_imports.append(f'from modules.analytics.domain.models import {imports_str}')
        
        return '\\n'.join(new_imports)
    
    content = re.sub(import_pattern, process_imports, content, flags=re.MULTILINE | re.DOTALL)
    
    # Process single-line imports
    single_import_pattern = r'from\s+modules\.analytics\.domain\.models\s+import\s+([^\\n]+)'
    
    def process_single_import(match):
        imports_str = match.group(1)
        imports = [imp.strip() for imp in imports_str.split(',')]
        
        # Same separation logic
        models_analytics = []
        modules_analytics = []
        
        for imp in imports:
            imp = imp.strip()
            if imp in model_mapping:
                models_analytics.append(imp)
            elif imp in unique_models:
                modules_analytics.append(imp)
            else:
                modules_analytics.append(imp)
        
        new_imports = []
        if models_analytics:
            new_imports.append(f'from models.analytics import {", ".join(models_analytics)}')
        if modules_analytics:
            new_imports.append(f'from modules.analytics.domain.models import {", ".join(modules_analytics)}')
        
        return '\\n'.join(new_imports)
    
    # Apply single-line pattern only where multiline didn't match
    if 'from modules.analytics.domain.models import (\n    ' not in content:
        content = re.sub(single_import_pattern,\n    process_single_import,\n    content\n)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False

def main():
    print("Fixing duplicate analytics model imports...")
    print("=" * 60)
    
    # Get files to update
    files = get_files_to_update()
    print(f"Found {len(files)} files importing from modules.analytics.domain.models")
    
    # Update files
    updated_count = 0
    for file_path in files:
        print(f"Processing: {file_path}")
        if update_analytics_imports(file_path):
            updated_count += 1
            print(f"  ✓ Updated")
        else:
            print(f"  - No changes needed")
    
    print("\\n" + "=" * 60)
    print(f"Complete: Updated {updated_count} files")
    
    # Now comment out the duplicate MetricSnapshot in modules/analytics/domain/models.py
    print("\\nCommenting out duplicate MetricSnapshot...")
    
    models_file = 'modules/analytics/domain/models.py'
    if os.path.exists(models_file):
        with open(models_file, 'r') as f:
            lines = f.readlines()
        
        # Find and comment out MetricSnapshot class
        in_metric_snapshot = False
        class_indent = None
        
        for i, line in enumerate(lines):
            if line.strip().startswith('class MetricSnapshot'):
                in_metric_snapshot = True
                class_indent = len(line) - len(line.lstrip())
                lines[i] = '# ' + lines[i]
            elif in_metric_snapshot and line.strip():
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= class_indent and (line.strip().startswith('class ') or line.strip().startswith('def ')):
                    # End of class
                    in_metric_snapshot = False
                else:
                    # Part of MetricSnapshot class
                    lines[i] = '# ' + lines[i]
        
        # Write back
        with open(models_file, 'w') as f:
            f.writelines(lines)
        
        print(f"  ✓ Commented out MetricSnapshot in {models_file}")
        
        # Add import at the top
        with open(models_file, 'r') as f:
            content = f.read()
        
        if 'from models.analytics import MetricSnapshot' not in content:
            lines = content.split('\\n')
            import_added = False
            for i, line in enumerate(lines):
                if line.startswith('from ') and not import_added:
                    lines.insert(i, 'from models.analytics import MetricSnapshot')
                    import_added = True
                    break
            
            with open(models_file, 'w') as f:
                f.write('\\n'.join(lines))
            
            print(f"  ✓ Added import for MetricSnapshot")

if __name__ == "__main__":
    main()