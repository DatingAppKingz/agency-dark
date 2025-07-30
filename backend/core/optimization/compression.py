"""
Response compression and optimization middleware.
"""

import gzip
import zlib
import brotli
from typing import Any, Callable, Dict, List, Optional, Set
from io import BytesIO

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from core.logging import get_logger

logger = get_logger(__name__)


class CompressionMiddleware(BaseHTTPMiddleware):
    """Middleware for compressing HTTP responses."""
    
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 1024,
        compression_level: int = 6,
        excluded_paths: Optional[Set[str]] = None,
        excluded_media_types: Optional[Set[str]] = None
    ):
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level
        self.excluded_paths = excluded_paths or {"/health", "/metrics"}
        self.excluded_media_types = excluded_media_types or {
            "image/jpeg",
            "image/png",
            "image/gif",
            "video/mp4",
            "application/zip",
            "application/gzip"
        }
        
        # Compression statistics
        self.stats = {
            "total_responses": 0,
            "compressed_responses": 0,
            "total_bytes_saved": 0,
            "compression_errors": 0
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and compress response if applicable."""
        # Skip compression for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Get accepted encodings
        accept_encoding = request.headers.get("accept-encoding", "")
        
        # Process request
        response = await call_next(request)
        
        # Update statistics
        self.stats["total_responses"] += 1
        
        # Check if compression should be applied
        if not self._should_compress(response, accept_encoding):
            return response
        
        # Choose compression algorithm
        encoding = self._choose_encoding(accept_encoding)
        if not encoding:
            return response
        
        # Compress response
        return await self._compress_response(response, encoding)
    
    def _should_compress(self, response: Response, accept_encoding: str) -> bool:
        """Determine if response should be compressed."""
        # Check if client accepts compression
        if not accept_encoding:
            return False
        
        # Check response status
        if response.status_code < 200 or response.status_code >= 300:
            return False
        
        # Check if already compressed
        if response.headers.get("content-encoding"):
            return False
        
        # Check media type
        content_type = response.headers.get("content-type", "")
        media_type = content_type.split(";")[0].strip()
        
        if media_type in self.excluded_media_types:
            return False
        
        # Check content length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) < self.minimum_size:
            return False
        
        return True
    
    def _choose_encoding(self, accept_encoding: str) -> Optional[str]:
        """Choose the best compression encoding."""
        accept_encoding = accept_encoding.lower()
        
        # Priority order: br > gzip > deflate
        if "br" in accept_encoding and brotli:
            return "br"
        elif "gzip" in accept_encoding:
            return "gzip"
        elif "deflate" in accept_encoding:
            return "deflate"
        
        return None
    
    async def _compress_response(self, response: Response, encoding: str) -> Response:
        """Compress response body."""
        try:
            # Get response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            original_size = len(body)
            
            # Compress body
            if encoding == "br":
                compressed_body = brotli.compress(
                    body,
                    quality=self.compression_level
                )
            elif encoding == "gzip":
                compressed_body = gzip.compress(
                    body,
                    compresslevel=self.compression_level
                )
            elif encoding == "deflate":
                compressed_body = zlib.compress(
                    body,
                    level=self.compression_level
                )
            else:
                return response
            
            compressed_size = len(compressed_body)
            
            # Only use compression if it reduces size
            if compressed_size >= original_size:
                return response
            
            # Update statistics
            self.stats["compressed_responses"] += 1
            self.stats["total_bytes_saved"] += original_size - compressed_size
            
            # Create compressed response
            headers = dict(response.headers)
            headers["content-encoding"] = encoding
            headers["content-length"] = str(compressed_size)
            headers["vary"] = "Accept-Encoding"
            
            # Add compression ratio header for debugging
            compression_ratio = (1 - compressed_size / original_size) * 100
            headers["x-compression-ratio"] = f"{compression_ratio:.1f}%"
            
            return Response(
                content=compressed_body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type
            )
            
        except Exception as e:
            logger.error(f"Compression error: {e}")
            self.stats["compression_errors"] += 1
            return response
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        compression_rate = (
            self.stats["compressed_responses"] / self.stats["total_responses"] * 100
            if self.stats["total_responses"] > 0
            else 0
        )
        
        return {
            **self.stats,
            "compression_rate": f"{compression_rate:.1f}%",
            "average_bytes_saved": (
                self.stats["total_bytes_saved"] / self.stats["compressed_responses"]
                if self.stats["compressed_responses"] > 0
                else 0
            )
        }


class StreamingCompressionMiddleware:
    """Middleware for compressing streaming responses."""
    
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 1024,
        compression_level: int = 6
    ):
        self.app = app
        self.minimum_size = minimum_size
        self.compression_level = compression_level
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Check accept-encoding header
        headers = dict(scope["headers"])
        accept_encoding = headers.get(b"accept-encoding", b"").decode()
        
        # Choose encoding
        if "gzip" in accept_encoding:
            encoding = "gzip"
        elif "deflate" in accept_encoding:
            encoding = "deflate"
        else:
            await self.app(scope, receive, send)
            return
        
        # Wrap send function
        compressor = StreamCompressor(send, encoding, self.compression_level)
        await self.app(scope, receive, compressor.send)


class StreamCompressor:
    """Compress streaming response data."""
    
    def __init__(self, send: Send, encoding: str, level: int):
        self.send = send
        self.encoding = encoding
        self.level = level
        self.compressor = None
        self.headers_sent = False
    
    async def send(self, message: Dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            # Modify headers to include content-encoding
            headers = list(message.get("headers", []))
            headers.append((b"content-encoding", self.encoding.encode()))
            headers.append((b"vary", b"Accept-Encoding"))
            
            # Remove content-length as it will change
            headers = [
                (name, value)
                for name, value in headers
                if name.lower() != b"content-length"
            ]
            
            message["headers"] = headers
            self.headers_sent = True
            
            # Initialize compressor
            if self.encoding == "gzip":
                self.compressor = gzip.GzipFile(
                    mode="wb",
                    fileobj=BytesIO(),
                    compresslevel=self.level
                )
            elif self.encoding == "deflate":
                self.compressor = zlib.compressobj(level=self.level)
            
            await self.send(message)
            
        elif message["type"] == "http.response.body":
            if not self.headers_sent:
                # Headers must be sent first
                await self.send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": []
                })
            
            body = message.get("body", b"")
            more_body = message.get("more_body", False)
            
            if body:
                # Compress body
                if self.encoding == "gzip":
                    self.compressor.write(body)
                    compressed = self.compressor.fileobj.getvalue()
                    self.compressor.fileobj.truncate(0)
                    self.compressor.fileobj.seek(0)
                else:
                    compressed = self.compressor.compress(body)
            else:
                compressed = b""
            
            if not more_body and self.compressor:
                # Flush remaining data
                if self.encoding == "gzip":
                    self.compressor.close()
                    compressed += self.compressor.fileobj.getvalue()
                else:
                    compressed += self.compressor.flush()
            
            await self.send({
                "type": "http.response.body",
                "body": compressed,
                "more_body": more_body
            })


# Response optimization utilities
def optimize_json_response(data: Any) -> Dict[str, Any]:
    """Optimize JSON response for size."""
    import json
    
    # Remove null values
    def remove_nulls(obj):
        if isinstance(obj, dict):
            return {k: remove_nulls(v) for k, v in obj.items() if v is not None}
        elif isinstance(obj, list):
            return [remove_nulls(item) for item in obj]
        return obj
    
    # Remove empty arrays and objects
    def remove_empty(obj):
        if isinstance(obj, dict):
            return {
                k: remove_empty(v)
                for k, v in obj.items()
                if v not in (None, [], {})
            }
        elif isinstance(obj, list):
            return [remove_empty(item) for item in obj]
        return obj
    
    optimized = remove_nulls(data)
    optimized = remove_empty(optimized)
    
    return optimized


def estimate_compression_ratio(content: bytes, encoding: str = "gzip") -> float:
    """Estimate compression ratio for content."""
    original_size = len(content)
    
    if encoding == "gzip":
        compressed_size = len(gzip.compress(content))
    elif encoding == "deflate":
        compressed_size = len(zlib.compress(content))
    elif encoding == "br" and brotli:
        compressed_size = len(brotli.compress(content))
    else:
        return 0.0
    
    return 1 - (compressed_size / original_size)