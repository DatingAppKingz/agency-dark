"""
OAuth-specific Locust load testing configuration.
Run with: locust -f oauth_locustfile.py --host=http://localhost:8000
"""
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner
import random
import json
import time
from uuid import uuid4
from datetime import datetime, timezone
import logging
import base64
import hashlib
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OAuthUser(HttpUser):
    """OAuth user simulation for load testing."""
    
    wait_time = between(0.5, 2)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_tokens = []
        self.refresh_tokens = []
        self.client_id = None
        self.user_id = None
        self.code_verifier = None
        self.code_challenge = None
    
    def on_start(self):
        """Initialize user session."""
        self.client_id = f"load_test_client_{uuid4()}"
        self.user_id = f"user_{uuid4()}"
        self.agency_id = random.choice(["agency_1", "agency_2", "agency_3"])
        
        # Generate PKCE challenge
        self.generate_pkce()
        
        # Get initial token
        self.get_client_credentials_token()
    
    def on_stop(self):
        """Clean up user session."""
        # Revoke all tokens
        for token in self.access_tokens:
            self.revoke_token(token)
    
    def generate_pkce(self):
        """Generate PKCE challenge and verifier."""
        self.code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode('utf-8').rstrip('=')
        
        challenge = hashlib.sha256(self.code_verifier.encode()).digest()
        self.code_challenge = base64.urlsafe_b64encode(
            challenge
        ).decode('utf-8').rstrip('=')
    
    @task(10)
    def authorization_flow(self):
        """Simulate complete authorization flow with PKCE."""
        # Step 1: Authorization request
        auth_params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read write",
            "state": str(uuid4()),
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
        }
        
        with self.client.get(
            "/oauth/authorize",
            params=auth_params,
            name="/oauth/authorize",
            catch_response=True
        ) as response:
            if response.status_code in [200, 302]:
                response.success()
                
                # Step 2: Simulate user consent
                time.sleep(random.uniform(0.5, 1.5))  # User decision time
                
                # Step 3: Token exchange with PKCE
                self.exchange_code_for_token()
            else:
                response.failure(f"Auth failed: {response.status_code}")
    
    @task(5)
    def get_client_credentials_token(self):
        """Get token using client credentials grant."""
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": "test_secret",
            "scope": "read",
        }
        
        with self.client.post(
            "/oauth/token",
            json=data,
            name="/oauth/token [client_credentials]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    token_data = response.json()
                    self.access_tokens.append(token_data.get("access_token"))
                    response.success()
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 400:
                # Expected for invalid client
                response.success()
            else:
                response.failure(f"Token request failed: {response.status_code}")
    
    @task(8)
    def exchange_code_for_token(self):
        """Exchange authorization code for token with PKCE."""
        data = {
            "grant_type": "authorization_code",
            "code": str(uuid4()),  # Simulated code
            "client_id": self.client_id,
            "client_secret": "test_secret",
            "redirect_uri": "http://localhost:3000/callback",
            "code_verifier": self.code_verifier,
        }
        
        with self.client.post(
            "/oauth/token",
            json=data,
            name="/oauth/token [authorization_code]",
            catch_response=True
        ) as response:
            if response.status_code in [200, 400]:  # 400 for invalid code is expected
                if response.status_code == 200:
                    try:
                        token_data = response.json()
                        self.access_tokens.append(token_data.get("access_token"))
                        if token_data.get("refresh_token"):
                            self.refresh_tokens.append(token_data.get("refresh_token"))
                    except json.JSONDecodeError:
                        pass
                response.success()
                # Generate new PKCE for next request
                self.generate_pkce()
            else:
                response.failure(f"Code exchange failed: {response.status_code}")
    
    @task(6)
    def refresh_access_token(self):
        """Refresh an access token."""
        if not self.refresh_tokens:
            return
        
        refresh_token = random.choice(self.refresh_tokens)
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": "test_secret",
        }
        
        with self.client.post(
            "/oauth/token",
            json=data,
            name="/oauth/token [refresh_token]",
            catch_response=True
        ) as response:
            if response.status_code in [200, 400]:
                if response.status_code == 200:
                    try:
                        token_data = response.json()
                        self.access_tokens.append(token_data.get("access_token"))
                    except json.JSONDecodeError:
                        pass
                response.success()
            else:
                response.failure(f"Refresh failed: {response.status_code}")
    
    @task(10)
    def introspect_token(self):
        """Introspect a token."""
        if not self.access_tokens:
            return
        
        token = random.choice(self.access_tokens)
        
        data = {
            "token": token,
            "token_type_hint": "access_token",
        }
        
        # Basic auth for client credentials
        credentials = base64.b64encode(
            f"{self.client_id}:test_secret".encode()
        ).decode()
        
        headers = {
            "Authorization": f"Basic {credentials}",
        }
        
        with self.client.post(
            "/oauth/introspect",
            json=data,
            headers=headers,
            name="/oauth/introspect",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Introspection failed: {response.status_code}")
    
    @task(2)
    def revoke_token(self, token: str = None):
        """Revoke a token."""
        if not token and not self.access_tokens:
            return
        
        token = token or self.access_tokens.pop() if self.access_tokens else str(uuid4())
        
        data = {
            "token": token,
            "token_type_hint": "access_token",
        }
        
        with self.client.post(
            "/oauth/revoke",
            json=data,
            name="/oauth/revoke",
            catch_response=True
        ) as response:
            if response.status_code in [200, 400]:
                response.success()
            else:
                response.failure(f"Revocation failed: {response.status_code}")
    
    @task(15)
    def use_access_token(self):
        """Use access token to access protected resource."""
        if not self.access_tokens:
            self.get_client_credentials_token()
            return
        
        token = random.choice(self.access_tokens)
        
        headers = {
            "Authorization": f"Bearer {token}",
        }
        
        # Simulate different API endpoints
        endpoints = [
            "/api/v1/me",
            "/api/v1/users",
            "/api/v1/models",
            "/api/v1/chat/messages",
        ]
        
        endpoint = random.choice(endpoints)
        
        with self.client.get(
            endpoint,
            headers=headers,
            name=f"Protected: {endpoint}",
            catch_response=True
        ) as response:
            if response.status_code in [200, 401, 403, 404]:
                response.success()
            else:
                response.failure(f"API call failed: {response.status_code}")
    
    @task(3)
    def provider_callback(self):
        """Simulate OAuth provider callback."""
        providers = ["google", "instagram", "microsoft"]
        provider = random.choice(providers)
        
        callback_params = {
            "code": str(uuid4()),
            "state": str(uuid4()),
        }
        
        with self.client.get(
            f"/oauth/callback/{provider}",
            params=callback_params,
            name=f"/oauth/callback/{provider}",
            catch_response=True
        ) as response:
            if response.status_code in [200, 302, 400]:
                response.success()
            else:
                response.failure(f"Callback failed: {response.status_code}")


class HighLoadOAuthUser(OAuthUser):
    """High-frequency OAuth user for stress testing."""
    
    wait_time = between(0.1, 0.5)  # Much shorter wait times
    
    @task(20)
    def rapid_token_generation(self):
        """Generate tokens rapidly."""
        for _ in range(5):
            self.get_client_credentials_token()
    
    @task(15)
    def rapid_introspection(self):
        """Introspect tokens rapidly."""
        for _ in range(10):
            if self.access_tokens:
                self.introspect_token()
    
    @task(10)
    def concurrent_refreshes(self):
        """Refresh multiple tokens concurrently."""
        if len(self.refresh_tokens) > 3:
            for _ in range(3):
                self.refresh_access_token()


class MultiTenantOAuthUser(OAuthUser):
    """Multi-tenant OAuth user for testing agency isolation."""
    
    def on_start(self):
        """Initialize with specific agency context."""
        super().on_start()
        self.agencies = ["agency_1", "agency_2", "agency_3", "agency_4", "agency_5"]
        self.current_agency = random.choice(self.agencies)
    
    @task(5)
    def switch_agency_context(self):
        """Switch between different agencies."""
        self.current_agency = random.choice(self.agencies)
        
        # Get new token for different agency
        data = {
            "grant_type": "client_credentials",
            "client_id": f"{self.current_agency}_{self.client_id}",
            "client_secret": "test_secret",
            "scope": "read write",
        }
        
        headers = {
            "X-Agency-ID": self.current_agency,
            "Host": f"{self.current_agency}.agencydark.com",
        }
        
        with self.client.post(
            "/oauth/token",
            json=data,
            headers=headers,
            name="/oauth/token [multi-tenant]",
            catch_response=True
        ) as response:
            if response.status_code in [200, 400]:
                response.success()
            else:
                response.failure(f"Multi-tenant token failed: {response.status_code}")
    
    @task(8)
    def cross_agency_access_attempt(self):
        """Attempt cross-agency access (should fail)."""
        if not self.access_tokens:
            return
        
        # Try to use token from one agency in another agency's context
        different_agency = random.choice(
            [a for a in self.agencies if a != self.current_agency]
        )
        
        token = random.choice(self.access_tokens)
        
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Agency-ID": different_agency,
        }
        
        with self.client.get(
            "/api/v1/agency/data",
            headers=headers,
            name="/api/v1/agency/data [cross-agency]",
            catch_response=True
        ) as response:
            if response.status_code in [401, 403]:
                # Expected to fail
                response.success()
            elif response.status_code == 200:
                response.failure("Cross-agency access should be denied!")
            else:
                response.failure(f"Unexpected status: {response.status_code}")


# Event handlers for statistics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Handle test start."""
    logger.info("=" * 60)
    logger.info("OAuth Load Test Starting")
    logger.info("=" * 60)
    logger.info(f"Target Host: {environment.host}")
    logger.info(f"Number of Users: {environment.parsed_options.num_users}")
    logger.info(f"Spawn Rate: {environment.parsed_options.spawn_rate}")
    if hasattr(environment.parsed_options, 'run_time'):
        logger.info(f"Run Time: {environment.parsed_options.run_time}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Handle test stop."""
    logger.info("\n" + "=" * 60)
    logger.info("OAuth Load Test Results")
    logger.info("=" * 60)
    
    # Overall statistics
    stats = environment.stats
    logger.info(f"Total Requests: {stats.total.num_requests}")
    logger.info(f"Total Failures: {stats.total.num_failures}")
    logger.info(f"Failure Rate: {stats.total.fail_ratio:.2%}")
    logger.info(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"Min Response Time: {stats.total.min_response_time:.2f}ms")
    logger.info(f"Max Response Time: {stats.total.max_response_time:.2f}ms")
    logger.info(f"Median Response Time: {stats.total.median_response_time:.2f}ms")
    logger.info(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    logger.info(f"99th Percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")
    logger.info(f"RPS: {stats.total.current_rps:.2f}")
    
    # Per-endpoint statistics
    logger.info("\nPer-Endpoint Statistics:")
    logger.info("-" * 40)
    
    for entry in stats.entries.values():
        if entry.num_requests > 0:
            logger.info(f"\n{entry.name}:")
            logger.info(f"  Requests: {entry.num_requests}")
            logger.info(f"  Failures: {entry.num_failures}")
            logger.info(f"  Avg Response: {entry.avg_response_time:.2f}ms")
            logger.info(f"  95th Percentile: {entry.get_response_time_percentile(0.95):.2f}ms")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track individual requests for detailed analysis."""
    if exception:
        logger.debug(f"Request failed: {name} - {exception}")
    
    # Track slow requests
    if response_time > 1000:  # Log requests slower than 1 second
        logger.warning(f"Slow request: {name} took {response_time}ms")


@events.init_command_line_parser.add_listener
def init_parser(parser, **kwargs):
    """Add custom command line arguments."""
    parser.add_argument(
        "--test-type",
        type=str,
        default="standard",
        choices=["standard", "high-load", "multi-tenant"],
        help="Type of load test to run"
    )


@events.init.add_listener
def on_init(environment, **kwargs):
    """Initialize test based on command line arguments."""
    if hasattr(environment.parsed_options, 'test_type'):
        test_type = environment.parsed_options.test_type
        
        if test_type == "high-load":
            logger.info("Running HIGH LOAD stress test")
            environment.user_classes = [HighLoadOAuthUser]
        elif test_type == "multi-tenant":
            logger.info("Running MULTI-TENANT load test")
            environment.user_classes = [MultiTenantOAuthUser]
        else:
            logger.info("Running STANDARD load test")
            environment.user_classes = [OAuthUser]


# Custom failure conditions
@events.quitting.add_listener
def check_failure_conditions(environment, **kwargs):
    """Check for test failure conditions."""
    stats = environment.stats
    
    # Define failure thresholds
    max_failure_rate = 0.05  # 5%
    max_p95_response = 1000  # 1 second
    min_rps = 10  # Minimum requests per second
    
    failures = []
    
    if stats.total.fail_ratio > max_failure_rate:
        failures.append(f"Failure rate {stats.total.fail_ratio:.2%} exceeds {max_failure_rate:.0%}")
    
    p95 = stats.total.get_response_time_percentile(0.95)
    if p95 and p95 > max_p95_response:
        failures.append(f"95th percentile {p95:.0f}ms exceeds {max_p95_response}ms")
    
    if stats.total.current_rps < min_rps and stats.total.num_requests > 100:
        failures.append(f"RPS {stats.total.current_rps:.2f} below minimum {min_rps}")
    
    if failures:
        logger.error("\n" + "!" * 60)
        logger.error("LOAD TEST FAILED - Thresholds Exceeded:")
        for failure in failures:
            logger.error(f"  - {failure}")
        logger.error("!" * 60)
        environment.process_exit_code = 1
    else:
        logger.info("\n" + "✓" * 60)
        logger.info("LOAD TEST PASSED - All thresholds met")
        logger.info("✓" * 60)