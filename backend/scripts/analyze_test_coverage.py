#!/usr/bin/env python3
"""
Analyze test coverage and identify areas needing improvement.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
import json

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def find_source_files(directory: Path, exclude_dirs: List[str] = None) -> List[Path]:
    """Find all Python source files."""
    if exclude_dirs is None:
        exclude_dirs = ['tests', 'venv', 'env', '__pycache__', 'migrations', 'alembic', 'scripts', 'node_modules']
    
    source_files = []
    for path in directory.rglob('*.py'):
        # Skip if in excluded directory
        if any(excluded in path.parts for excluded in exclude_dirs):
            continue
        
        # Skip __init__.py files
        if path.name == '__init__.py':
            continue
            
        source_files.append(path)
    
    return source_files

def find_test_files(test_dir: Path) -> Dict[str, List[Path]]:
    """Find all test files and categorize them."""
    test_files = {
        'unit': [],
        'integration': [],
        'performance': [],
        'security': [],
        'contract': [],
        'other': []
    }
    
    for path in test_dir.rglob('test_*.py'):
        if 'unit' in path.parts:
            test_files['unit'].append(path)
        elif 'integration' in path.parts:
            test_files['integration'].append(path)
        elif 'performance' in path.parts:
            test_files['performance'].append(path)
        elif 'security' in path.parts:
            test_files['security'].append(path)
        elif 'contract' in path.parts:
            test_files['contract'].append(path)
        else:
            test_files['other'].append(path)
    
    return test_files

def map_source_to_tests(source_files: List[Path], test_files: Dict[str, List[Path]]) -> Dict[Path, List[Path]]:
    """Map source files to their corresponding test files."""
    source_test_map = {}
    
    all_tests = []
    for category_tests in test_files.values():
        all_tests.extend(category_tests)
    
    for source in source_files:
        source_test_map[source] = []
        source_name = source.stem
        
        # Look for corresponding test files
        for test in all_tests:
            test_content = test.stem
            
            # Direct match (e.g., auth.py -> test_auth.py)
            if test_content == f"test_{source_name}":
                source_test_map[source].append(test)
                continue
            
            # Service match (e.g., auth_service.py -> test_auth.py)
            if source_name.endswith('_service') and test_content == f"test_{source_name.replace('_service', '')}":
                source_test_map[source].append(test)
                continue
            
            # Partial match
            if source_name in test_content:
                source_test_map[source].append(test)
    
    return source_test_map

def categorize_source_files(source_files: List[Path]) -> Dict[str, List[Path]]:
    """Categorize source files by functionality."""
    categories = {
        'api': [],
        'core': [],
        'models': [],
        'services': [],
        'security': [],
        'utils': [],
        'other': []
    }
    
    for source in source_files:
        path_str = str(source)
        
        if '/api/' in path_str or '/endpoints/' in path_str:
            categories['api'].append(source)
        elif '/core/' in path_str:
            categories['core'].append(source)
        elif '/models/' in path_str or 'model' in source.stem:
            categories['models'].append(source)
        elif '_service' in source.stem or '/services/' in path_str:
            categories['services'].append(source)
        elif '/security/' in path_str or 'auth' in source.stem or 'security' in source.stem:
            categories['security'].append(source)
        elif '/utils/' in path_str or 'util' in source.stem:
            categories['utils'].append(source)
        else:
            categories['other'].append(source)
    
    return categories

def analyze_coverage():
    """Analyze test coverage for the project."""
    backend_dir = Path(__file__).parent.parent
    tests_dir = backend_dir / 'tests'
    
    print("="*60)
    print("TEST COVERAGE ANALYSIS")
    print("="*60)
    
    # Find all source and test files
    print("\n1. Discovering files...")
    source_files = find_source_files(backend_dir)
    test_files = find_test_files(tests_dir)
    
    print(f"   Found {len(source_files)} source files")
    print(f"   Found {sum(len(tests) for tests in test_files.values())} test files")
    
    # Categorize files
    print("\n2. Categorizing files...")
    source_categories = categorize_source_files(source_files)
    
    print("\n   Source files by category:")
    for category, files in source_categories.items():
        print(f"   - {category}: {len(files)} files")
    
    print("\n   Test files by type:")
    for test_type, files in test_files.items():
        print(f"   - {test_type}: {len(files)} files")
    
    # Map source to tests
    print("\n3. Mapping source files to tests...")
    source_test_map = map_source_to_tests(source_files, test_files)
    
    # Find untested files
    untested_files = [source for source, tests in source_test_map.items() if not tests]
    partially_tested = [source for source, tests in source_test_map.items() if len(tests) == 1]
    well_tested = [source for source, tests in source_test_map.items() if len(tests) > 1]
    
    print(f"\n   Coverage summary:")
    print(f"   - Well tested (2+ test files): {len(well_tested)} files")
    print(f"   - Partially tested (1 test file): {len(partially_tested)} files")
    print(f"   - Not tested: {len(untested_files)} files")
    
    # Report untested files by category
    print("\n4. Untested files by category:")
    for category, files in source_categories.items():
        untested_in_category = [f for f in files if f in untested_files]
        if untested_in_category:
            print(f"\n   {category.upper()} ({len(untested_in_category)} untested):")
            for file in untested_in_category[:5]:  # Show first 5
                print(f"   - {file.relative_to(backend_dir)}")
            if len(untested_in_category) > 5:
                print(f"   ... and {len(untested_in_category) - 5} more")
    
    # Identify critical untested files
    print("\n5. Critical untested files (high priority):")
    critical_patterns = ['auth', 'security', 'payment', 'api', 'financial', 'commission']
    critical_untested = []
    
    for file in untested_files:
        if any(pattern in str(file).lower() for pattern in critical_patterns):
            critical_untested.append(file)
    
    for file in critical_untested[:10]:
        print(f"   ❗ {file.relative_to(backend_dir)}")
    
    # Generate recommendations
    print("\n6. RECOMMENDATIONS:")
    print("-" * 40)
    
    if critical_untested:
        print("\n   HIGH PRIORITY:")
        print(f"   - Add tests for {len(critical_untested)} critical untested files")
        print("     (auth, security, payment, financial modules)")
    
    if len(untested_files) > 0:
        coverage_estimate = (1 - len(untested_files) / len(source_files)) * 100
        print(f"\n   COVERAGE ESTIMATE: ~{coverage_estimate:.1f}%")
        print(f"   - Target: 80% minimum coverage")
        print(f"   - Need tests for {len(untested_files)} more files")
    
    # Test type recommendations
    print("\n   TEST TYPE BALANCE:")
    total_tests = sum(len(tests) for tests in test_files.values())
    if total_tests > 0:
        for test_type, tests in test_files.items():
            percentage = len(tests) / total_tests * 100
            print(f"   - {test_type}: {percentage:.1f}%")
    
    # Create test priority list
    print("\n7. Creating test priority list...")
    priority_list = create_test_priority_list(untested_files, source_categories)
    
    output_file = backend_dir / "TEST_PRIORITY_LIST.md"
    with open(output_file, 'w') as f:
        f.write("# Test Priority List\n\n")
        f.write("## High Priority (Security/Financial)\n\n")
        for file in priority_list['high'][:20]:
            f.write(f"- [ ] {file.relative_to(backend_dir)}\n")
        
        f.write("\n## Medium Priority (Core Services)\n\n")
        for file in priority_list['medium'][:20]:
            f.write(f"- [ ] {file.relative_to(backend_dir)}\n")
        
        f.write("\n## Low Priority (Utils/Other)\n\n")
        for file in priority_list['low'][:20]:
            f.write(f"- [ ] {file.relative_to(backend_dir)}\n")
    
    print(f"\n   ✅ Test priority list saved to: {output_file.name}")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"\nTotal source files: {len(source_files)}")
    print(f"Files with tests: {len(source_files) - len(untested_files)}")
    print(f"Files without tests: {len(untested_files)}")
    print(f"Estimated coverage: ~{coverage_estimate:.1f}%")
    print(f"\nNext steps:")
    print("1. Focus on high-priority untested files")
    print("2. Add integration tests for API endpoints")
    print("3. Improve test coverage for critical modules")
    print("4. Run pytest with coverage to get exact metrics")

def create_test_priority_list(untested_files: List[Path], categories: Dict[str, List[Path]]) -> Dict[str, List[Path]]:
    """Create prioritized list of files needing tests."""
    priority = {
        'high': [],
        'medium': [],
        'low': []
    }
    
    high_priority_patterns = ['auth', 'security', 'payment', 'financial', 'commission', 'api', 'webhook']
    medium_priority_patterns = ['service', 'core', 'models', 'sync', 'integration']
    
    for file in untested_files:
        file_str = str(file).lower()
        
        if any(pattern in file_str for pattern in high_priority_patterns):
            priority['high'].append(file)
        elif any(pattern in file_str for pattern in medium_priority_patterns):
            priority['medium'].append(file)
        else:
            priority['low'].append(file)
    
    # Sort by filename for consistency
    for level in priority:
        priority[level].sort(key=lambda x: x.name)
    
    return priority

if __name__ == '__main__':
    analyze_coverage()