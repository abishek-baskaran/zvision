import os
from datetime import timedelta
from secrets import token_hex

# Environment settings
ENVIRONMENT = os.environ.get("ZVISION_ENV", "development")
IS_PRODUCTION = ENVIRONMENT == "production"
DEBUG = not IS_PRODUCTION

# JWT Configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "30"))

# Database Configuration
DATABASE_PATH = os.environ.get("DATABASE_PATH", "database/zvision.db")

# Server Configuration
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))

# Frontend URL
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# CORS Configuration
if IS_PRODUCTION:
    # In production, only allow the specific domain
    PRODUCTION_DOMAIN = os.environ.get("PRODUCTION_DOMAIN", "https://your-production-domain.com")
    ALLOWED_ORIGINS = [PRODUCTION_DOMAIN]
else:
    # In development, allow multiple origins for testing
    ALLOWED_ORIGINS = [
        "http://localhost:3000",     # React dev server
        "http://localhost:5000",     # Optional: production build served locally
        "http://localhost:8080",     # Your frontend
        "http://localhost:8000",     # Local FastAPI server
        "http://127.0.0.1:3000",     # React dev server (IP version)
        "http://127.0.0.1:5000",     # Optional: production build (IP version)
        "http://127.0.0.1:8080",     # Your frontend (IP version)
        "http://127.0.0.1:8000",     # Local FastAPI server (IP version)
        "http://192.168.31.36:8080", # Your desktop's network IP
        "http://192.168.31.36:8081", # Your desktop's network IP
        "http://192.168.31.37:8080", # Raspberry Pi's IP address
        "http://192.168.31.37:8000", # Raspberry Pi's API server
        "*",                         # Allow all origins during testing
    ]

# Static files configuration
STATIC_DIR = os.environ.get("STATIC_DIR", "static")
BUILD_DIR = os.environ.get("BUILD_DIR", f"{STATIC_DIR}/build")

# Security settings
SECURE_COOKIES = IS_PRODUCTION  # Only use secure cookies in production
HTTPS_REQUIRED = IS_PRODUCTION  # Require HTTPS in production 