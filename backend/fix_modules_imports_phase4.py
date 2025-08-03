#!/usr/bin/env python3
"""
Phase 4: Update Domain Layer to use centralized models.
This script updates all imports in the modules/ directory to use models from the models/ directory
instead of duplicate definitions in modules/*/domain/models.py.
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

def get_files_to_update() -> List[str]:
    """Get all Python files that import from modules financial domain models."""
    files = []
    backend_dir = Path('.')
    
    for file_path in backend_dir.rglob('*.py'):
        if file_path.is_file():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'from modules.financial.domain.models import' in content:
                        files.append(str(file_path))
            except Exception:
                pass
    
    return files

def update_financial_imports(file_path: str) -> bool:
    """Update financial model imports in a file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Map of models that should come from models.financial instead
    model_mapping = {
        'Transaction': 'models.financial',
        'Earning': 'models.financial',
        'Payout': 'models.financial',
        'Invoice': 'models.financial',
        'TransactionType': 'models.financial',
        'TransactionStatus': 'models.financial',
        'PayoutStatus': 'models.financial',
        'PaymentMethod': 'models.financial',
    }
    
    # Models that are unique to modules/financial/domain/models.py
    unique_models = [
        'CommissionRule', 'CommissionTier', 'CryptoWallet', 'CryptoPayment',
        'CryptoPaymentStatus', 'CryptoNetwork', 'PaymentGatewayConfig',
        'BillingCycle', 'PayoutSchedule', 'FinancialTransaction', 'InvoiceStatus'
    ]
    
    # Process multiline imports
    import_pattern = r'from\s+modules\.financial\.domain\.models\s+import\s*\(([^)]+)\)'
    
    def process_imports(match):
        imports_str = match.group(1)
        imports = [imp.strip() for imp in imports_str.split(',')]
        
        # Separate imports by source
        models_financial = []
        modules_financial = []
        
        for imp in imports:
            imp = imp.strip()
            if imp in model_mapping:
                models_financial.append(imp)
            elif imp in unique_models:
                modules_financial.append(imp)
            else:
                # Unknown model, keep in modules for now
                modules_financial.append(imp)
        
        # Build new import statements
        new_imports = []
        
        if models_financial:
            if len(models_financial) == 1:
                new_imports.append(f'from models.financial import {models_financial[0]}')
            else:
                imports_str = ', '.join(models_financial)
                if len(imports_str) > 80:
                    imports_formatted = ',\\n    '.join(models_financial)
                    new_imports.append(f'from models.financial import (\\n    {imports_formatted}\\n)')
                else:
                    new_imports.append(f'from models.financial import {imports_str}')
        
        if modules_financial:
            if len(modules_financial) == 1:
                new_imports.append(f'from modules.financial.domain.models import {modules_financial[0]}')
            else:
                imports_str = ', '.join(modules_financial)
                if len(imports_str) > 80:
                    imports_formatted = ',\\n    '.join(modules_financial)
                    new_imports.append(f'from modules.financial.domain.models import \\n    {imports_formatted}\\n')
                else:
                    new_imports.append(f'from modules.financial.domain.models import {imports_str}')
        
        return '\\n'.join(new_imports)
    
    content = re.sub(import_pattern, process_imports, content, flags=re.MULTILINE | re.DOTALL)
    
    # Process single-line imports
    single_import_pattern = r'from\s+modules\.financial\.domain\.models\s+import\s+([^\\n]+)'
    
    def process_single_import(match):
        imports_str = match.group(1)
        imports = [imp.strip() for imp in imports_str.split(',')]
        
        # Same separation logic
        models_financial = []
        modules_financial = []
        
        for imp in imports:
            imp = imp.strip()
            if imp in model_mapping:
                models_financial.append(imp)
            elif imp in unique_models:
                modules_financial.append(imp)
            else:
                modules_financial.append(imp)
        
        new_imports = []
        if models_financial:
            new_imports.append(f'from models.financial import {", ".join(models_financial)}')
        if modules_financial:
            new_imports.append(f'from modules.financial.domain.models import {", ".join(modules_financial)}')
        
        return '\\n'.join(new_imports)
    
    # Apply single-line pattern only where multiline didn't match
    if 'from modules.financial.domain.models import (\n    ' not in content:
        content = re.sub(single_import_pattern,\n    process_single_import,\n    content\n)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False

def main():
    print("Phase 4: Updating Domain Layer imports...")
    print("=" * 60)
    
    # Get files to update
    files = get_files_to_update()
    print(f"Found {len(files)} files importing from modules.financial.domain.models")
    
    # Update files
    updated_count = 0
    for file_path in files:
        print(f"Processing: {file_path}")
        if update_financial_imports(file_path):
            updated_count += 1
            print(f"  ✓ Updated")
        else:
            print(f"  - No changes needed")
    
    print("\\n" + "=" * 60)
    print(f"Phase 4 complete: Updated {updated_count} files")
    
    # Now we need to update the modules/financial/domain/models.py to remove duplicates
    print("\\nRemoving duplicate models from modules/financial/domain/models.py...")
    
    models_file = 'modules/financial/domain/models.py'
    if os.path.exists(models_file):
        with open(models_file, 'r') as f:
            content = f.read()
        
        # Comment out duplicate model definitions
        duplicates = ['Invoice', 'Payout', 'PayoutStatus', 'TransactionStatus', 'TransactionType']
        
        for model in duplicates:
            # Comment out class definitions
            pattern = rf'^(class {model}.*?)(?=^class|\\Z)'
            content = re.sub(pattern, lambda m: '# ' + m.group(0).replace('\\n', '\\n# '), 
                           content, flags=re.MULTILINE | re.DOTALL)
        
        # Add import from models.financial at the top
        if 'from models.financial import' not in content:
            imports = 'from models.financial import Transaction, Earning, Payout, Invoice, TransactionType, TransactionStatus, PayoutStatus, PaymentMethod\\n\\n'
            # Insert after other imports
            lines = content.split('\\n')
            import_end = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith('import') and not line.startswith('from'):
                    import_end = i
                    break
            
            lines.insert(import_end, imports)
            content = '\\n'.join(lines)
        
        with open(models_file, 'w') as f:
            f.write(content)
        
        print(f"  ✓ Updated {models_file} - commented out duplicate models")

if __name__ == "__main__":
    main()