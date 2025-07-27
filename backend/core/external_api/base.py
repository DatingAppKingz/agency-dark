"""
Base API Client and Exception classes
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, Union, List
import asyncio
import json
from datetime import datetime
import aiohttp
from pydantic import BaseModel

from .retry import RetryPolicy, ExponentialBackoff
from .logging import APILogger
from .config import APIConfig


class APIError(Exception):
    """Base API exception"""
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class APIConnectionError(APIError):
    """Connection error"""
    pass


class APITimeoutError(APIError):
    """Timeout error"""
    pass


class APIAuthenticationError(APIError):
    """Authentication error"""
    pass


class APIRateLimitError(APIError):
    """Rate limit exceeded error"""
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class APIValidationError(APIError):
    """Validation error"""
    pass


class BaseAPIClient(ABC):
    """Abstract base class for API clients"""
    
    def __init__(
        self,
        config: APIConfig,
        retry_policy: Optional[RetryPolicy] = None,
        logger: Optional[APILogger] = None
    ):
        self.config = config
        self.retry_policy = retry_policy or ExponentialBackoff()
        self.logger = logger or APILogger(self.__class__.__name__)
        self._session: Optional[aiohttp.ClientSession] = None
        
    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.get_default_headers()
            )
        return self._session
        
    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
            
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        
    @abstractmethod
    def get_default_headers(self) -> Dict[str, str]:
        """Get default headers for all requests"""
        pass
        
    @abstractmethod
    async def authenticate(self) -> Dict[str, Any]:
        """Authenticate with the API"""
        pass
        
    async def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Union[Dict[str, Any], BaseModel]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make an API request with retry logic"""
        url = f"{self.config.base_url}{endpoint}"
        
        # Convert Pydantic models to dict
        if isinstance(data, BaseModel):
            data = data.model_dump(exclude_unset=True)
            
        # Merge headers
        request_headers = self.get_default_headers()
        if headers:
            request_headers.update(headers)
            
        # Log request
        self.logger.log_request(method, url, data, params, request_headers)
        
        # Retry logic
        last_exception = None
        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                response = await self._make_request(
                    method, url, data, params, request_headers, **kwargs
                )
                
                # Log successful response
                self.logger.log_response(
                    method, url, response.status, 
                    await response.text(), 
                    dict(response.headers)
                )
                
                # Parse response
                return await self._parse_response(response)
                
            except (APIConnectionError, APITimeoutError, APIRateLimitError) as e:
                last_exception = e
                
                # Check if we should retry
                if attempt < self.retry_policy.max_retries:
                    retry_delay = self.retry_policy.get_retry_delay(attempt)
                    
                    # For rate limit errors, use the retry_after if provided
                    if isinstance(e, APIRateLimitError) and e.retry_after:
                        retry_delay = e.retry_after
                        
                    self.logger.log_retry(attempt + 1, retry_delay, str(e))
                    await asyncio.sleep(retry_delay)
                else:
                    # Log final failure
                    self.logger.log_error(method, url, e)
                    raise
                    
            except Exception as e:
                # Log non-retryable errors
                self.logger.log_error(method, url, e)
                raise
                
        # If we've exhausted retries
        if last_exception:
            raise last_exception
            
    async def _make_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]],
        params: Optional[Dict[str, Any]],
        headers: Dict[str, str],
        **kwargs
    ) -> aiohttp.ClientResponse:
        """Make the actual HTTP request"""
        try:
            # Prepare request kwargs
            request_kwargs = {
                'headers': headers,
                'params': params,
                **kwargs
            }
            
            # Add data based on content type
            if data is not None:
                if headers.get('Content-Type') == 'application/json':
                    request_kwargs['json'] = data
                else:
                    request_kwargs['data'] = data
                    
            # Make request
            async with self.session.request(method, url, **request_kwargs) as response:
                # Check for rate limiting
                if response.status == 429:
                    retry_after = response.headers.get('Retry-After')
                    raise APIRateLimitError(
                        "Rate limit exceeded",
                        retry_after=int(retry_after) if retry_after else None
                    )
                    
                # Check for authentication errors
                if response.status in (401, 403):
                    raise APIAuthenticationError(
                        f"Authentication failed: {response.status}"
                    )
                    
                # Return response for further processing
                return response
                
        except asyncio.TimeoutError:
            raise APITimeoutError(f"Request timeout: {url}")
        except aiohttp.ClientError as e:
            raise APIConnectionError(f"Connection error: {str(e)}")
            
    async def _parse_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Parse API response"""
        try:
            # Try to parse JSON
            if 'application/json' in response.headers.get('Content-Type', ''):
                data = await response.json()
            else:
                # Return text content as data
                text = await response.text()
                data = {'content': text}
                
            # Check for HTTP errors
            if response.status >= 400:
                error_message = self._extract_error_message(data)
                error_code = self._extract_error_code(data)
                
                if response.status < 500:
                    raise APIValidationError(error_message, code=error_code, details=data)
                else:
                    raise APIError(error_message, code=error_code, details=data)
                    
            return data
            
        except json.JSONDecodeError:
            raise APIError(f"Invalid JSON response: {await response.text()}")
            
    def _extract_error_message(self, data: Dict[str, Any]) -> str:
        """Extract error message from response data"""
        # Common error message fields
        for field in ['error', 'message', 'error_message', 'detail']:
            if field in data:
                if isinstance(data[field], dict):
                    return self._extract_error_message(data[field])
                return str(data[field])
        return "Unknown error"
        
    def _extract_error_code(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract error code from response data"""
        # Common error code fields
        for field in ['code', 'error_code', 'error_type']:
            if field in data:
                return str(data[field])
        return None
        
    # Convenience methods
    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """GET request"""
        return await self.request('GET', endpoint, **kwargs)
        
    async def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """POST request"""
        return await self.request('POST', endpoint, **kwargs)
        
    async def put(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """PUT request"""
        return await self.request('PUT', endpoint, **kwargs)
        
    async def patch(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """PATCH request"""
        return await self.request('PATCH', endpoint, **kwargs)
        
    async def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """DELETE request"""
        return await self.request('DELETE', endpoint, **kwargs)