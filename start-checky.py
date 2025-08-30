#!/usr/bin/env python3
"""
Startup script for Checky Multimodal Assistant.

This script starts the Checky web application with proper configuration
and error handling.
"""

import os
import sys
import logging
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def check_environment():
    """Check that required environment variables are set."""
    required_vars = [
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT", 
        "GEMINI_API_KEY"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Please check your .env file or set these variables.")
        print("   See env-checky.example for reference.")
        return False
    
    # Check if credentials file exists
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not os.path.exists(creds_path):
        print(f"❌ Google credentials file not found: {creds_path}")
        print("💡 Please ensure the file exists and path is correct.")
        return False
    
    return True

def main():
    """Main startup function."""
    print("🤖 Starting Checky Multimodal Assistant...")
    
    # Load environment variables from .env file if it exists
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print(f"✅ Loaded environment from {env_file}")
    else:
        print("ℹ️  No .env file found, using system environment variables")
    
    # Check environment configuration
    if not check_environment():
        sys.exit(1)
    
    print("✅ Environment configuration validated")
    
    # Set up logging
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Get configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    print(f"🚀 Starting server at http://{host}:{port}")
    print(f"👨‍👩‍👧‍👦 Parent interface: http://{host}:{port}/parent.html")
    print(f"🤖 Child interface: http://{host}:{port}/")
    
    # Import and run the application
    try:
        import uvicorn
        from checky.web_app import app
        
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=debug,
            log_level=log_level.lower(),
        )
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Please install required dependencies:")
        print("   pip install -r requirements-checky.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()