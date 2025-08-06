#!/usr/bin/env python3
"""
Audit all Python imports in the project to identify dependencies.
"""
import ast
import os
from pathlib import Path
from collections import defaultdict
import json

def find_imports(directory):
    """Find all imports in Python files."""
    imports = defaultdict(set)
    
    for py_file in Path(directory).rglob("*.py"):
        # Skip virtual environments and cache
        if any(skip in str(py_file) for skip in ['venv', '__pycache__', '.git', 'node_modules']):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        module_name = name.name.split('.')[0]
                        imports[module_name].add(str(py_file.relative_to(directory)))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split('.')[0]
                        imports[module_name].add(str(py_file.relative_to(directory)))
        except Exception as e:
            print(f"Error parsing {py_file}: {e}")
    
    return imports

def categorize_imports(imports):
    """Categorize imports into standard library, third-party, and local."""
    import sys
    
    stdlib_modules = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else {
        'os', 'sys', 'time', 'datetime', 'json', 're', 'math', 'random',
        'collections', 'itertools', 'functools', 'pathlib', 'typing',
        'asyncio', 'threading', 'multiprocessing', 'subprocess', 'uuid',
        'hashlib', 'secrets', 'string', 'enum', 'copy', 'pickle', 'base64'
    }
    
    local_modules = {'api', 'core', 'models', 'schemas', 'services', 'utils', 'middleware', 'tasks', 'ml', 'modules'}
    
    categorized = {
        'stdlib': {},
        'third_party': {},
        'local': {}
    }
    
    for module, files in imports.items():
        if module in stdlib_modules:
            categorized['stdlib'][module] = list(files)
        elif module in local_modules:
            categorized['local'][module] = list(files)
        else:
            categorized['third_party'][module] = list(files)
    
    return categorized

# Run audit
print("Auditing dependencies in backend/...")
backend_imports = find_imports("backend/")
categorized = categorize_imports(backend_imports)

# Generate report
report = {
    'total_modules': len(backend_imports),
    'stdlib_count': len(categorized['stdlib']),
    'third_party_count': len(categorized['third_party']),
    'local_count': len(categorized['local']),
    'third_party_modules': sorted(categorized['third_party'].keys()),
    'security_related': []
}

# Identify security-related imports
security_keywords = ['auth', 'jwt', 'password', 'security', 'crypt', 'token', 'session', 'rbac', 'permission']
for module in categorized['third_party']:
    if any(keyword in module.lower() for keyword in security_keywords):
        report['security_related'].append(module)

# Save detailed report
with open("dependency_audit.json", "w") as f:
    json.dump(categorized, f, indent=2)

# Print summary
print("\n📊 Dependency Audit Summary")
print("=" * 50)
print(f"Total unique modules imported: {report['total_modules']}")
print(f"Standard library modules: {report['stdlib_count']}")
print(f"Third-party modules: {report['third_party_count']}")
print(f"Local modules: {report['local_count']}")

print("\n📦 Third-party dependencies found:")
for module in report['third_party_modules']:
    file_count = len(categorized['third_party'][module])
    print(f"  - {module} (used in {file_count} files)")

if report['security_related']:
    print("\n🔐 Security-related modules:")
    for module in report['security_related']:
        print(f"  - {module}")

print("\n✅ Full report saved to: dependency_audit.json")