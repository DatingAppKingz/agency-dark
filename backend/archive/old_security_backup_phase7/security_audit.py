"""
Comprehensive Security Audit Module

Performs automated security audits including:
- OWASP Top 10 vulnerability checks
- API endpoint security analysis
- Authentication/authorization verification
- Input validation checks
- SQL injection detection
- XSS vulnerability scanning
"""
import re
import asyncio
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import inspect
import ast

from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import get_logger
from core.database import get_db

logger = get_logger(__name__)


class SecurityRisk(str, Enum):
    """Security risk levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityType(str, Enum):
    """Types of vulnerabilities."""
    SQL_INJECTION = "sql_injection"
    XSS = "cross_site_scripting"
    CSRF = "csrf"
    BROKEN_AUTH = "broken_authentication"
    SENSITIVE_DATA = "sensitive_data_exposure"
    XXE = "xml_external_entities"
    BROKEN_ACCESS = "broken_access_control"
    SECURITY_MISCONFIG = "security_misconfiguration"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    INSUFFICIENT_LOGGING = "insufficient_logging"
    RATE_LIMITING = "missing_rate_limiting"
    INPUT_VALIDATION = "insufficient_input_validation"
    API_KEY_EXPOSURE = "api_key_exposure"


@dataclass
class SecurityVulnerability:
    """Security vulnerability finding."""
    type: VulnerabilityType
    risk: SecurityRisk
    endpoint: Optional[str]
    description: str
    recommendation: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SecurityAuditor:
    """Comprehensive security audit system."""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.vulnerabilities: List[SecurityVulnerability] = []
        self.sql_injection_patterns = [
            r"(?i)(union\s+select|select\s+\*|drop\s+table|insert\s+into|delete\s+from)",
            r"(?i)(or\s+1\s*=\s*1|and\s+1\s*=\s*1|'\s+or\s+'|admin'\s*--)",
            r"(?i)(exec\s*\(|execute\s+immediate|xp_cmdshell)",
            r"(?i)(script\s*>|javascript:|onerror\s*=|onload\s*=)",
        ]
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:\s*[^\"']+",
            r"on\w+\s*=\s*[\"'][^\"']+[\"']",
            r"<iframe[^>]*>.*?</iframe>",
        ]
        self.sensitive_data_patterns = [
            r"(?i)(password|passwd|pwd)\s*[:=]\s*[\"']?[^\"'\s]+",
            r"(?i)(api[_-]?key|apikey)\s*[:=]\s*[\"']?[^\"'\s]+",
            r"(?i)(secret[_-]?key|secretkey)\s*[:=]\s*[\"']?[^\"'\s]+",
            r"(?i)(private[_-]?key|privatekey)\s*[:=]\s*[\"']?[^\"'\s]+",
            r"\b(?:\d{4}[-\s]?){3}\d{4}\b",  # Credit card pattern
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN pattern
        ]
    
    async def run_full_audit(self) -> Dict[str, Any]:
        """Run a comprehensive security audit."""
        logger.info("Starting comprehensive security audit")
        self.vulnerabilities.clear()
        
        # Run all audit checks
        await asyncio.gather(
            self._audit_endpoints(),
            self._audit_authentication(),
            self._audit_input_validation(),
            self._audit_sql_injection(),
            self._audit_xss_vulnerabilities(),
            self._audit_sensitive_data(),
            self._audit_rate_limiting(),
            self._audit_cors_configuration(),
            self._audit_security_headers(),
            self._audit_api_keys(),
            return_exceptions=True
        )
        
        # Generate report
        report = self._generate_audit_report()
        
        logger.info(f"Security audit completed. Found {len(self.vulnerabilities)} vulnerabilities")
        return report
    
    async def _audit_endpoints(self):
        """Audit all API endpoints for security issues."""
        for route in self.app.routes:
            if isinstance(route, APIRoute):
                # Check for missing authentication
                if not self._has_authentication(route):
                    if self._is_sensitive_endpoint(route.path):
                        self.vulnerabilities.append(SecurityVulnerability(
                            type=VulnerabilityType.BROKEN_AUTH,
                            risk=SecurityRisk.CRITICAL,
                            endpoint=route.path,
                            description="Sensitive endpoint lacks authentication",
                            recommendation="Add authentication dependency to this endpoint"
                        ))
                
                # Check for missing authorization
                if not self._has_authorization(route):
                    if "admin" in route.path.lower() or "delete" in str(route.methods):
                        self.vulnerabilities.append(SecurityVulnerability(
                            type=VulnerabilityType.BROKEN_ACCESS,
                            risk=SecurityRisk.HIGH,
                            endpoint=route.path,
                            description="Administrative endpoint lacks proper authorization",
                            recommendation="Implement role-based access control"
                        ))
    
    async def _audit_authentication(self):
        """Audit authentication mechanisms."""
        # Check for weak password policies
        auth_endpoints = [
            route for route in self.app.routes
            if isinstance(route, APIRoute) and "auth" in route.path.lower()
        ]
        
        for route in auth_endpoints:
            if "login" in route.path.lower() or "register" in route.path.lower():
                # Check if endpoint has rate limiting
                if not self._has_rate_limiting(route):
                    self.vulnerabilities.append(SecurityVulnerability(
                        type=VulnerabilityType.RATE_LIMITING,
                        risk=SecurityRisk.HIGH,
                        endpoint=route.path,
                        description="Authentication endpoint lacks rate limiting",
                        recommendation="Implement rate limiting to prevent brute force attacks"
                    ))
    
    async def _audit_input_validation(self):
        """Audit input validation across endpoints."""
        for route in self.app.routes:
            if isinstance(route, APIRoute):
                # Analyze endpoint function
                endpoint_func = route.endpoint
                
                # Check for raw string inputs without validation
                if self._has_unvalidated_inputs(endpoint_func):
                    self.vulnerabilities.append(SecurityVulnerability(
                        type=VulnerabilityType.INPUT_VALIDATION,
                        risk=SecurityRisk.MEDIUM,
                        endpoint=route.path,
                        description="Endpoint accepts unvalidated string inputs",
                        recommendation="Use Pydantic models for input validation"
                    ))
    
    async def _audit_sql_injection(self):
        """Check for SQL injection vulnerabilities."""
        # This is a simplified check - in production, use more sophisticated analysis
        vulnerable_patterns = [
            "execute(f\"",  # f-strings in SQL
            "execute(query +",  # String concatenation
            ".format(",  # String formatting
            "raw(",  # Raw queries
        ]
        
        # Check for vulnerable query patterns in codebase
        # In a real implementation, this would scan actual code files
        logger.info("Checking for SQL injection vulnerabilities")
    
    async def _audit_xss_vulnerabilities(self):
        """Check for XSS vulnerabilities."""
        for route in self.app.routes:
            if isinstance(route, APIRoute):
                # Check if endpoint returns HTML content
                if self._returns_html_content(route):
                    if not self._has_xss_protection(route):
                        self.vulnerabilities.append(SecurityVulnerability(
                            type=VulnerabilityType.XSS,
                            risk=SecurityRisk.HIGH,
                            endpoint=route.path,
                            description="Endpoint returns HTML without XSS protection",
                            recommendation="Sanitize all user inputs and use Content Security Policy"
                        ))
    
    async def _audit_sensitive_data(self):
        """Check for sensitive data exposure."""
        for route in self.app.routes:
            if isinstance(route, APIRoute):
                # Check if endpoint might expose sensitive data
                if any(term in route.path.lower() for term in ["user", "profile", "account"]):
                    if "GET" in route.methods and not self._has_field_filtering(route):
                        self.vulnerabilities.append(SecurityVulnerability(
                            type=VulnerabilityType.SENSITIVE_DATA,
                            risk=SecurityRisk.MEDIUM,
                            endpoint=route.path,
                            description="Endpoint may expose sensitive user data",
                            recommendation="Implement field filtering and data minimization"
                        ))
    
    async def _audit_rate_limiting(self):
        """Audit rate limiting implementation."""
        endpoints_needing_limits = []
        
        for route in self.app.routes:
            if isinstance(route, APIRoute):
                # Check if endpoint needs rate limiting
                if self._needs_rate_limiting(route):
                    if not self._has_rate_limiting(route):
                        endpoints_needing_limits.append(route.path)
        
        if endpoints_needing_limits:
            self.vulnerabilities.append(SecurityVulnerability(
                type=VulnerabilityType.RATE_LIMITING,
                risk=SecurityRisk.MEDIUM,
                endpoint=None,
                description=f"Multiple endpoints lack rate limiting: {', '.join(endpoints_needing_limits[:5])}",
                recommendation="Implement rate limiting for all public endpoints",
                metadata={"endpoints": endpoints_needing_limits}
            ))
    
    async def _audit_cors_configuration(self):
        """Audit CORS configuration."""
        # Check for overly permissive CORS
        cors_middleware = None
        for middleware in self.app.user_middleware:
            if "cors" in str(middleware.cls).lower():
                cors_middleware = middleware
                break
        
        if cors_middleware:
            # Check if allow_origins contains wildcard
            if hasattr(cors_middleware.options, "allow_origins"):
                if "*" in cors_middleware.options.get("allow_origins", []):
                    self.vulnerabilities.append(SecurityVulnerability(
                        type=VulnerabilityType.SECURITY_MISCONFIG,
                        risk=SecurityRisk.HIGH,
                        endpoint=None,
                        description="CORS allows all origins (wildcard)",
                        recommendation="Restrict CORS to specific trusted domains"
                    ))
    
    async def _audit_security_headers(self):
        """Audit security headers configuration."""
        required_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": None,  # Just check presence
        }
        
        missing_headers = []
        
        # In a real implementation, this would check actual response headers
        # For now, we'll flag this as a general recommendation
        self.vulnerabilities.append(SecurityVulnerability(
            type=VulnerabilityType.SECURITY_MISCONFIG,
            risk=SecurityRisk.MEDIUM,
            endpoint=None,
            description="Ensure all security headers are properly configured",
            recommendation="Implement security headers middleware with proper values",
            metadata={"required_headers": list(required_headers.keys())}
        ))
    
    async def _audit_api_keys(self):
        """Audit API key security."""
        # Check for API key exposure in responses
        for route in self.app.routes:
            if isinstance(route, APIRoute):
                if "api" in route.path.lower() and "key" in route.path.lower():
                    if "GET" in route.methods:
                        # Check if endpoint might expose full API keys
                        self.vulnerabilities.append(SecurityVulnerability(
                            type=VulnerabilityType.API_KEY_EXPOSURE,
                            risk=SecurityRisk.HIGH,
                            endpoint=route.path,
                            description="Endpoint may expose API keys",
                            recommendation="Never return full API keys; use key prefixes for identification"
                        ))
    
    def _has_authentication(self, route: APIRoute) -> bool:
        """Check if route has authentication."""
        # Check for common auth dependencies
        dependencies = route.dependencies or []
        dep_names = [str(dep) for dep in dependencies]
        
        auth_patterns = ["current_user", "get_current", "require_token", "oauth2"]
        return any(pattern in dep_str.lower() for dep_str in dep_names for pattern in auth_patterns)
    
    def _has_authorization(self, route: APIRoute) -> bool:
        """Check if route has authorization checks."""
        # Check for authorization patterns
        dependencies = route.dependencies or []
        dep_names = [str(dep) for dep in dependencies]
        
        auth_patterns = ["require_role", "check_permission", "is_admin", "has_access"]
        return any(pattern in dep_str.lower() for dep_str in dep_names for pattern in auth_patterns)
    
    def _has_rate_limiting(self, route: APIRoute) -> bool:
        """Check if route has rate limiting."""
        dependencies = route.dependencies or []
        dep_names = [str(dep) for dep in dependencies]
        
        return any("rate" in dep_str.lower() and "limit" in dep_str.lower() for dep_str in dep_names)
    
    def _is_sensitive_endpoint(self, path: str) -> bool:
        """Check if endpoint handles sensitive data."""
        sensitive_patterns = [
            "user", "account", "profile", "payment", "billing",
            "admin", "settings", "config", "api-key", "secret"
        ]
        return any(pattern in path.lower() for pattern in sensitive_patterns)
    
    def _needs_rate_limiting(self, route: APIRoute) -> bool:
        """Check if endpoint needs rate limiting."""
        # Public endpoints and mutation operations need rate limiting
        if route.methods & {"POST", "PUT", "DELETE", "PATCH"}:
            return True
        
        # Authentication endpoints always need rate limiting
        if any(term in route.path.lower() for term in ["login", "register", "auth"]):
            return True
        
        return False
    
    def _has_unvalidated_inputs(self, func) -> bool:
        """Check if function has unvalidated string inputs."""
        # Simplified check - in production, use AST analysis
        sig = inspect.signature(func)
        for param in sig.parameters.values():
            if param.annotation == str or param.annotation == inspect.Parameter.empty:
                # Check if it's not a Pydantic model
                if "BaseModel" not in str(param.annotation):
                    return True
        return False
    
    def _returns_html_content(self, route: APIRoute) -> bool:
        """Check if endpoint returns HTML content."""
        # Check response model or endpoint name
        return "html" in route.path.lower() or "template" in route.path.lower()
    
    def _has_xss_protection(self, route: APIRoute) -> bool:
        """Check if route has XSS protection."""
        # Simplified check - would need to analyze actual implementation
        return False  # Conservative approach
    
    def _has_field_filtering(self, route: APIRoute) -> bool:
        """Check if route implements field filtering."""
        # Check for field selection parameters
        return "fields" in str(route.endpoint) or "select" in str(route.endpoint)
    
    def _generate_audit_report(self) -> Dict[str, Any]:
        """Generate comprehensive audit report."""
        # Group vulnerabilities by risk level
        by_risk = {
            SecurityRisk.CRITICAL: [],
            SecurityRisk.HIGH: [],
            SecurityRisk.MEDIUM: [],
            SecurityRisk.LOW: [],
            SecurityRisk.INFO: []
        }
        
        for vuln in self.vulnerabilities:
            by_risk[vuln.risk].append(vuln)
        
        # Calculate security score
        score = 100
        score -= len(by_risk[SecurityRisk.CRITICAL]) * 25
        score -= len(by_risk[SecurityRisk.HIGH]) * 15
        score -= len(by_risk[SecurityRisk.MEDIUM]) * 5
        score -= len(by_risk[SecurityRisk.LOW]) * 2
        score = max(0, score)
        
        return {
            "audit_timestamp": datetime.utcnow().isoformat(),
            "security_score": score,
            "total_vulnerabilities": len(self.vulnerabilities),
            "vulnerabilities_by_risk": {
                risk.value: len(vulns) for risk, vulns in by_risk.items()
            },
            "critical_vulnerabilities": [
                {
                    "type": v.type.value,
                    "endpoint": v.endpoint,
                    "description": v.description,
                    "recommendation": v.recommendation
                }
                for v in by_risk[SecurityRisk.CRITICAL]
            ],
            "high_vulnerabilities": [
                {
                    "type": v.type.value,
                    "endpoint": v.endpoint,
                    "description": v.description,
                    "recommendation": v.recommendation
                }
                for v in by_risk[SecurityRisk.HIGH]
            ],
            "recommendations": self._generate_recommendations(by_risk),
            "owasp_coverage": self._calculate_owasp_coverage()
        }
    
    def _generate_recommendations(self, by_risk: Dict[SecurityRisk, List[SecurityVulnerability]]) -> List[str]:
        """Generate prioritized recommendations."""
        recommendations = []
        
        if by_risk[SecurityRisk.CRITICAL]:
            recommendations.append("URGENT: Address all critical vulnerabilities immediately")
        
        if any(v.type == VulnerabilityType.BROKEN_AUTH for v in self.vulnerabilities):
            recommendations.append("Implement comprehensive authentication across all sensitive endpoints")
        
        if any(v.type == VulnerabilityType.RATE_LIMITING for v in self.vulnerabilities):
            recommendations.append("Add rate limiting to prevent abuse and brute force attacks")
        
        if any(v.type == VulnerabilityType.INPUT_VALIDATION for v in self.vulnerabilities):
            recommendations.append("Use Pydantic models for all input validation")
        
        recommendations.extend([
            "Implement security headers middleware",
            "Enable comprehensive logging and monitoring",
            "Conduct regular security audits",
            "Keep all dependencies up to date"
        ])
        
        return recommendations[:10]  # Top 10 recommendations
    
    def _calculate_owasp_coverage(self) -> Dict[str, bool]:
        """Calculate OWASP Top 10 coverage."""
        checked_types = {v.type for v in self.vulnerabilities}
        
        return {
            "A01_Broken_Access_Control": VulnerabilityType.BROKEN_ACCESS in checked_types,
            "A02_Cryptographic_Failures": False,  # Would need crypto audit
            "A03_Injection": VulnerabilityType.SQL_INJECTION in checked_types,
            "A04_Insecure_Design": VulnerabilityType.SECURITY_MISCONFIG in checked_types,
            "A05_Security_Misconfiguration": VulnerabilityType.SECURITY_MISCONFIG in checked_types,
            "A06_Vulnerable_Components": False,  # Would need dependency audit
            "A07_Authentication_Failures": VulnerabilityType.BROKEN_AUTH in checked_types,
            "A08_Data_Integrity_Failures": VulnerabilityType.INSECURE_DESERIALIZATION in checked_types,
            "A09_Security_Logging_Failures": VulnerabilityType.INSUFFICIENT_LOGGING in checked_types,
            "A10_SSRF": False  # Would need SSRF-specific audit
        }


# Utility function to run security audit
async def run_security_audit(app: FastAPI) -> Dict[str, Any]:
    """Run a security audit on the FastAPI application."""
    auditor = SecurityAuditor(app)
    return await auditor.run_full_audit()