from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import HTTPS_REQUIRED, IS_PRODUCTION

class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce HTTPS in production.
    Redirects HTTP requests to HTTPS and checks for secure headers.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Skip middleware in development
        if not IS_PRODUCTION or not HTTPS_REQUIRED:
            return await call_next(request)
            
        # Check if request is secure
        protocol = request.headers.get('x-forwarded-proto', 'http')
        host = request.headers.get('host', '')
        
        # X-Forwarded-Proto header often set by load balancers to indicate original protocol
        if protocol == 'http':
            # Return a 301 redirect to the HTTPS version of the URL
            url = f"https://{host}{request.url.path}"
            if request.query_params:
                url += f"?{request.query_params}"
            
            from starlette.responses import RedirectResponse
            return RedirectResponse(url, status_code=301)
        
        # Proceed with the request if it's already HTTPS
        return await call_next(request) 