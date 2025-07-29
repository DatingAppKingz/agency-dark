"""
Load testing scenarios using Locust
"""
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser
import random
import json
import time
from datetime import datetime, timedelta
import uuid


class AgencyAPIUser(FastHttpUser):
    """Base user class for Agency API load testing"""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Called when a user starts"""
        # Login and get token
        response = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": "loadtest",
                "password": "loadtest123",
                "grant_type": "password"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}
            print(f"Failed to authenticate: {response.status_code}")
    
    def on_stop(self):
        """Called when a user stops"""
        if self.token:
            self.client.post("/api/v1/auth/logout", headers=self.headers)


class StandardUser(AgencyAPIUser):
    """Standard user behavior - reads more than writes"""
    
    @task(10)
    def view_dashboard(self):
        """View dashboard (most common action)"""
        self.client.get("/api/v1/dashboard", headers=self.headers)
    
    @task(8)
    def list_content(self):
        """Browse content list"""
        page = random.randint(1, 10)
        self.client.get(
            f"/api/v1/content?page={page}&limit=20",
            headers=self.headers,
            name="/api/v1/content?page=[page]&limit=20"
        )
    
    @task(5)
    def view_content_details(self):
        """View specific content"""
        content_id = random.choice(self.content_ids) if hasattr(self, 'content_ids') else uuid.uuid4()
        self.client.get(
            f"/api/v1/content/{content_id}",
            headers=self.headers,
            name="/api/v1/content/[id]"
        )
    
    @task(3)
    def check_analytics(self):
        """Check analytics data"""
        self.client.get(
            "/api/v1/analytics/overview?period=7d",
            headers=self.headers
        )
    
    @task(2)
    def search_content(self):
        """Search for content"""
        query = random.choice(["test", "demo", "example", "guide"])
        self.client.get(
            f"/api/v1/content/search?q={query}",
            headers=self.headers,
            name="/api/v1/content/search?q=[query]"
        )
    
    @task(1)
    def create_content(self):
        """Create new content (less frequent)"""
        content_data = {
            "title": f"Load Test Content {uuid.uuid4()}",
            "body": "This is content created during load testing",
            "status": "draft",
            "tags": ["loadtest"]
        }
        
        response = self.client.post(
            "/api/v1/content",
            json=content_data,
            headers=self.headers
        )
        
        if response.status_code == 201:
            if not hasattr(self, 'content_ids'):
                self.content_ids = []
            self.content_ids.append(response.json()["id"])


class PowerUser(AgencyAPIUser):
    """Power user - performs more complex operations"""
    
    @task(8)
    def bulk_operations(self):
        """Perform bulk operations"""
        content_ids = [str(uuid.uuid4()) for _ in range(10)]
        
        self.client.post(
            "/api/v1/content/bulk",
            json={
                "operation": "update_status",
                "ids": content_ids,
                "data": {"status": "published"}
            },
            headers=self.headers
        )
    
    @task(6)
    def generate_report(self):
        """Generate analytics report"""
        report_params = {
            "type": "revenue",
            "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "format": "pdf"
        }
        
        self.client.post(
            "/api/v1/reports/generate",
            json=report_params,
            headers=self.headers
        )
    
    @task(5)
    def complex_analytics_query(self):
        """Complex analytics query"""
        self.client.get(
            "/api/v1/analytics/metrics?"
            "metrics=revenue,engagement,conversion&"
            "dimensions=channel,campaign&"
            "start_date=2024-01-01&"
            "end_date=2024-01-31&"
            "granularity=day",
            headers=self.headers,
            name="/api/v1/analytics/metrics?[complex]"
        )
    
    @task(4)
    def export_data(self):
        """Export large dataset"""
        self.client.get(
            "/api/v1/export/users?format=csv&limit=10000",
            headers=self.headers,
            name="/api/v1/export/[type]"
        )
    
    @task(3)
    def manage_webhooks(self):
        """Manage webhooks"""
        # List webhooks
        self.client.get("/api/v1/webhooks", headers=self.headers)
        
        # Create webhook
        webhook_data = {
            "url": f"https://example.com/webhook/{uuid.uuid4()}",
            "events": ["content.created", "content.updated"],
            "active": True
        }
        
        self.client.post(
            "/api/v1/webhooks",
            json=webhook_data,
            headers=self.headers
        )


class APIUser(AgencyAPIUser):
    """API user - makes API calls programmatically"""
    
    @task(10)
    def api_health_check(self):
        """Regular health checks"""
        self.client.get("/api/v1/health", name="/api/v1/health")
    
    @task(8)
    def batch_api_calls(self):
        """Batch API calls"""
        batch_requests = [
            {"method": "GET", "path": "/api/v1/users/me"},
            {"method": "GET", "path": "/api/v1/content?limit=10"},
            {"method": "GET", "path": "/api/v1/analytics/summary"}
        ]
        
        self.client.post(
            "/api/v1/batch",
            json={"requests": batch_requests},
            headers=self.headers
        )
    
    @task(5)
    def streaming_endpoint(self):
        """Test streaming endpoint"""
        with self.client.get(
            "/api/v1/analytics/stream",
            headers=self.headers,
            stream=True
        ) as response:
            for line in response.iter_lines():
                if line:
                    # Process streamed data
                    pass
    
    @task(3)
    def graphql_query(self):
        """GraphQL query"""
        query = """
        query {
            user(id: "me") {
                id
                username
                content(limit: 10) {
                    id
                    title
                    createdAt
                }
            }
        }
        """
        
        self.client.post(
            "/api/v1/graphql",
            json={"query": query},
            headers=self.headers
        )


class MobileUser(AgencyAPIUser):
    """Mobile app user - different usage patterns"""
    
    wait_time = between(2, 5)  # Mobile users interact less frequently
    
    def on_start(self):
        """Mobile-specific initialization"""
        super().on_start()
        self.device_id = str(uuid.uuid4())
        self.headers.update({
            "User-Agent": "AgencyApp/1.0 (iOS 17.0)",
            "X-Device-ID": self.device_id
        })
    
    @task(15)
    def sync_data(self):
        """Sync offline changes"""
        sync_data = {
            "device_id": self.device_id,
            "last_sync": (datetime.now() - timedelta(hours=1)).isoformat(),
            "changes": [
                {
                    "type": "content_view",
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat()
                }
            ]
        }
        
        self.client.post(
            "/api/v1/sync",
            json=sync_data,
            headers=self.headers
        )
    
    @task(10)
    def push_notification_register(self):
        """Register for push notifications"""
        self.client.post(
            "/api/v1/notifications/register",
            json={
                "device_id": self.device_id,
                "token": f"fake_push_token_{uuid.uuid4()}",
                "platform": "ios"
            },
            headers=self.headers
        )
    
    @task(8)
    def load_feed(self):
        """Load personalized feed"""
        self.client.get(
            "/api/v1/feed?limit=20",
            headers=self.headers
        )
    
    @task(5)
    def upload_media(self):
        """Upload media file"""
        # Simulate file upload
        files = {"file": ("image.jpg", b"fake_image_data", "image/jpeg")}
        
        self.client.post(
            "/api/v1/media/upload",
            files=files,
            headers={k: v for k, v in self.headers.items() if k != "Content-Type"}
        )


class WebSocketUser(HttpUser):
    """WebSocket connection testing"""
    
    wait_time = between(5, 10)
    
    @task
    def connect_websocket(self):
        """Test WebSocket connections"""
        # Note: Locust doesn't natively support WebSocket
        # This is a placeholder for WebSocket testing
        # Use specialized tools like Artillery.io for WebSocket load testing
        pass


# Custom event handlers
@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize load test"""
    print("Load test starting...")
    print(f"Target host: {environment.host}")
    print(f"Users: {environment.parsed_options.num_users}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("Creating test data...")
    
    # Create test users if needed
    # This would typically be done in a separate setup script
    

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("Cleaning up test data...")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Custom request logging"""
    if exception:
        print(f"Request failed: {name} - {exception}")
    elif response_time > 1000:  # Log slow requests (>1s)
        print(f"Slow request: {name} - {response_time}ms")


# Scenario definitions
class BlackFridayScenario(AgencyAPIUser):
    """Simulate Black Friday traffic spike"""
    
    wait_time = between(0.1, 0.5)  # Much faster interaction
    
    @task(20)
    def browse_deals(self):
        """Browse Black Friday deals"""
        self.client.get(
            "/api/v1/deals/black-friday",
            headers=self.headers
        )
    
    @task(15)
    def add_to_cart(self):
        """Add items to cart rapidly"""
        item_id = random.randint(1, 1000)
        self.client.post(
            "/api/v1/cart/add",
            json={"item_id": item_id, "quantity": 1},
            headers=self.headers
        )
    
    @task(10)
    def checkout(self):
        """Attempt checkout"""
        self.client.post(
            "/api/v1/checkout",
            json={"payment_method": "card"},
            headers=self.headers
        )


class StressTestUser(AgencyAPIUser):
    """User for stress testing - aggressive behavior"""
    
    wait_time = between(0, 0.1)  # Almost no wait
    
    @task
    def hammer_endpoint(self):
        """Repeatedly hit the same endpoint"""
        self.client.get(
            "/api/v1/health",
            headers=self.headers,
            name="/api/v1/health [stress]"
        )


# Composite scenarios
class MixedLoadScenario(HttpUser):
    """Mixed load scenario with different user types"""
    
    tasks = {
        StandardUser: 70,    # 70% standard users
        PowerUser: 20,       # 20% power users
        APIUser: 8,          # 8% API users
        MobileUser: 2        # 2% mobile users
    }


# Configuration for different test scenarios
"""
Usage examples:

# Basic load test (100 users over 5 minutes)
locust -f locustfile.py --host=https://api.agency.com --users=100 --spawn-rate=10 --run-time=5m

# Stress test (ramp up to 1000 users)
locust -f locustfile.py --host=https://api.agency.com --users=1000 --spawn-rate=50 --run-time=10m

# Spike test (sudden traffic increase)
locust -f locustfile.py --host=https://api.agency.com --users=500 --spawn-rate=500 --run-time=2m

# Soak test (sustained load)
locust -f locustfile.py --host=https://api.agency.com --users=200 --spawn-rate=5 --run-time=1h

# Distributed testing
locust -f locustfile.py --master --host=https://api.agency.com
locust -f locustfile.py --worker --master-host=localhost
"""