"""
API Key authentication middleware.
Validates X-API-Key header against configured keys.
"""

from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time
import config

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    FastAPI dependency that validates the API key.
    Returns the key name (e.g. 'antigravity', 'cursor') for logging.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={"error": "Missing API key", "hint": "Set X-API-Key header"}
        )
    
    for name, secret in config.API_KEYS.items():
        if api_key == secret:
            return name
    
    raise HTTPException(
        status_code=401,
        detail={"error": "Invalid API key"}
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiter.
    Limits requests per IP to prevent abuse.
    """
    
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = {}
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/"):
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Clean old entries
        if client_ip in self.requests:
            self.requests[client_ip] = [
                t for t in self.requests[client_ip] 
                if now - t < self.window_seconds
            ]
        else:
            self.requests[client_ip] = []
        
        # Check rate limit
        if len(self.requests[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "retry_after": self.window_seconds}
            )
        
        self.requests[client_ip].append(now)
        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all API requests for audit trail."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Only log non-health-check requests
        if request.url.path not in ("/health", "/"):
            client_ip = request.client.host if request.client else "unknown"
            print(
                f"[API] {request.method} {request.url.path} "
                f"-> {response.status_code} "
                f"({duration:.3f}s) "
                f"from {client_ip}"
            )
        
        return response
