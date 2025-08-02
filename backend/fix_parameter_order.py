#!/usr/bin/env python3
"""Fix parameter ordering - move CurrentUser before optional parameters."""

import ast
import os
from pathlib import Path

def fix_parameter_order_in_file(file_path):
    """Fix parameter ordering in Python file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content)
        
        # Track if we made changes
        changed = False
        original_content = content
        
        # Process function definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if this function has CurrentUser parameter
                has_current_user = False
                current_user_idx = -1
                
                for i, arg in enumerate(node.args.args):
                    if arg.annotation and isinstance(arg.annotation, ast.Name):
                        if arg.annotation.id in ['CurrentUser', 'CurrentUserOptional']:
                            has_current_user = True
                            current_user_idx = i
                            break
                
                if has_current_user and current_user_idx > 0:
                    # Check if there are optional parameters before CurrentUser
                    defaults_start = len(node.args.args) - len(node.args.defaults)
                    
                    if current_user_idx >= defaults_start:
                        # CurrentUser is after optional parameters, we need to move it
                        # This is a simple fix - just swap parameter order in the source
                        
                        # Find the function definition in the source
                        func_line = node.lineno - 1
                        lines = content.split('\n')
                        
                        # Look for the function definition
                        func_start = func_line
                        while func_start < len(lines) and 'def ' not in lines[func_start]:
                            func_start += 1
                        
                        # Find the end of the function signature
                        func_end = func_start
                        paren_count = 0
                        in_func = False
                        
                        for i in range(func_start, len(lines)):
                            line = lines[i]
                            for char in line:
                                if char == '(':
                                    paren_count += 1
                                    in_func = True
                                elif char == ')':
                                    paren_count -= 1
                                    if paren_count == 0 and in_func:
                                        func_end = i
                                        break
                            if func_end != func_start:
                                break
                        
                        # Extract function signature
                        func_lines = lines[func_start:func_end+1]
                        func_sig = '\n'.join(func_lines)
                        
                        # Simple fix: move current_user parameter before first optional parameter
                        if 'current_user: CurrentUser' in func_sig:
                            # Remove current_user line
                            new_lines = []
                            current_user_line = None
                            
                            for line in func_lines:
                                if 'current_user: CurrentUser' in line:
                                    current_user_line = line.strip().rstrip(',')
                                else:
                                    new_lines.append(line)
                            
                            if current_user_line:
                                # Find first parameter with default value
                                insert_idx = 0
                                for i, line in enumerate(new_lines):
                                    if '=' in line and 'def ' not in line:
                                        insert_idx = i
                                        break
                                
                                # Insert current_user before first optional parameter
                                if insert_idx > 0:
                                    new_lines.insert(insert_idx, '    ' + current_user_line + ',')
                                    
                                    # Replace in original content
                                    new_func = '\n'.join(new_lines)
                                    content = content.replace(func_sig, new_func)
                                    changed = True
        
        if changed and content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"Fixed parameter order in {file_path}")
            return True
            
    except Exception as e:
        # For complex cases, use a simpler regex-based approach
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Simple pattern to fix common case
            import re
            
            # Pattern to find function with current_user after optional params
            pattern = r'(async def \w+\([^)]*?)(\s*\w+:\s*\w+\s*=\s*[^,\)]+,)([^)]*?)(current_user:\s*CurrentUser(?:Optional)?),([^)]*?\))'
            
            def reorder(match):
                prefix = match.group(1)
                optional_param = match.group(2)
                middle = match.group(3)
                current_user = match.group(4)
                suffix = match.group(5)
                
                # Put current_user before optional parameters
                return f"{prefix}{current_user},{optional_param}{middle}{suffix}"
            
            content = re.sub(pattern, reorder, content, flags=re.DOTALL)
            
            if content != original_content:
                with open(file_path, 'w') as f:
                    f.write(content)
                print(f"Fixed parameter order in {file_path} (regex method)")
                return True
                
        except Exception as e2:
            print(f"Could not fix {file_path}: {e2}")
    
    return False

def main():
    backend_dir = Path(__file__).parent
    
    # Find all Python files that might have this issue
    dirs_to_check = [
        backend_dir / "api" / "v1" / "endpoints",
        backend_dir / "modules",
    ]
    
    print("Fixing parameter ordering issues...")
    fixed_count = 0
    
    for dir_path in dirs_to_check:
        if dir_path.exists():
            for py_file in dir_path.rglob("*.py"):
                if fix_parameter_order_in_file(py_file):
                    fixed_count += 1
    
    print(f"\nFixed {fixed_count} files!")

if __name__ == "__main__":
    main()