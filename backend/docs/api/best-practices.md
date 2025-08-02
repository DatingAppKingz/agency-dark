
# API Best Practices

## Request Optimization

### 1. Use Field Selection

Request only the fields you need:

```bash
# Good - specific fields
GET /api/v1/users/123?fields=id,name,email

# Bad - all fields
GET /api/v1/users/123
```

### 2. Pagination

Always paginate list requests:

```python
# Good - paginated request
page = 1
while True:
    response = requests.get(
        f"/api/v1/content?page={page}&limit=100"
    )
    data = response.json()
    process_items(data["items"])
    
    if page >= data["pages"]:
        break
    page += 1
```

### 3. Batch Operations

Use batch endpoints when available:

```python
# Good - single batch request
requests.post("/api/v1/users/batch", json={
    "operations": [
        {"method": "POST", "data": {"name": "User 1"}},
        {"method": "POST", "data": {"name": "User 2"}},
        {"method": "POST", "data": {"name": "User 3"}}
    ]
})

# Bad - multiple individual requests
for user in users:
    requests.post("/api/v1/users", json=user)
```

## Error Handling

### 1. Implement Retry Logic

```python
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Configure retry strategy
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)

# Apply to session
session = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
```

### 2. Handle Rate Limits

```python
def make_request_with_rate_limit(url, headers):
    response = requests.get(url, headers=headers)
    
    if response.status_code == 429:
        # Get retry after header
        retry_after = int(response.headers.get("Retry-After", 60))
        time.sleep(retry_after)
        return make_request_with_rate_limit(url, headers)
    
    return response
```

### 3. Graceful Degradation

```python
def get_user_with_fallback(user_id):
    try:
        # Try to get fresh data
        return api_client.get(f"/users/{user_id}")
    except APIError:
        # Fall back to cache
        return cache.get(f"user:{user_id}")
```

## Performance Optimization

### 1. Connection Pooling

```python
# Reuse connections
session = requests.Session()
session.headers.update({"Authorization": f"Bearer {token}"})

# Make multiple requests with same session
for endpoint in endpoints:
    response = session.get(endpoint)
```

### 2. Async Requests

```python
import asyncio
import aiohttp

async def fetch_multiple(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_one(session, url) for url in urls]
        return await asyncio.gather(*tasks)

async def fetch_one(session, url):
    async with session.get(url) as response:
        return await response.json()
```

### 3. Caching

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def get_cached_response(endpoint, params_hash):
    return requests.get(endpoint, params=params).json()

# Use cache
params = {"filter": "active", "sort": "created_at"}
params_hash = hashlib.md5(
    json.dumps(params, sort_keys=True).encode()
).hexdigest()
data = get_cached_response("/api/v1/users", params_hash)
```

## Security Best Practices

### 1. Input Validation

```python
# Validate all inputs
def create_user(data):
    # Sanitize inputs
    data["email"] = data["email"].lower().strip()
    data["name"] = bleach.clean(data["name"])
    
    # Validate format
    if not re.match(r"[^@]+@[^@]+\.[^@]+", data["email"]):
        raise ValueError("Invalid email format")
    
    return api_client.post("/users", json=data)
```

### 2. Secure Token Handling

```python
import os
from cryptography.fernet import Fernet

# Encrypt tokens at rest
key = os.environ["ENCRYPTION_KEY"].encode()
cipher = Fernet(key)

def store_token(token):
    encrypted = cipher.encrypt(token.encode())
    save_to_secure_storage(encrypted)

def retrieve_token():
    encrypted = load_from_secure_storage()
    return cipher.decrypt(encrypted).decode()
```

### 3. Request Signing

```python
import hmac
import hashlib

def sign_request(method, path, body, secret):
    # Create signature
    message = f"{method}\n{path}\n{body}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return signature

# Use signature
signature = sign_request("POST", "/api/v1/transfer", body, secret)
headers["X-Signature"] = signature
```

## Monitoring and Logging

### 1. Request Tracking

```python
import uuid
import logging

def make_tracked_request(endpoint, **kwargs):
    request_id = str(uuid.uuid4())
    
    # Add tracking header
    headers = kwargs.get("headers", {})
    headers["X-Request-ID"] = request_id
    kwargs["headers"] = headers
    
    # Log request
    logging.info(f"API Request: {request_id} - {endpoint}")
    
    try:
        response = requests.get(endpoint, **kwargs)
        logging.info(f"API Response: {request_id} - {response.status_code}")
        return response
    except Exception as e:
        logging.error(f"API Error: {request_id} - {str(e)}")
        raise
```

### 2. Performance Monitoring

```python
import time
from contextlib import contextmanager

@contextmanager
def monitor_api_call(operation):
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        metrics.record("api.call.duration", duration, tags={
            "operation": operation
        })
```

### 3. Error Tracking

```python
def track_api_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            # Track error metrics
            metrics.increment("api.errors", tags={
                "status_code": e.status_code,
                "error_code": e.error_code,
                "endpoint": e.endpoint
            })
            
            # Send to error tracking service
            sentry.capture_exception(e)
            raise
    return wrapper
```

## Testing

### 1. Mock API Responses

```python
from unittest.mock import patch

@patch('requests.get')
def test_get_user(mock_get):
    # Mock response
    mock_get.return_value.json.return_value = {
        "id": 1,
        "name": "Test User"
    }
    
    # Test code
    user = get_user(1)
    assert user["name"] == "Test User"
```

### 2. Integration Testing

```python
import pytest

@pytest.mark.integration
def test_user_workflow():
    # Create user
    user = api_client.create_user({
        "name": "Test User",
        "email": "test@example.com"
    })
    
    # Update user
    updated = api_client.update_user(user["id"], {
        "name": "Updated Name"
    })
    
    # Verify update
    assert updated["name"] == "Updated Name"
    
    # Cleanup
    api_client.delete_user(user["id"])
```

### 3. Load Testing

```python
import concurrent.futures
import statistics

def load_test_endpoint(endpoint, concurrent_requests=10):
    def make_request():
        start = time.time()
        response = requests.get(endpoint)
        return time.time() - start
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        response_times = list(executor.map(
            lambda _: make_request(),
            range(concurrent_requests)
        ))
    
    print(f"Average response time: {statistics.mean(response_times):.2f}s")
    print(f"95th percentile: {statistics.quantiles(response_times, n=20)[18]:.2f}s")
```

## Versioning Strategy

### 1. Version Headers

```python
# Specify version in header
headers = {
    "API-Version": "v2",
    "Accept": "application/vnd.agency.v2+json"
}
```

### 2. Graceful Migration

```python
def get_user_compatible(user_id, version="v1"):
    if version == "v1":
        # Old format
        user = api_client.get(f"/api/v1/users/{user_id}")
        return {
            "id": user["id"],
            "name": user["full_name"]  # v1 field name
        }
    else:
        # New format
        user = api_client.get(f"/api/v2/users/{user_id}")
        return {
            "id": user["id"],
            "name": f"{user['first_name']} {user['last_name']}"  # v2 fields
        }
```

## Additional Resources

- [RESTful API Design](https://restfulapi.net/)
- [API Design Patterns](https://www.oreilly.com/library/view/api-design-patterns/9781617295850/)
- [The Web API Checklist](https://mathieu.fenniak.net/the-api-checklist/)
