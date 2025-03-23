from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.config import IS_PRODUCTION

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    These headers help protect against various web security vulnerabilities.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Process the request
        response = await call_next(request)
        
        # Add security headers
        self._add_security_headers(response)
        
        return response
    
    def _add_security_headers(self, response: Response):
        """Add security headers to the response."""
        
        # Content Security Policy (CSP): Controls which resources can be loaded
        if IS_PRODUCTION:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'"
            )
        else:
            # More permissive CSP for development
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'"
            )
            
        # X-Content-Type-Options: Prevents MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-Frame-Options: Prevents your page from being put in an iframe
        response.headers["X-Frame-Options"] = "DENY"
        
        # X-XSS-Protection: Enables XSS filtering in browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer-Policy: Controls information sent in the Referer header
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions-Policy: Controls which browser features can be used
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        
        # Strict-Transport-Security: Forces HTTPS usage
        if IS_PRODUCTION:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains" 