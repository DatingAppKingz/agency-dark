"""
Mutation testing configuration and tests
Using mutmut for Python mutation testing
"""
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any
import ast
import os


class MutationTester:
    """Mutation testing orchestrator"""
    
    def __init__(self, source_path: str = "backend", test_path: str = "backend/tests"):
        self.source_path = source_path
        self.test_path = test_path
        self.results: Dict[str, Any] = {}
    
    def run_mutation_tests(self, target_modules: List[str] = None):
        """Run mutation tests on specified modules"""
        if target_modules is None:
            target_modules = self._find_critical_modules()
        
        for module in target_modules:
            print(f"Running mutation tests on {module}...")
            result = self._run_mutmut_on_module(module)
            self.results[module] = result
        
        return self.results
    
    def _find_critical_modules(self) -> List[str]:
        """Identify critical modules that need mutation testing"""
        critical_patterns = [
            "auth",
            "security",
            "payment",
            "core/database",
            "core/cache",
            "api/v1/endpoints"
        ]
        
        modules = []
        for root, dirs, files in os.walk(self.source_path):
            for file in files:
                if file.endswith('.py') and not file.startswith('test_'):
                    filepath = os.path.join(root, file)
                    
                    # Check if it matches critical patterns
                    for pattern in critical_patterns:
                        if pattern in filepath:
                            modules.append(filepath)
                            break
        
        return modules
    
    def _run_mutmut_on_module(self, module_path: str) -> Dict[str, Any]:
        """Run mutmut on a specific module"""
        try:
            # Run mutmut
            cmd = [
                "mutmut", "run",
                "--paths-to-mutate", module_path,
                "--tests-dir", self.test_path,
                "--runner", "pytest -x",
                "--use-coverage"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse results
            if result.returncode == 0:
                # Get results
                results_cmd = ["mutmut", "results"]
                results_output = subprocess.run(results_cmd, capture_output=True, text=True)
                
                return self._parse_mutmut_results(results_output.stdout)
            else:
                return {"error": result.stderr}
                
        except Exception as e:
            return {"error": str(e)}
    
    def _parse_mutmut_results(self, output: str) -> Dict[str, Any]:
        """Parse mutmut results output"""
        lines = output.strip().split('\n')
        
        results = {
            "killed": 0,
            "survived": 0,
            "incompetent": 0,
            "timeout": 0,
            "suspicious": 0
        }
        
        for line in lines:
            for status in results.keys():
                if status in line.lower():
                    # Extract number
                    import re
                    match = re.search(r'\d+', line)
                    if match:
                        results[status] = int(match.group())
        
        # Calculate mutation score
        total = sum(results.values())
        if total > 0:
            results["mutation_score"] = (results["killed"] / total) * 100
        else:
            results["mutation_score"] = 0
        
        return results
    
    def generate_report(self, output_path: str = "mutation_report.md"):
        """Generate mutation testing report"""
        content = """# Mutation Testing Report

## Summary

Mutation testing helps ensure test quality by introducing small changes (mutations) to the code and checking if tests catch these changes.

## Results by Module

"""
        
        total_killed = 0
        total_survived = 0
        
        for module, results in self.results.items():
            if "error" in results:
                content += f"### {module}\n\n❌ Error: {results['error']}\n\n"
                continue
            
            total_killed += results["killed"]
            total_survived += results["survived"]
            
            content += f"""### {module}

- **Mutation Score**: {results['mutation_score']:.1f}%
- **Killed**: {results['killed']}
- **Survived**: {results['survived']}
- **Incompetent**: {results['incompetent']}
- **Timeout**: {results['timeout']}

"""
            
            # Add specific survived mutations if available
            if results["survived"] > 0:
                content += "#### Survived Mutations\n\n"
                survived = self._get_survived_mutations(module)
                for mutation in survived[:5]:  # Show top 5
                    content += f"- Line {mutation['line']}: {mutation['mutation']}\n"
                
                if len(survived) > 5:
                    content += f"\n... and {len(survived) - 5} more\n"
        
        # Overall score
        if total_killed + total_survived > 0:
            overall_score = (total_killed / (total_killed + total_survived)) * 100
            content += f"\n## Overall Mutation Score: {overall_score:.1f}%\n"
        
        with open(output_path, "w") as f:
            f.write(content)
    
    def _get_survived_mutations(self, module: str) -> List[Dict[str, Any]]:
        """Get details of survived mutations"""
        cmd = ["mutmut", "show", "--all"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse output for survived mutations
        # This is simplified - actual parsing would be more complex
        survived = []
        
        return survived


class MutationGenerator:
    """Generate custom mutations for testing"""
    
    @staticmethod
    def generate_boundary_mutations(code: str) -> List[str]:
        """Generate boundary condition mutations"""
        mutations = []
        
        # Parse code
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                # Mutate comparison operators
                for i, op in enumerate(node.ops):
                    if isinstance(op, ast.Lt):
                        # Change < to <=
                        mutations.append("Change < to <=")
                    elif isinstance(op, ast.Gt):
                        # Change > to >=
                        mutations.append("Change > to >=")
                    elif isinstance(op, ast.Eq):
                        # Change == to !=
                        mutations.append("Change == to !=")
            
            elif isinstance(node, ast.BinOp):
                # Mutate arithmetic operators
                if isinstance(node.op, ast.Add):
                    mutations.append("Change + to -")
                elif isinstance(node.op, ast.Sub):
                    mutations.append("Change - to +")
                elif isinstance(node.op, ast.Mult):
                    mutations.append("Change * to /")
        
        return mutations
    
    @staticmethod
    def generate_security_mutations(code: str) -> List[str]:
        """Generate security-focused mutations"""
        mutations = []
        
        # Look for security-relevant patterns
        security_patterns = [
            ("if.*authenticated", "Remove authentication check"),
            ("if.*authorized", "Remove authorization check"),
            ("validate.*input", "Remove input validation"),
            ("sanitize", "Remove sanitization"),
            ("escape", "Remove escaping"),
            ("hash.*password", "Remove password hashing")
        ]
        
        for pattern, mutation in security_patterns:
            import re
            if re.search(pattern, code, re.IGNORECASE):
                mutations.append(mutation)
        
        return mutations


# Mutation test specifications
class MutationTestSpec:
    """Define specific mutation test cases"""
    
    @staticmethod
    def test_authentication_mutations():
        """Test mutations in authentication code"""
        mutations = [
            {
                "module": "auth/auth_service.py",
                "function": "verify_password",
                "mutations": [
                    "Return True always",
                    "Return False always",
                    "Skip password hashing",
                    "Change comparison operator"
                ]
            },
            {
                "module": "auth/auth_service.py",
                "function": "create_access_token",
                "mutations": [
                    "Change token expiration time",
                    "Remove user ID from token",
                    "Change token algorithm",
                    "Remove token signature"
                ]
            }
        ]
        
        return mutations
    
    @staticmethod
    def test_authorization_mutations():
        """Test mutations in authorization code"""
        mutations = [
            {
                "module": "auth/permissions.py",
                "function": "has_permission",
                "mutations": [
                    "Always return True",
                    "Always return False",
                    "Invert permission check",
                    "Skip role verification"
                ]
            }
        ]
        
        return mutations
    
    @staticmethod
    def test_data_validation_mutations():
        """Test mutations in data validation"""
        mutations = [
            {
                "module": "api/validators.py",
                "function": "validate_email",
                "mutations": [
                    "Accept any string as email",
                    "Reject all emails",
                    "Remove @ check",
                    "Remove domain validation"
                ]
            },
            {
                "module": "api/validators.py",
                "function": "validate_password",
                "mutations": [
                    "Accept any password",
                    "Remove length check",
                    "Remove complexity check",
                    "Remove special character requirement"
                ]
            }
        ]
        
        return mutations


# Configuration for mutmut
MUTMUT_CONFIG = """
[mutmut]
paths_to_mutate = backend/
backup = False
runner = pytest -x -q
tests_dir = backend/tests/
dict_synonyms = 
    Struct, NamedStruct
    
# Exclude patterns
exclude_patterns = 
    */migrations/*
    */tests/*
    */venv/*
    */__pycache__/*
    
# Mutation operators to use
operators = 
    standard
    logical
    arithmetic
    comparison
    assignment
"""


def setup_mutation_testing():
    """Setup mutation testing configuration"""
    # Write mutmut config
    with open(".mutmut.conf", "w") as f:
        f.write(MUTMUT_CONFIG)
    
    # Install mutmut if not present
    try:
        import mutmut
    except ImportError:
        subprocess.run(["pip", "install", "mutmut"])
    
    print("Mutation testing setup complete")


def run_mutation_campaign():
    """Run a full mutation testing campaign"""
    tester = MutationTester()
    
    # Define critical modules
    critical_modules = [
        "backend/modules/auth/application/auth_service.py",
        "backend/modules/auth/domain/permissions.py",
        "backend/api/v1/endpoints/auth.py",
        "backend/core/security.py",
        "backend/core/database.py",
        "backend/core/cache.py"
    ]
    
    # Run tests
    results = tester.run_mutation_tests(critical_modules)
    
    # Generate report
    tester.generate_report()
    
    # Check if mutation score meets threshold
    overall_score = calculate_overall_score(results)
    
    if overall_score < 80:
        print(f"⚠️  Mutation score {overall_score:.1f}% is below threshold (80%)")
        print("Consider improving test coverage and quality")
        return False
    else:
        print(f"✅ Mutation score {overall_score:.1f}% meets threshold")
        return True


def calculate_overall_score(results: Dict[str, Any]) -> float:
    """Calculate overall mutation score"""
    total_killed = 0
    total_mutations = 0
    
    for module, result in results.items():
        if "error" not in result:
            total_killed += result["killed"]
            total_mutations += sum([
                result["killed"],
                result["survived"],
                result["incompetent"],
                result["timeout"]
            ])
    
    if total_mutations == 0:
        return 0
    
    return (total_killed / total_mutations) * 100


if __name__ == "__main__":
    setup_mutation_testing()
    success = run_mutation_campaign()
    exit(0 if success else 1)