"""
Contract tests for API endpoints using Pact
"""
import pytest
from datetime import datetime
from typing import Dict, Any, List
import json
from pathlib import Path

from pydantic import BaseModel, ValidationError
from fastapi import status

# Import API schemas
from api.v1.schemas.user import UserResponse, UserCreate, UserUpdate
from api.v1.schemas.auth import Token, TokenRefresh
from api.v1.schemas.content import ContentResponse, ContentCreate
from api.v1.schemas.analytics import AnalyticsEvent, MetricsResponse


class ContractValidator:
    """Validate API contracts against schemas"""
    
    def __init__(self):
        self.contracts: Dict[str, Dict[str, Any]] = {}
        self.violations: List[Dict[str, Any]] = []
    
    def add_contract(self, endpoint: str, method: str, contract: Dict[str, Any]):
        """Add a contract for an endpoint"""
        key = f"{method} {endpoint}"
        self.contracts[key] = contract
    
    def validate_request(self, endpoint: str, method: str, request_data: Any) -> bool:
        """Validate request against contract"""
        key = f"{method} {endpoint}"
        contract = self.contracts.get(key)
        
        if not contract:
            return True  # No contract defined
        
        request_schema = contract.get("request_schema")
        if request_schema:
            try:
                request_schema(**request_data)
                return True
            except ValidationError as e:
                self.violations.append({
                    "endpoint": endpoint,
                    "method": method,
                    "type": "request",
                    "error": str(e)
                })
                return False
        
        return True
    
    def validate_response(self, endpoint: str, method: str, status_code: int, response_data: Any) -> bool:
        """Validate response against contract"""
        key = f"{method} {endpoint}"
        contract = self.contracts.get(key)
        
        if not contract:
            return True
        
        # Check status code
        expected_status = contract.get("status_code")
        if expected_status and status_code != expected_status:
            self.violations.append({
                "endpoint": endpoint,
                "method": method,
                "type": "status_code",
                "expected": expected_status,
                "actual": status_code
            })
            return False
        
        # Check response schema
        response_schema = contract.get("response_schema")
        if response_schema and status_code == 200:
            try:
                if isinstance(response_data, list):
                    for item in response_data:
                        response_schema(**item)
                else:
                    response_schema(**response_data)
                return True
            except ValidationError as e:
                self.violations.append({
                    "endpoint": endpoint,
                    "method": method,
                    "type": "response",
                    "error": str(e)
                })
                return False
        
        return True


class TestAuthContracts:
    """Contract tests for authentication endpoints"""
    
    @pytest.mark.contract
    async def test_login_contract(self, async_client, contract_validator):
        """Test login endpoint contract"""
        # Define contract
        contract_validator.add_contract(
            "/api/v1/auth/login",
            "POST",
            {
                "request_schema": None,  # Uses OAuth2PasswordRequestForm
                "response_schema": Token,
                "status_code": status.HTTP_200_OK
            }
        )
        
        # Test valid request
        login_data = {
            "username": "testuser",
            "password": "testpassword",
            "grant_type": "password"
        }
        
        response = await async_client.post(
            "/api/v1/auth/login",
            data=login_data,  # Form data, not JSON
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Validate contract
        assert contract_validator.validate_response(
            "/api/v1/auth/login",
            "POST",
            response.status_code,
            response.json()
        )
    
    @pytest.mark.contract
    async def test_register_contract(self, async_client, contract_validator):
        """Test registration endpoint contract"""
        contract_validator.add_contract(
            "/api/v1/auth/register",
            "POST",
            {
                "request_schema": UserCreate,
                "response_schema": UserResponse,
                "status_code": status.HTTP_201_CREATED
            }
        )
        
        register_data = {
            "email": "contract@example.com",
            "username": "contractuser",
            "password": "SecurePass123!",
            "full_name": "Contract User"
        }
        
        # Validate request
        assert contract_validator.validate_request(
            "/api/v1/auth/register",
            "POST",
            register_data
        )
        
        response = await async_client.post(
            "/api/v1/auth/register",
            json=register_data
        )
        
        # Validate response
        assert contract_validator.validate_response(
            "/api/v1/auth/register",
            "POST",
            response.status_code,
            response.json()
        )


class TestUserContracts:
    """Contract tests for user endpoints"""
    
    @pytest.mark.contract
    async def test_get_user_contract(self, async_client, auth_headers, contract_validator):
        """Test get user endpoint contract"""
        contract_validator.add_contract(
            "/api/v1/users/me",
            "GET",
            {
                "response_schema": UserResponse,
                "status_code": status.HTTP_200_OK
            }
        )
        
        response = await async_client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )
        
        assert contract_validator.validate_response(
            "/api/v1/users/me",
            "GET",
            response.status_code,
            response.json()
        )
    
    @pytest.mark.contract
    async def test_update_user_contract(self, async_client, auth_headers, contract_validator):
        """Test update user endpoint contract"""
        contract_validator.add_contract(
            "/api/v1/users/me",
            "PUT",
            {
                "request_schema": UserUpdate,
                "response_schema": UserResponse,
                "status_code": status.HTTP_200_OK
            }
        )
        
        update_data = {
            "full_name": "Updated Name",
            "bio": "Updated bio"
        }
        
        assert contract_validator.validate_request(
            "/api/v1/users/me",
            "PUT",
            update_data
        )
        
        response = await async_client.put(
            "/api/v1/users/me",
            json=update_data,
            headers=auth_headers
        )
        
        assert contract_validator.validate_response(
            "/api/v1/users/me",
            "PUT",
            response.status_code,
            response.json()
        )


class TestContentContracts:
    """Contract tests for content endpoints"""
    
    @pytest.mark.contract
    async def test_create_content_contract(self, async_client, auth_headers, contract_validator):
        """Test create content endpoint contract"""
        contract_validator.add_contract(
            "/api/v1/content",
            "POST",
            {
                "request_schema": ContentCreate,
                "response_schema": ContentResponse,
                "status_code": status.HTTP_201_CREATED
            }
        )
        
        content_data = {
            "title": "Contract Test Content",
            "body": "This is test content",
            "status": "draft",
            "tags": ["test"]
        }
        
        assert contract_validator.validate_request(
            "/api/v1/content",
            "POST",
            content_data
        )
        
        response = await async_client.post(
            "/api/v1/content",
            json=content_data,
            headers=auth_headers
        )
        
        assert contract_validator.validate_response(
            "/api/v1/content",
            "POST",
            response.status_code,
            response.json()
        )


class TestAnalyticsContracts:
    """Contract tests for analytics endpoints"""
    
    @pytest.mark.contract
    async def test_analytics_event_contract(self, async_client, auth_headers, contract_validator):
        """Test analytics event endpoint contract"""
        contract_validator.add_contract(
            "/api/v1/analytics/events",
            "POST",
            {
                "request_schema": AnalyticsEvent,
                "status_code": status.HTTP_201_CREATED
            }
        )
        
        event_data = {
            "event_type": "page_view",
            "properties": {
                "page": "/home",
                "referrer": "https://google.com"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        assert contract_validator.validate_request(
            "/api/v1/analytics/events",
            "POST",
            event_data
        )
        
        response = await async_client.post(
            "/api/v1/analytics/events",
            json=event_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_201_CREATED


class ContractTestRunner:
    """Run contract tests and generate reports"""
    
    def __init__(self, output_dir: Path = Path("contract_tests")):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.results: List[Dict[str, Any]] = []
    
    def add_result(self, endpoint: str, method: str, passed: bool, details: Dict[str, Any] = None):
        """Add test result"""
        self.results.append({
            "endpoint": endpoint,
            "method": method,
            "passed": passed,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        })
    
    def generate_report(self):
        """Generate contract test report"""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_tests": len(self.results),
            "passed": sum(1 for r in self.results if r["passed"]),
            "failed": sum(1 for r in self.results if not r["passed"]),
            "results": self.results
        }
        
        # Save JSON report
        with open(self.output_dir / "contract_test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        # Generate markdown report
        self.generate_markdown_report(report)
        
        return report
    
    def generate_markdown_report(self, report: Dict[str, Any]):
        """Generate markdown report"""
        content = f"""# Contract Test Report

Generated: {report['timestamp']}

## Summary

- **Total Tests**: {report['total_tests']}
- **Passed**: {report['passed']} ✅
- **Failed**: {report['failed']} ❌
- **Success Rate**: {(report['passed'] / report['total_tests'] * 100):.1f}%

## Results

| Endpoint | Method | Status | Details |
|----------|--------|--------|---------|
"""
        
        for result in report["results"]:
            status = "✅ Pass" if result["passed"] else "❌ Fail"
            details = result["details"].get("error", "-") if result["details"] else "-"
            content += f"| {result['endpoint']} | {result['method']} | {status} | {details} |\n"
        
        with open(self.output_dir / "contract_test_report.md", "w") as f:
            f.write(content)


# Fixtures for contract testing
@pytest.fixture
def contract_validator():
    """Create contract validator instance"""
    return ContractValidator()


@pytest.fixture
def contract_runner():
    """Create contract test runner"""
    return ContractTestRunner()


# Generate OpenAPI contract tests
def generate_openapi_contract_tests(openapi_spec: Dict[str, Any], output_file: str = "test_openapi_contracts.py"):
    """Generate contract tests from OpenAPI specification"""
    test_content = '''"""
Auto-generated contract tests from OpenAPI specification
"""
import pytest
from typing import Dict, Any

'''
    
    # Generate test for each endpoint
    for path, methods in openapi_spec.get("paths", {}).items():
        for method, operation in methods.items():
            if method in ["get", "post", "put", "delete", "patch"]:
                test_name = f"test_{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}_contract"
                
                test_content += f'''
@pytest.mark.contract
async def {test_name}(async_client, auth_headers, contract_validator):
    """Test {method.upper()} {path} contract"""
    # Test implementation based on OpenAPI spec
    pass
'''
    
    with open(output_file, "w") as f:
        f.write(test_content)


# Pact-style consumer contract
class ConsumerContract:
    """Define consumer contract for external services"""
    
    def __init__(self, consumer: str, provider: str):
        self.consumer = consumer
        self.provider = provider
        self.interactions: List[Dict[str, Any]] = []
    
    def add_interaction(self, description: str, request: Dict[str, Any], response: Dict[str, Any]):
        """Add interaction to contract"""
        self.interactions.append({
            "description": description,
            "request": request,
            "response": response
        })
    
    def to_pact(self) -> Dict[str, Any]:
        """Convert to Pact format"""
        return {
            "consumer": {"name": self.consumer},
            "provider": {"name": self.provider},
            "interactions": self.interactions,
            "metadata": {
                "pactSpecification": {"version": "2.0.0"}
            }
        }
    
    def save(self, filename: str):
        """Save contract to file"""
        with open(filename, "w") as f:
            json.dump(self.to_pact(), f, indent=2)