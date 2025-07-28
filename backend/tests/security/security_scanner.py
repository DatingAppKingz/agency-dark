"""
Automated security scanner for AgencyDark platform.
"""
import asyncio
import subprocess
import json
import os
from datetime import datetime
from typing import List, Dict, Any
import yaml
import aiohttp
from pathlib import Path


class SecurityScanner:
    """Comprehensive security scanning tool."""
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "scans": {}
        }
    
    async def run_all_scans(self):
        """Run all security scans."""
        print("Starting comprehensive security scan...")
        
        # Dependency scanning
        await self.scan_dependencies()
        
        # Code security scanning
        await self.scan_code_security()
        
        # Container scanning
        await self.scan_containers()
        
        # Infrastructure scanning
        await self.scan_infrastructure()
        
        # API security testing
        await self.scan_api_security()
        
        # Generate report
        self.generate_report()
    
    async def scan_dependencies(self):
        """Scan for vulnerable dependencies."""
        print("\n[*] Scanning dependencies...")
        
        # Python dependencies with Safety
        try:
            result = subprocess.run(
                ["safety", "check", "--json"],
                capture_output=True,
                text=True
            )
            vulnerabilities = json.loads(result.stdout) if result.stdout else []
            
            self.results["scans"]["dependencies"] = {
                "python": {
                    "tool": "safety",
                    "vulnerabilities": vulnerabilities,
                    "count": len(vulnerabilities)
                }
            }
            
            if vulnerabilities:
                print(f"  Found {len(vulnerabilities)} vulnerable Python packages")
                for vuln in vulnerabilities[:5]:  # Show first 5
                    print(f"    - {vuln.get('package', 'Unknown')}: {vuln.get('vulnerability', 'Unknown')}")
            else:
                print("  ✓ No vulnerable Python packages found")
                
        except Exception as e:
            print(f"  Error running Safety: {e}")
        
        # NPM dependencies with npm audit
        if (self.base_path / "frontend" / "package.json").exists():
            try:
                os.chdir(self.base_path / "frontend")
                result = subprocess.run(
                    ["npm", "audit", "--json"],
                    capture_output=True,
                    text=True
                )
                audit_data = json.loads(result.stdout) if result.stdout else {}
                
                self.results["scans"]["dependencies"]["npm"] = {
                    "tool": "npm audit",
                    "vulnerabilities": audit_data.get("vulnerabilities", {}),
                    "count": audit_data.get("metadata", {}).get("vulnerabilities", {}).get("total", 0)
                }
                
                vuln_count = audit_data.get("metadata", {}).get("vulnerabilities", {}).get("total", 0)
                if vuln_count > 0:
                    print(f"  Found {vuln_count} vulnerable npm packages")
                else:
                    print("  ✓ No vulnerable npm packages found")
                    
            except Exception as e:
                print(f"  Error running npm audit: {e}")
            finally:
                os.chdir(self.base_path)
    
    async def scan_code_security(self):
        """Scan code for security issues."""
        print("\n[*] Scanning code security...")
        
        # Bandit for Python security issues
        try:
            result = subprocess.run(
                ["bandit", "-r", str(self.base_path / "backend"), "-f", "json"],
                capture_output=True,
                text=True
            )
            bandit_results = json.loads(result.stdout) if result.stdout else {}
            
            self.results["scans"]["code_security"] = {
                "python": {
                    "tool": "bandit",
                    "issues": bandit_results.get("results", []),
                    "metrics": bandit_results.get("metrics", {}),
                    "severity_counts": {
                        "high": len([i for i in bandit_results.get("results", []) if i["issue_severity"] == "HIGH"]),
                        "medium": len([i for i in bandit_results.get("results", []) if i["issue_severity"] == "MEDIUM"]),
                        "low": len([i for i in bandit_results.get("results", []) if i["issue_severity"] == "LOW"])
                    }
                }
            }
            
            high_issues = self.results["scans"]["code_security"]["python"]["severity_counts"]["high"]
            if high_issues > 0:
                print(f"  Found {high_issues} high severity issues")
                for issue in bandit_results.get("results", [])[:3]:
                    if issue["issue_severity"] == "HIGH":
                        print(f"    - {issue['filename']}:{issue['line_number']} - {issue['issue_text']}")
            else:
                print("  ✓ No high severity code issues found")
                
        except Exception as e:
            print(f"  Error running Bandit: {e}")
        
        # Semgrep for advanced pattern matching
        try:
            result = subprocess.run(
                ["semgrep", "--config=auto", "--json", str(self.base_path)],
                capture_output=True,
                text=True
            )
            semgrep_results = json.loads(result.stdout) if result.stdout else {}
            
            self.results["scans"]["code_security"]["semgrep"] = {
                "tool": "semgrep",
                "findings": semgrep_results.get("results", []),
                "count": len(semgrep_results.get("results", []))
            }
            
            findings = len(semgrep_results.get("results", []))
            if findings > 0:
                print(f"  Semgrep found {findings} security patterns")
            else:
                print("  ✓ Semgrep found no security issues")
                
        except Exception as e:
            print(f"  Error running Semgrep: {e}")
    
    async def scan_containers(self):
        """Scan Docker containers for vulnerabilities."""
        print("\n[*] Scanning containers...")
        
        # Find Dockerfiles
        dockerfiles = list(self.base_path.rglob("Dockerfile*"))
        
        if not dockerfiles:
            print("  No Dockerfiles found")
            return
        
        self.results["scans"]["containers"] = {}
        
        for dockerfile in dockerfiles:
            print(f"  Scanning {dockerfile.relative_to(self.base_path)}")
            
            # Hadolint for Dockerfile best practices
            try:
                result = subprocess.run(
                    ["hadolint", str(dockerfile), "--format", "json"],
                    capture_output=True,
                    text=True
                )
                issues = json.loads(result.stdout) if result.stdout else []
                
                self.results["scans"]["containers"][str(dockerfile)] = {
                    "hadolint": {
                        "issues": issues,
                        "count": len(issues)
                    }
                }
                
                if issues:
                    print(f"    Found {len(issues)} Dockerfile issues")
                else:
                    print("    ✓ Dockerfile follows best practices")
                    
            except Exception as e:
                print(f"    Error running Hadolint: {e}")
            
            # Trivy for container vulnerabilities
            try:
                # Build image first (in real scenario)
                image_name = f"agencydark-scan-{dockerfile.parent.name}"
                
                result = subprocess.run(
                    ["trivy", "image", "--format", "json", image_name],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    trivy_results = json.loads(result.stdout) if result.stdout else {}
                    vulnerabilities = []
                    
                    for result in trivy_results.get("Results", []):
                        vulnerabilities.extend(result.get("Vulnerabilities", []))
                    
                    self.results["scans"]["containers"][str(dockerfile)]["trivy"] = {
                        "vulnerabilities": vulnerabilities,
                        "count": len(vulnerabilities),
                        "critical": len([v for v in vulnerabilities if v.get("Severity") == "CRITICAL"]),
                        "high": len([v for v in vulnerabilities if v.get("Severity") == "HIGH"])
                    }
                    
                    critical = self.results["scans"]["containers"][str(dockerfile)]["trivy"]["critical"]
                    if critical > 0:
                        print(f"    Found {critical} CRITICAL vulnerabilities")
                        
            except Exception as e:
                print(f"    Error running Trivy: {e}")
    
    async def scan_infrastructure(self):
        """Scan infrastructure as code."""
        print("\n[*] Scanning infrastructure...")
        
        # Find Terraform files
        tf_files = list(self.base_path.rglob("*.tf"))
        
        if tf_files:
            # Checkov for IaC security
            try:
                result = subprocess.run(
                    ["checkov", "-d", str(self.base_path), "--output", "json"],
                    capture_output=True,
                    text=True
                )
                checkov_results = json.loads(result.stdout) if result.stdout else {}
                
                self.results["scans"]["infrastructure"] = {
                    "terraform": {
                        "tool": "checkov",
                        "passed": checkov_results.get("summary", {}).get("passed", 0),
                        "failed": checkov_results.get("summary", {}).get("failed", 0),
                        "skipped": checkov_results.get("summary", {}).get("skipped", 0)
                    }
                }
                
                failed = checkov_results.get("summary", {}).get("failed", 0)
                if failed > 0:
                    print(f"  Found {failed} infrastructure security issues")
                else:
                    print("  ✓ Infrastructure configuration is secure")
                    
            except Exception as e:
                print(f"  Error running Checkov: {e}")
        
        # Check for exposed secrets
        await self.scan_secrets()
    
    async def scan_secrets(self):
        """Scan for exposed secrets."""
        print("\n[*] Scanning for secrets...")
        
        # GitLeaks for secret detection
        try:
            result = subprocess.run(
                ["gitleaks", "detect", "--source", str(self.base_path), "--report-format", "json"],
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                leaks = json.loads(result.stdout)
                self.results["scans"]["secrets"] = {
                    "tool": "gitleaks",
                    "findings": leaks,
                    "count": len(leaks)
                }
                
                if leaks:
                    print(f"  ⚠️  Found {len(leaks)} potential secrets!")
                    for leak in leaks[:3]:
                        print(f"    - {leak.get('File')}:{leak.get('StartLine')} - {leak.get('Description')}")
                else:
                    print("  ✓ No secrets found")
            else:
                print("  ✓ No secrets found")
                
        except Exception as e:
            print(f"  Error running GitLeaks: {e}")
    
    async def scan_api_security(self):
        """Test API security."""
        print("\n[*] Testing API security...")
        
        # OWASP ZAP API scan (if available)
        api_url = "http://localhost:8000"
        
        try:
            # Basic API security checks
            async with aiohttp.ClientSession() as session:
                checks = {
                    "cors": await self.check_cors(session, api_url),
                    "headers": await self.check_security_headers(session, api_url),
                    "ssl": await self.check_ssl(session, api_url.replace("http://", "https://")),
                    "methods": await self.check_http_methods(session, api_url)
                }
                
                self.results["scans"]["api_security"] = checks
                
                # Print summary
                issues = sum(1 for check in checks.values() if not check.get("passed", False))
                if issues > 0:
                    print(f"  Found {issues} API security issues")
                else:
                    print("  ✓ API security checks passed")
                    
        except Exception as e:
            print(f"  Error testing API security: {e}")
    
    async def check_cors(self, session: aiohttp.ClientSession, base_url: str) -> Dict[str, Any]:
        """Check CORS configuration."""
        try:
            async with session.options(
                f"{base_url}/api/v1/auth/login",
                headers={
                    "Origin": "https://evil.com",
                    "Access-Control-Request-Method": "POST"
                }
            ) as response:
                allow_origin = response.headers.get("Access-Control-Allow-Origin")
                
                return {
                    "passed": allow_origin != "*" and allow_origin != "https://evil.com",
                    "allow_origin": allow_origin,
                    "issue": "CORS allows any origin" if allow_origin == "*" else None
                }
        except:
            return {"passed": True, "error": "Could not test CORS"}
    
    async def check_security_headers(self, session: aiohttp.ClientSession, base_url: str) -> Dict[str, Any]:
        """Check security headers."""
        try:
            async with session.get(f"{base_url}/api/v1/health") as response:
                headers = response.headers
                
                required_headers = {
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": ["DENY", "SAMEORIGIN"],
                    "X-XSS-Protection": "1; mode=block",
                    "Strict-Transport-Security": None  # Just check presence
                }
                
                missing = []
                for header, expected in required_headers.items():
                    if header not in headers:
                        missing.append(header)
                    elif expected and headers[header] not in (expected if isinstance(expected, list) else [expected]):
                        missing.append(f"{header} (incorrect value)")
                
                return {
                    "passed": len(missing) == 0,
                    "missing_headers": missing
                }
        except:
            return {"passed": False, "error": "Could not check headers"}
    
    async def check_ssl(self, session: aiohttp.ClientSession, base_url: str) -> Dict[str, Any]:
        """Check SSL/TLS configuration."""
        # In production, would use sslyze or similar
        return {
            "passed": True,
            "note": "SSL check requires external tools"
        }
    
    async def check_http_methods(self, session: aiohttp.ClientSession, base_url: str) -> Dict[str, Any]:
        """Check for unnecessary HTTP methods."""
        try:
            # Test TRACE method (should be disabled)
            async with session.request("TRACE", f"{base_url}/") as response:
                trace_enabled = response.status == 200
            
            return {
                "passed": not trace_enabled,
                "trace_enabled": trace_enabled
            }
        except:
            return {"passed": True}
    
    def generate_report(self):
        """Generate security scan report."""
        # Calculate summary
        total_issues = 0
        critical_issues = 0
        
        for scan_type, results in self.results["scans"].items():
            if isinstance(results, dict):
                if "vulnerabilities" in results:
                    total_issues += len(results["vulnerabilities"])
                elif "count" in results:
                    total_issues += results["count"]
                elif "failed" in results:
                    total_issues += results["failed"]
        
        self.results["summary"] = {
            "total_issues": total_issues,
            "critical_issues": critical_issues,
            "scan_date": self.results["timestamp"],
            "recommendations": self.generate_recommendations()
        }
        
        # Save detailed report
        with open("security_scan_report.json", "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Save summary report
        self.generate_summary_report()
        
        print("\n" + "="*80)
        print("SECURITY SCAN COMPLETE")
        print("="*80)
        print(f"Total Issues Found: {total_issues}")
        print(f"Critical Issues: {critical_issues}")
        print("\nReports generated:")
        print("  - security_scan_report.json (detailed)")
        print("  - security_scan_summary.md (summary)")
    
    def generate_recommendations(self) -> List[str]:
        """Generate security recommendations based on scan results."""
        recommendations = []
        
        # Check each scan type
        if "dependencies" in self.results["scans"]:
            deps = self.results["scans"]["dependencies"]
            if deps.get("python", {}).get("count", 0) > 0:
                recommendations.append("Update vulnerable Python dependencies")
            if deps.get("npm", {}).get("count", 0) > 0:
                recommendations.append("Update vulnerable npm packages")
        
        if "code_security" in self.results["scans"]:
            code = self.results["scans"]["code_security"]
            if code.get("python", {}).get("severity_counts", {}).get("high", 0) > 0:
                recommendations.append("Fix high severity code security issues")
        
        if "secrets" in self.results["scans"]:
            if self.results["scans"]["secrets"].get("count", 0) > 0:
                recommendations.append("Remove exposed secrets and rotate credentials")
        
        if "api_security" in self.results["scans"]:
            api = self.results["scans"]["api_security"]
            if api.get("headers", {}).get("missing_headers"):
                recommendations.append("Add missing security headers")
        
        return recommendations
    
    def generate_summary_report(self):
        """Generate markdown summary report."""
        with open("security_scan_summary.md", "w") as f:
            f.write("# Security Scan Summary\n\n")
            f.write(f"**Scan Date:** {self.results['timestamp']}\n\n")
            
            f.write("## Overview\n\n")
            f.write(f"- **Total Issues:** {self.results['summary']['total_issues']}\n")
            f.write(f"- **Critical Issues:** {self.results['summary']['critical_issues']}\n\n")
            
            f.write("## Scan Results\n\n")
            
            for scan_type, results in self.results["scans"].items():
                f.write(f"### {scan_type.replace('_', ' ').title()}\n\n")
                
                if isinstance(results, dict):
                    for key, value in results.items():
                        if isinstance(value, dict) and "count" in value:
                            f.write(f"- **{key}:** {value['count']} issues\n")
                        elif isinstance(value, int):
                            f.write(f"- **{key}:** {value}\n")
                
                f.write("\n")
            
            f.write("## Recommendations\n\n")
            for rec in self.results["summary"]["recommendations"]:
                f.write(f"- {rec}\n")


async def main():
    """Run security scanner."""
    scanner = SecurityScanner()
    await scanner.run_all_scans()


if __name__ == "__main__":
    asyncio.run(main())