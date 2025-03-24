#!/usr/bin/env python3
"""
ZVision Deployment Script

This script prepares the ZVision application for production deployment.
It sets up the necessary directory structure and checks for required components.
"""

import os
import shutil
import argparse
import sys
import json
from pathlib import Path

def setup_dirs(react_build_path=None):
    """Set up the directory structure for deployment."""
    # Create directories
    os.makedirs("static/build", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("database", exist_ok=True)
    
    print("✅ Created directory structure")
    
    # Copy React build files if provided
    if react_build_path:
        react_path = Path(react_build_path)
        if not react_path.exists():
            print(f"❌ Error: React build path does not exist: {react_path}")
            sys.exit(1)
            
        # Copy all files from the React build directory to static/build
        print(f"📁 Copying React build from {react_path} to static/build...")
        
        # Check if the build directory contains index.html
        if not (react_path / "index.html").exists():
            print(f"❌ Error: React build path does not contain index.html: {react_path}")
            sys.exit(1)
            
        # Copy all files
        for item in react_path.glob("*"):
            if item.is_file():
                shutil.copy2(item, f"static/build/{item.name}")
            elif item.is_dir():
                shutil.copytree(
                    item, 
                    f"static/build/{item.name}", 
                    dirs_exist_ok=True
                )
                
        print("✅ Copied React build files")
    else:
        print("⚠️ No React build path provided. Frontend will not be available.")

def create_env_file(env_type="production"):
    """Create a .env file with the appropriate settings."""
    if env_type == "production":
        env_content = """# ZVision Production Environment
ZVISION_ENV=production
DATABASE_PATH=database/zvision.db
JWT_SECRET_KEY=generate-a-strong-secret-key-here
JWT_EXPIRE_MINUTES=30
PRODUCTION_DOMAIN=https://your-production-domain.com
"""
    else:
        env_content = """# ZVision Development Environment
ZVISION_ENV=development
DATABASE_PATH=database/zvision.db
JWT_SECRET_KEY=dev-secret-key
JWT_EXPIRE_MINUTES=30
"""

    with open(".env", "w") as f:
        f.write(env_content)
        
    print(f"✅ Created .env file for {env_type} environment")
    
def create_service_file():
    """Create a systemd service file for running the application."""
    service_content = """[Unit]
Description=ZVision Entry/Exit Detection System
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/zvision
ExecStart=/home/pi/.local/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5
Environment=PYTHONPATH=/home/pi/zvision
EnvironmentFile=/home/pi/zvision/.env

[Install]
WantedBy=multi-user.target
"""

    with open("zvision.service", "w") as f:
        f.write(service_content)
        
    print("✅ Created systemd service file")
    print("ℹ️ To install the service:")
    print("   1. sudo cp zvision.service /etc/systemd/system/")
    print("   2. sudo systemctl daemon-reload")
    print("   3. sudo systemctl enable zvision")
    print("   4. sudo systemctl start zvision")

def check_dependencies():
    """Check if all required dependencies are installed."""
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import python_jose
        import passlib
        import bcrypt
        print("✅ All required Python packages are installed")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("ℹ️ Install dependencies with: pip install -r requirements.txt")
        return False
    
    return True

def create_requirements():
    """Create a requirements.txt file."""
    requirements = """fastapi>=0.103.1
uvicorn>=0.23.2
python-jose[cryptography]>=3.3.0
passlib>=1.7.4
python-multipart>=0.0.6
requests>=2.31.0
sqlalchemy>=2.0.21
bcrypt>=4.0.1
opencv-python>=4.8.0.76
ultralytics>=8.0.196
"""

    with open("requirements.txt", "w") as f:
        f.write(requirements)
        
    print("✅ Created requirements.txt")

def main():
    parser = argparse.ArgumentParser(description="Deploy ZVision to production")
    parser.add_argument("--react-build", help="Path to React build directory")
    parser.add_argument("--env", choices=["production", "development"], default="production", 
                      help="Environment type (default: production)")
    parser.add_argument("--service", action="store_true", help="Create systemd service file")
    parser.add_argument("--requirements", action="store_true", help="Create requirements.txt file")
    
    args = parser.parse_args()
    
    print("🚀 Deploying ZVision...")
    
    # Setup directory structure and copy React build if provided
    setup_dirs(args.react_build)
    
    # Create .env file with the appropriate settings
    create_env_file(args.env)
    
    # Create systemd service file if requested
    if args.service:
        create_service_file()
    
    # Create requirements.txt if requested
    if args.requirements:
        create_requirements()
    
    # Check dependencies
    check_dependencies()
    
    print("✅ Deployment setup complete!")
    print("ℹ️ Start the server with: uvicorn main:app --host 0.0.0.0 --port 8000")
    
if __name__ == "__main__":
    main() 