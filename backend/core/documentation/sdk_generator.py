"""
Client SDK generation for multiple programming languages
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import re
from datetime import datetime

from core.logging import logger


class SDKGenerator:
    """Generate client SDKs from OpenAPI specification"""
    
    def __init__(self, openapi_spec: Dict[str, Any], output_dir: Path = Path("sdks")):
        self.spec = openapi_spec
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_python_sdk(self) -> str:
        """Generate Python SDK"""
        sdk_dir = self.output_dir / "python"
        sdk_dir.mkdir(exist_ok=True)
        
        # Generate setup.py
        setup_content = f"""from setuptools import setup, find_packages

setup(
    name="agency-sdk",
    version="{self.spec['info']['version']}",
    description="{self.spec['info']['description'].split('.')[0]}",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Agency API Team",
    author_email="api@agency.com",
    url="https://github.com/agency/python-sdk",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "pydantic>=2.0.0",
        "python-dateutil>=2.8.0"
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
"""
        (sdk_dir / "setup.py").write_text(setup_content)
        
        # Generate SDK structure
        agency_dir = sdk_dir / "agency_sdk"
        agency_dir.mkdir(exist_ok=True)
        
        # Generate __init__.py
        init_content = '''"""
Agency API Python SDK

Example usage:
    from agency_sdk import Client
    
    client = Client(api_key="your-api-key")
    user = client.users.get_current()
"""
from .client import Client
from .exceptions import (
    AgencyError,
    AuthenticationError,
    RateLimitError,
    ValidationError
)
from .models import *

__version__ = "{version}"
__all__ = ["Client", "AgencyError", "AuthenticationError", "RateLimitError", "ValidationError"]
'''.format(version=self.spec['info']['version'])
        
        (agency_dir / "__init__.py").write_text(init_content)
        
        # Generate client.py
        client_content = '''"""
Agency API Client
"""
from typing import Optional, Dict, Any
import requests
from urllib.parse import urljoin

from .auth import Auth
from .users import Users
from .content import Content
from .analytics import Analytics
from .exceptions import handle_response_error


class Client:
    """Main Agency API client"""
    
    DEFAULT_BASE_URL = "https://api.agency.com"
    DEFAULT_TIMEOUT = 30
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        verify_ssl: bool = True
    ):
        """
        Initialize Agency API client
        
        Args:
            api_key: API key for authentication
            access_token: JWT access token
            base_url: Base URL for API (defaults to production)
            timeout: Request timeout in seconds
            verify_ssl: Verify SSL certificates
        """
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        # Setup session
        self.session = requests.Session()
        
        # Setup authentication
        if api_key:
            self.session.headers["X-API-Key"] = api_key
        elif access_token:
            self.session.headers["Authorization"] = f"Bearer {access_token}"
        
        # Setup default headers
        self.session.headers.update({
            "User-Agent": f"agency-python-sdk/{__version__}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        # Initialize resources
        self.auth = Auth(self)
        self.users = Users(self)
        self.content = Content(self)
        self.analytics = Analytics(self)
    
    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request to API
        
        Args:
            method: HTTP method
            path: API path
            params: Query parameters
            json: JSON body
            **kwargs: Additional request arguments
            
        Returns:
            Response data
        """
        url = urljoin(self.base_url, path)
        
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=json,
            timeout=self.timeout,
            verify=self.verify_ssl,
            **kwargs
        )
        
        # Handle errors
        if not response.ok:
            handle_response_error(response)
        
        # Return JSON response
        return response.json()
    
    def get(self, path: str, **kwargs) -> Dict[str, Any]:
        """GET request"""
        return self.request("GET", path, **kwargs)
    
    def post(self, path: str, **kwargs) -> Dict[str, Any]:
        """POST request"""
        return self.request("POST", path, **kwargs)
    
    def put(self, path: str, **kwargs) -> Dict[str, Any]:
        """PUT request"""
        return self.request("PUT", path, **kwargs)
    
    def patch(self, path: str, **kwargs) -> Dict[str, Any]:
        """PATCH request"""
        return self.request("PATCH", path, **kwargs)
    
    def delete(self, path: str, **kwargs) -> Dict[str, Any]:
        """DELETE request"""
        return self.request("DELETE", path, **kwargs)
'''
        
        (agency_dir / "client.py").write_text(client_content)
        
        # Generate exceptions.py
        exceptions_content = '''"""
SDK Exceptions
"""
from typing import Optional, Dict, Any
import requests


class AgencyError(Exception):
    """Base exception for Agency SDK"""
    
    def __init__(
        self,
        message: str,
        response: Optional[requests.Response] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(message)
        self.response = response
        self.error_code = error_code
        
        if response:
            self.status_code = response.status_code
            self.request_id = response.headers.get("X-Request-ID")
        else:
            self.status_code = None
            self.request_id = None


class AuthenticationError(AgencyError):
    """Authentication failed"""
    pass


class AuthorizationError(AgencyError):
    """Authorization failed"""
    pass


class NotFoundError(AgencyError):
    """Resource not found"""
    pass


class ValidationError(AgencyError):
    """Request validation failed"""
    
    def __init__(self, message: str, errors: Dict[str, Any], **kwargs):
        super().__init__(message, **kwargs)
        self.errors = errors


class RateLimitError(AgencyError):
    """Rate limit exceeded"""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ServerError(AgencyError):
    """Server error occurred"""
    pass


def handle_response_error(response: requests.Response) -> None:
    """
    Handle API error responses
    
    Args:
        response: HTTP response
        
    Raises:
        Appropriate AgencyError subclass
    """
    try:
        error_data = response.json()
        message = error_data.get("detail", response.reason)
        error_code = error_data.get("error_code")
    except:
        message = response.reason or f"HTTP {response.status_code}"
        error_code = None
    
    # Map status codes to exceptions
    if response.status_code == 401:
        raise AuthenticationError(message, response, error_code)
    elif response.status_code == 403:
        raise AuthorizationError(message, response, error_code)
    elif response.status_code == 404:
        raise NotFoundError(message, response, error_code)
    elif response.status_code == 422:
        errors = error_data.get("errors", {})
        raise ValidationError(message, errors, response=response, error_code=error_code)
    elif response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        retry_after = int(retry_after) if retry_after else None
        raise RateLimitError(message, retry_after, response=response, error_code=error_code)
    elif response.status_code >= 500:
        raise ServerError(message, response, error_code)
    else:
        raise AgencyError(message, response, error_code)
'''
        
        (agency_dir / "exceptions.py").write_text(exceptions_content)
        
        # Generate resource modules
        self._generate_python_resource_module(agency_dir, "auth", "Authentication")
        self._generate_python_resource_module(agency_dir, "users", "User Management")
        self._generate_python_resource_module(agency_dir, "content", "Content Management")
        self._generate_python_resource_module(agency_dir, "analytics", "Analytics")
        
        # Generate README
        readme_content = f"""# Agency Python SDK

Official Python SDK for the Agency API.

## Installation

```bash
pip install agency-sdk
```

## Quick Start

```python
from agency_sdk import Client

# Initialize client
client = Client(api_key="your-api-key")

# Get current user
user = client.users.get_current()
print(f"Hello, {{user['name']}}!")

# Create content
content = client.content.create({{
    "title": "My First Post",
    "body": "Hello, World!",
    "status": "draft"
}})

# Get analytics
analytics = client.analytics.get_overview(
    start_date="2024-01-01",
    end_date="2024-01-31"
)
```

## Authentication

The SDK supports multiple authentication methods:

### API Key
```python
client = Client(api_key="your-api-key")
```

### Access Token
```python
client = Client(access_token="your-jwt-token")
```

### Email/Password
```python
client = Client()
client.auth.login(email="user@example.com", password="password")
```

## Error Handling

```python
from agency_sdk import Client, AgencyError, RateLimitError

client = Client(api_key="your-api-key")

try:
    user = client.users.get(user_id=123)
except RateLimitError as e:
    print(f"Rate limited. Retry after {{e.retry_after}} seconds")
except AgencyError as e:
    print(f"API error: {{e.message}} ({{e.status_code}})")
```

## Pagination

```python
# Iterate through all pages
for page in client.content.list_pages(limit=100):
    for item in page["items"]:
        print(item["title"])

# Or get a specific page
page = client.content.list(page=2, limit=50)
```

## Documentation

Full documentation: https://docs.agency.com/python-sdk

## License

MIT License
"""
        
        (sdk_dir / "README.md").write_text(readme_content)
        
        logger.info(f"Generated Python SDK in {sdk_dir}")
        return str(sdk_dir)
    
    def _generate_python_resource_module(self, parent_dir: Path, name: str, description: str):
        """Generate a Python resource module"""
        content = f'''"""
{description} API resources
"""
from typing import Dict, Any, Optional, List, Iterator


class {name.capitalize()}:
    """
    {description} operations
    """
    
    def __init__(self, client):
        self.client = client
    
    def list(
        self,
        page: int = 1,
        limit: int = 20,
        **params
    ) -> Dict[str, Any]:
        """
        List {name}
        
        Args:
            page: Page number
            limit: Items per page
            **params: Additional query parameters
            
        Returns:
            Paginated response
        """
        return self.client.get(
            f"/api/v1/{name}",
            params={{"page": page, "limit": limit, **params}}
        )
    
    def list_pages(self, **params) -> Iterator[Dict[str, Any]]:
        """
        Iterate through all pages of {name}
        
        Args:
            **params: Query parameters
            
        Yields:
            Page of results
        """
        page = 1
        while True:
            response = self.list(page=page, **params)
            yield response
            
            if page >= response["pages"]:
                break
            page += 1
    
    def get(self, id: str) -> Dict[str, Any]:
        """
        Get {name[:-1]} by ID
        
        Args:
            id: Resource ID
            
        Returns:
            Resource data
        """
        return self.client.get(f"/api/v1/{name}/{{id}}")
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new {name[:-1]}
        
        Args:
            data: Resource data
            
        Returns:
            Created resource
        """
        return self.client.post(f"/api/v1/{name}", json=data)
    
    def update(self, id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update {name[:-1]}
        
        Args:
            id: Resource ID
            data: Update data
            
        Returns:
            Updated resource
        """
        return self.client.put(f"/api/v1/{name}/{{id}}", json=data)
    
    def delete(self, id: str) -> None:
        """
        Delete {name[:-1]}
        
        Args:
            id: Resource ID
        """
        self.client.delete(f"/api/v1/{name}/{{id}}")
'''
        
        (parent_dir / f"{name}.py").write_text(content)
    
    def generate_javascript_sdk(self) -> str:
        """Generate JavaScript/TypeScript SDK"""
        sdk_dir = self.output_dir / "javascript"
        sdk_dir.mkdir(exist_ok=True)
        
        # Generate package.json
        package_json = {
            "name": "@agency/sdk",
            "version": self.spec['info']['version'],
            "description": self.spec['info']['description'].split('.')[0],
            "main": "dist/index.js",
            "types": "dist/index.d.ts",
            "scripts": {
                "build": "tsc",
                "test": "jest",
                "lint": "eslint src/**/*.ts",
                "prepublish": "npm run build"
            },
            "keywords": ["agency", "api", "sdk"],
            "author": "Agency API Team",
            "license": "MIT",
            "dependencies": {
                "axios": "^1.6.0",
                "form-data": "^4.0.0"
            },
            "devDependencies": {
                "@types/node": "^20.0.0",
                "typescript": "^5.0.0",
                "jest": "^29.0.0",
                "eslint": "^8.0.0"
            },
            "repository": {
                "type": "git",
                "url": "https://github.com/agency/javascript-sdk"
            }
        }
        
        (sdk_dir / "package.json").write_text(json.dumps(package_json, indent=2))
        
        # Generate TypeScript config
        tsconfig = {
            "compilerOptions": {
                "target": "ES2020",
                "module": "commonjs",
                "lib": ["ES2020"],
                "outDir": "./dist",
                "rootDir": "./src",
                "strict": true,
                "esModuleInterop": true,
                "skipLibCheck": true,
                "forceConsistentCasingInFileNames": true,
                "declaration": true,
                "declarationMap": true,
                "sourceMap": true
            },
            "include": ["src/**/*"],
            "exclude": ["node_modules", "dist", "tests"]
        }
        
        (sdk_dir / "tsconfig.json").write_text(json.dumps(tsconfig, indent=2))
        
        # Generate source files
        src_dir = sdk_dir / "src"
        src_dir.mkdir(exist_ok=True)
        
        # Generate index.ts
        index_content = '''/**
 * Agency SDK for JavaScript/TypeScript
 */
export { AgencyClient } from './client';
export * from './types';
export * from './errors';
export { Auth } from './resources/auth';
export { Users } from './resources/users';
export { Content } from './resources/content';
export { Analytics } from './resources/analytics';
'''
        
        (src_dir / "index.ts").write_text(index_content)
        
        # Generate client.ts
        client_content = '''import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import { Auth } from './resources/auth';
import { Users } from './resources/users';
import { Content } from './resources/content';
import { Analytics } from './resources/analytics';
import { handleApiError } from './errors';

export interface ClientOptions {
  apiKey?: string;
  accessToken?: string;
  baseURL?: string;
  timeout?: number;
}

export class AgencyClient {
  private client: AxiosInstance;
  
  public auth: Auth;
  public users: Users;
  public content: Content;
  public analytics: Analytics;
  
  constructor(options: ClientOptions = {}) {
    const config: AxiosRequestConfig = {
      baseURL: options.baseURL || 'https://api.agency.com',
      timeout: options.timeout || 30000,
      headers: {
        'User-Agent': `agency-js-sdk/${process.env.npm_package_version || '1.0.0'}`,
        'Content-Type': 'application/json',
      },
    };
    
    // Set authentication
    if (options.apiKey) {
      config.headers!['X-API-Key'] = options.apiKey;
    } else if (options.accessToken) {
      config.headers!['Authorization'] = `Bearer ${options.accessToken}`;
    }
    
    this.client = axios.create(config);
    
    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      response => response,
      error => handleApiError(error)
    );
    
    // Initialize resources
    this.auth = new Auth(this.client);
    this.users = new Users(this.client);
    this.content = new Content(this.client);
    this.analytics = new Analytics(this.client);
  }
  
  /**
   * Set access token for authenticated requests
   */
  setAccessToken(token: string): void {
    this.client.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }
  
  /**
   * Remove authentication
   */
  clearAuth(): void {
    delete this.client.defaults.headers.common['Authorization'];
    delete this.client.defaults.headers.common['X-API-Key'];
  }
}
'''
        
        (src_dir / "client.ts").write_text(client_content)
        
        # Generate types.ts
        types_content = '''/**
 * Common types used throughout the SDK
 */

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'user' | 'admin' | 'super_admin';
  created_at: string;
  updated_at: string;
}

export interface Content {
  id: string;
  title: string;
  body: string;
  status: 'draft' | 'published' | 'archived';
  author_id: string;
  created_at: string;
  updated_at: string;
  published_at?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pages: number;
  limit: number;
}

export interface ApiError {
  detail: string;
  status_code: number;
  error_code?: string;
  timestamp: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  mfa_code?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string;
}
'''
        
        (src_dir / "types.ts").write_text(types_content)
        
        # Generate errors.ts
        errors_content = '''import { AxiosError } from 'axios';
import { ApiError } from './types';

export class AgencyError extends Error {
  public statusCode?: number;
  public errorCode?: string;
  public requestId?: string;
  
  constructor(message: string, statusCode?: number, errorCode?: string) {
    super(message);
    this.name = 'AgencyError';
    this.statusCode = statusCode;
    this.errorCode = errorCode;
  }
}

export class AuthenticationError extends AgencyError {
  constructor(message: string) {
    super(message, 401, 'AUTHENTICATION_ERROR');
    this.name = 'AuthenticationError';
  }
}

export class AuthorizationError extends AgencyError {
  constructor(message: string) {
    super(message, 403, 'AUTHORIZATION_ERROR');
    this.name = 'AuthorizationError';
  }
}

export class NotFoundError extends AgencyError {
  constructor(message: string) {
    super(message, 404, 'NOT_FOUND');
    this.name = 'NotFoundError';
  }
}

export class ValidationError extends AgencyError {
  public errors: any;
  
  constructor(message: string, errors: any) {
    super(message, 422, 'VALIDATION_ERROR');
    this.name = 'ValidationError';
    this.errors = errors;
  }
}

export class RateLimitError extends AgencyError {
  public retryAfter?: number;
  
  constructor(message: string, retryAfter?: number) {
    super(message, 429, 'RATE_LIMIT_ERROR');
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter;
  }
}

export function handleApiError(error: AxiosError): never {
  const response = error.response;
  const data = response?.data as ApiError;
  const message = data?.detail || error.message;
  
  switch (response?.status) {
    case 401:
      throw new AuthenticationError(message);
    case 403:
      throw new AuthorizationError(message);
    case 404:
      throw new NotFoundError(message);
    case 422:
      throw new ValidationError(message, data);
    case 429:
      const retryAfter = response.headers['retry-after'];
      throw new RateLimitError(message, retryAfter ? parseInt(retryAfter) : undefined);
    default:
      throw new AgencyError(message, response?.status, data?.error_code);
  }
}
'''
        
        (src_dir / "errors.ts").write_text(errors_content)
        
        # Generate README
        readme_content = f"""# Agency JavaScript/TypeScript SDK

Official JavaScript/TypeScript SDK for the Agency API.

## Installation

```bash
npm install @agency/sdk
# or
yarn add @agency/sdk
```

## Quick Start

```typescript
import {{ AgencyClient }} from '@agency/sdk';

// Initialize client
const client = new AgencyClient({{
  apiKey: 'your-api-key'
}});

// Get current user
const user = await client.users.getCurrent();
console.log(`Hello, ${{user.name}}!`);

// Create content
const content = await client.content.create({{
  title: 'My First Post',
  body: 'Hello, World!',
  status: 'draft'
}});

// Get analytics
const analytics = await client.analytics.getOverview({{
  startDate: '2024-01-01',
  endDate: '2024-01-31'
}});
```

## Authentication

### API Key
```typescript
const client = new AgencyClient({{
  apiKey: 'your-api-key'
}});
```

### Access Token
```typescript
const client = new AgencyClient({{
  accessToken: 'your-jwt-token'
}});
```

### Email/Password
```typescript
const client = new AgencyClient();
const {{ access_token }} = await client.auth.login({{
  email: 'user@example.com',
  password: 'password'
}});
client.setAccessToken(access_token);
```

## Error Handling

```typescript
import {{ AgencyClient, RateLimitError, AgencyError }} from '@agency/sdk';

try {{
  const user = await client.users.get('123');
}} catch (error) {{
  if (error instanceof RateLimitError) {{
    console.log(`Rate limited. Retry after ${{error.retryAfter}} seconds`);
  }} else if (error instanceof AgencyError) {{
    console.log(`API error: ${{error.message}} (${{error.statusCode}})`);
  }}
}}
```

## TypeScript Support

This SDK is written in TypeScript and provides full type definitions.

## Documentation

Full documentation: https://docs.agency.com/javascript-sdk

## License

MIT License
"""
        
        (sdk_dir / "README.md").write_text(readme_content)
        
        logger.info(f"Generated JavaScript SDK in {sdk_dir}")
        return str(sdk_dir)
    
    def generate_all_sdks(self) -> Dict[str, str]:
        """Generate SDKs for all supported languages"""
        sdks = {
            "python": self.generate_python_sdk(),
            "javascript": self.generate_javascript_sdk()
        }
        
        logger.info(f"Generated {len(sdks)} SDKs")
        return sdks