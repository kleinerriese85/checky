from dotenv import load_dotenv
load_dotenv()

import os
import logging
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Checky API",
    description="A lightweight, API-driven service for validation and monitoring",
    version="1.0.0"
)

# Security scheme
security = HTTPBearer()

# Configuration from environment variables
API_KEY = os.getenv('API_KEY')
DEBUG_MODE = os.getenv('DEBUG', 'false').lower() == 'true'
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))

if not API_KEY:
    logger.warning("API_KEY environment variable not set - authentication will fail")


class CheckRequest(BaseModel):
    """Request model for check endpoints."""
    data: Dict[str, Any]
    rules: Optional[List[str]] = None


class CheckResponse(BaseModel):
    """Response model for check endpoints."""
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None


def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Verify the API key from the Authorization header.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        The verified API key
        
    Raises:
        HTTPException: If API key is invalid
    """
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: API key not configured"
        )
    
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return credentials.credentials


@app.get("/")
async def root():
    """Root endpoint returning basic API information."""
    return {
        "name": "Checky API",
        "version": "1.0.0",
        "status": "running",
        "debug": DEBUG_MODE,
        "api_key_configured": bool(API_KEY)
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "api_key_present": bool(API_KEY),
        "debug_mode": DEBUG_MODE
    }


@app.post("/v1/check", response_model=CheckResponse)
async def check_data(
    request: CheckRequest,
    api_key: str = Depends(verify_api_key)
) -> CheckResponse:
    """
    Main endpoint for data validation checks.
    
    Args:
        request: The check request containing data and optional rules
        api_key: Verified API key from authorization header
        
    Returns:
        Check response with validation results
    """
    logger.info(f"Processing check request with {len(request.data)} data fields")
    
    try:
        # Placeholder validation logic
        # In a real implementation, this would run the actual validation rules
        
        # Simulate some basic validation
        if not request.data:
            return CheckResponse(
                status="fail",
                message="No data provided for validation"
            )
        
        # Check for required fields (example)
        required_fields = ["id", "name"]  # Example required fields
        missing_fields = [field for field in required_fields if field not in request.data]
        
        if missing_fields:
            return CheckResponse(
                status="fail",
                message=f"Missing required fields: {', '.join(missing_fields)}",
                details={"missing_fields": missing_fields}
            )
        
        # If all checks pass
        logger.info("Validation checks passed")
        return CheckResponse(
            status="pass",
            message="All validation checks passed",
            details={
                "validated_fields": list(request.data.keys()),
                "rules_applied": request.rules or ["default"],
                "api_key_used": api_key[:8] + "..." if api_key else None
            }
        )
        
    except Exception as e:
        logger.error(f"Check processing failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/v1/status/{check_id}")
async def get_check_status(
    check_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get the status of a previous check by ID.
    
    Args:
        check_id: The ID of the check to retrieve
        api_key: Verified API key from authorization header
        
    Returns:
        Status information for the specified check
    """
    # Placeholder implementation
    # In a real system, this would query a database or cache
    return {
        "check_id": check_id,
        "status": "completed",
        "message": "Check status retrieval not fully implemented",
        "api_key_authenticated": True
    }


def validate_startup_config():
    """Validate configuration at startup."""
    if not API_KEY:
        logger.error("CRITICAL: API_KEY environment variable not configured!")
        return False
    
    logger.info("Startup configuration validation passed")
    return True


if __name__ == "__main__":
    # Validate configuration before starting
    if validate_startup_config():
        logger.info(f"Starting Checky web application on {HOST}:{PORT}")
        logger.info(f"Debug mode: {'enabled' if DEBUG_MODE else 'disabled'}")
        
        uvicorn.run(
            app,
            host=HOST,
            port=PORT,
            debug=DEBUG_MODE,
            log_level="debug" if DEBUG_MODE else "info"
        )
    else:
        logger.error("Startup validation failed. Please check your environment configuration.")
        exit(1)