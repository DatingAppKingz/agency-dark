"""
Response compression middleware for API optimization
"""
import gzip
import zlib
from typing import Callable, List, Optional
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
import brotli

from core.config import get_settings
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class CompressionMiddleware:
    """Middleware for compressing API responses"""
    
    def __init__(
        self,
        app,
        minimum_size: int = 500,
        compression_level: int = 6,
        exclude_paths: Optional[List[str]] = None
    ):
        self.app = app
        self.minimum_size = minimum_size
        self.compression_level = compression_level
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json"]
        
        # Compression algorithms in order of preference
        self.algorithms = {
            "br": self._compress_brotli,
            "gzip": self._compress_gzip,
            "deflate": self._compress_deflate
        }
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        # Skip compression for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Get accepted encodings
        accept_encoding = request.headers.get("accept-encoding", "")
        
        # Process request
        response = await call_next(request)
        
        # Skip if response is streaming or too small
        if (
            isinstance(response, StreamingResponse) or
            response.headers.get("content-encoding") or
            int(response.headers.get("content-length", 0)) < self.minimum_size
        ):
            return response
        
        # Determine best encoding
        encoding = self._select_encoding(accept_encoding)
        if not encoding:
            return response
        
        # Compress response
        return await self._compress_response(response, encoding)
    
    def _select_encoding(self, accept_encoding: str) -> Optional[str]:
        """Select the best encoding based on client preferences"""
        accept_encoding = accept_encoding.lower()
        
        # Check for Brotli support (best compression)
        if "br" in accept_encoding and "br" in self.algorithms:
            return "br"
        
        # Check for gzip support (most common)
        if "gzip" in accept_encoding:
            return "gzip"
        
        # Check for deflate support
        if "deflate" in accept_encoding:
            return "deflate"
        
        return None
    
    async def _compress_response(
        self,
        response: Response,
        encoding: str
    ) -> Response:
        """Compress response body"""
        # Read response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        
        # Skip if body is too small
        if len(body) < self.minimum_size:
            response.body = body
            return response
        
        # Compress body
        compress_func = self.algorithms.get(encoding)
        if not compress_func:
            response.body = body
            return response
        
        compressed_body = compress_func(body)
        
        # Update response
        response.body = compressed_body
        response.headers["content-encoding"] = encoding
        response.headers["content-length"] = str(len(compressed_body))
        
        # Add Vary header
        vary = response.headers.get("vary", "")
        if vary:
            vary = f"{vary}, Accept-Encoding"
        else:
            vary = "Accept-Encoding"
        response.headers["vary"] = vary
        
        logger.debug(
            f"Compressed response: {len(body)} -> {len(compressed_body)} bytes "
            f"({len(compressed_body) / len(body) * 100:.1f}%) using {encoding}"
        )
        
        return response
    
    def _compress_gzip(self, data: bytes) -> bytes:
        """Compress data using gzip"""
        return gzip.compress(data, compresslevel=self.compression_level)
    
    def _compress_deflate(self, data: bytes) -> bytes:
        """Compress data using deflate"""
        return zlib.compress(data, level=self.compression_level)
    
    def _compress_brotli(self, data: bytes) -> bytes:
        """Compress data using Brotli"""
        return brotli.compress(
            data,
            quality=self.compression_level,
            mode=brotli.MODE_TEXT
        )


class CacheControlMiddleware:
    """Middleware for setting cache control headers"""
    
    def __init__(
        self,
        app,
        default_max_age: int = 0,
        cache_paths: Optional[dict] = None
    ):
        self.app = app
        self.default_max_age = default_max_age
        self.cache_paths = cache_paths or {
            "/api/v1/static": 86400,      # 24 hours
            "/api/v1/analytics": 300,      # 5 minutes
            "/api/v1/models/list": 60,     # 1 minute
        }
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Skip if cache control already set
        if "cache-control" in response.headers:
            return response
        
        # Determine cache max age
        max_age = self.default_max_age
        for path, age in self.cache_paths.items():
            if request.url.path.startswith(path):
                max_age = age
                break
        
        # Set cache control header
        if max_age > 0:
            response.headers["cache-control"] = f"public, max-age={max_age}"
        else:
            response.headers["cache-control"] = "no-cache, no-store, must-revalidate"
        
        return response


class ETagMiddleware:
    """Middleware for handling ETags"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        # Check if client sent If-None-Match header
        if_none_match = request.headers.get("if-none-match")
        
        # Process request
        response = await call_next(request)
        
        # Skip if not a GET request or no body
        if request.method != "GET" or not hasattr(response, "body"):
            return response
        
        # Generate ETag from response body
        import hashlib
        
        # Read response body
        body = b""
        if hasattr(response, "body_iterator"):
            async for chunk in response.body_iterator:
                body += chunk
        else:
            body = response.body
        
        etag = f'"{hashlib.md5(body).hexdigest()}"'
        
        # Check if ETag matches
        if if_none_match == etag:
            # Return 304 Not Modified
            return Response(status_code=304, headers={"etag": etag})
        
        # Set ETag header
        response.body = body
        response.headers["etag"] = etag
        
        return response