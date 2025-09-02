
"""
FastAPI web application for Checky multimodal assistant.

Provides REST API endpoints for onboarding and parent settings management,
plus WebSocket endpoint for real-time audio chat with the CheckyPipeline.
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, continue without loading .env file
    pass

import asyncio
import logging
import os
from typing import Dict, Any, Optional, List
import time
from contextlib import asynccontextmanager

# Initialize logger first
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends, Security
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    FASTAPI_AVAILABLE = True
except ImportError:
    logger.warning("FastAPI not available")
    FASTAPI_AVAILABLE = False
    
    # Create minimal app placeholder
    class _StateObject:
        def __setattr__(self, name, value): pass
        def __getattr__(self, name): return None
    
    class FastAPI: 
        def __init__(self, *args, **kwargs): 
            self.state = _StateObject()
        def get(self, *args, **kwargs): return lambda f: f
        def post(self, *args, **kwargs): return lambda f: f  
        def put(self, *args, **kwargs): return lambda f: f
        def websocket(self, *args, **kwargs): return lambda f: f
        def middleware(self, *args, **kwargs): return lambda f: f
        def add_middleware(self, *args, **kwargs): pass
        def add_exception_handler(self, *args, **kwargs): pass
        def exception_handler(self, *args, **kwargs): return lambda f: f
        def mount(self, *args, **kwargs): pass
    
    class WebSocket: pass
    class WebSocketDisconnect(Exception): pass
    class HTTPException(Exception): pass
    class Request: pass
    def Depends(*args, **kwargs): return lambda f: f
    def Security(*args, **kwargs): return lambda f: f
    class CORSMiddleware: pass
    class JSONResponse: pass
    class StaticFiles: pass
    class HTTPBearer: pass
    class HTTPAuthorizationCredentials: pass
try:
    from pydantic import BaseModel, Field, validator
except ImportError:
    logger.warning("Pydantic not available")
    
    class BaseModel: pass
    class Field: 
        def __init__(self, *args, **kwargs): pass
    def validator(*args, **kwargs): return lambda f: f
# Logger already initialized above
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    SLOWAPI_AVAILABLE = True
except ImportError:
    logger.warning("SlowAPI not available - rate limiting disabled")
    SLOWAPI_AVAILABLE = False
    
    class Limiter: 
        def __init__(self, *args, **kwargs): pass
        def limit(self, *args, **kwargs): return lambda f: f
    def _rate_limit_exceeded_handler(*args, **kwargs): pass
    def get_remote_address(*args, **kwargs): return "127.0.0.1"
    class RateLimitExceeded(Exception): pass
    class SlowAPIMiddleware: pass

try:
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.runner.types import RunnerArguments
    from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketTransport, FastAPIWebsocketParams
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    PIPECAT_AVAILABLE = True
except ImportError:
    logger.warning("Pipecat imports not available for web_app")
    PIPECAT_AVAILABLE = False
    
    class PipelineRunner: pass
    class RunnerArguments: pass
    class FastAPIWebsocketTransport: pass
    class FastAPIWebsocketParams: pass
    class SileroVADAnalyzer: pass

from . import db
from .pipeline import CheckyPipeline

# Security scheme
security = HTTPBearer()

# Configuration from environment variables
API_KEY = os.getenv('API_KEY')
DEBUG_MODE = os.getenv('DEBUG', 'false').lower() == 'true'
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))


# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Global variables for pipeline management
active_connections: Dict[str, Dict[str, Any]] = {}


# Request/Response models
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Checky application")
    yield
    logger.info("Shutting down Checky application")


# Create FastAPI app
app = FastAPI(
    title="Checky Multimodal Assistant",
    description="Child-friendly voice assistant with German language support",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiting middleware
app.state.limiter = limiter
if SLOWAPI_AVAILABLE:
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

# Add CORS middleware
if FASTAPI_AVAILABLE:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify actual domains
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Request/Response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log request received and response sent."""
    start_time = time.time()
    
    logger.info(f"request_received: {request.method} {request.url}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(f"response_sent: {response.status_code} - {process_time:.4f}s")
    
    return response


# Pydantic models for API requests/responses
class OnboardRequest(BaseModel):
    """Request model for user onboarding."""
    age: int = Field(..., ge=5, le=10, description="Child's age (5-10)")
    pin: str = Field(..., min_length=4, max_length=4, description="4-digit PIN")
    tts_voice: str = Field(default="de-DE-Standard-A", description="TTS voice ID")
    
    @validator('pin')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('PIN must contain only digits')
        return v


class LoginRequest(BaseModel):
    """Request model for parent login."""
    pin: str = Field(..., min_length=4, max_length=4, description="4-digit PIN")
    
    @validator('pin')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('PIN must contain only digits')
        return v


class UpdateSettingsRequest(BaseModel):
    """Request model for updating settings."""
    pin: str = Field(..., min_length=4, max_length=4, description="4-digit PIN for authentication")
    age: Optional[int] = Field(None, ge=5, le=10, description="New child's age (5-10)")
    tts_voice: Optional[str] = Field(None, description="New TTS voice ID")
    
    @validator('pin')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('PIN must contain only digits')
        return v


class SuccessResponse(BaseModel):
    """Standard success response."""
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: str


# API Endpoints

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


@app.post("/onboard", response_model=SuccessResponse)
@limiter.limit("10/minute")
async def onboard_user(request: Request, data: OnboardRequest):
    """
    Onboard a new user with child's age and parent PIN.
    
    Creates initial configuration in the database.
    """
    try:
        success = db.create_user(data.age, data.pin, data.tts_voice)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to create user. User may already exist."
            )
        
        logger.info(f"User onboarded successfully with age {data.age}")
        return SuccessResponse(message="User onboarded successfully")
    
    except Exception as e:
        logger.error(f"Onboarding failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/parent/login", response_model=SuccessResponse)
@limiter.limit("10/minute")
async def parent_login(request: Request, data: LoginRequest):
    """
    Authenticate parent with PIN.
    
    Returns success if PIN is correct.
    """
    try:
        if not db.authenticate_pin(data.pin):
            raise HTTPException(status_code=401, detail="Invalid PIN")
        
        logger.info("Parent authentication successful")
        return SuccessResponse(message="Authentication successful")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/parent/settings", response_model=SuccessResponse)
@limiter.limit("10/minute")
async def update_settings(request: Request, data: UpdateSettingsRequest):
    """
    Update user settings with PIN authentication.
    
    Allows updating child's age and/or TTS voice preference.
    """
    try:
        # Authenticate PIN first
        if not db.authenticate_pin(data.pin):
            raise HTTPException(status_code=401, detail="Invalid PIN")
        
        # Update settings
        success = db.update_config(age=data.age, tts_voice=data.tts_voice)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update settings")
        
        logger.info("Settings updated successfully")
        return SuccessResponse(message="Settings updated successfully")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Settings update failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/config")
async def get_config():
    """Get current configuration (without PIN)."""
    try:
        config = db.get_config()
        if not config:
            raise HTTPException(status_code=404, detail="No configuration found")
        
        # Remove sensitive data
        safe_config = {k: v for k, v in config.items() if k != 'pin_hash'}
        return safe_config
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Config retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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


# WebSocket endpoint for voice chat
@app.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice chat with Checky.
    
    Handles audio input/output streaming through the CheckyPipeline.
    """
    client_id = f"client_{id(websocket)}"
    
    try:
        # Accept WebSocket connection first
        await websocket.accept()
        logger.info(f"WebSocket client connected: {client_id}")
        
        # Check if pipecat is available
        if not PIPECAT_AVAILABLE:
            error_msg = '{"error": "Voice chat functionality not available. Missing pipecat dependency."}'
            await websocket.send_text(error_msg)
            await websocket.close(code=1011, reason="Missing dependencies")
            return
            
        # Get user configuration from database
        config = db.get_config()
        if not config:
            error_msg = '{"error": "No configuration found. Please onboard first."}'
            await websocket.send_text(error_msg)
            await websocket.close(code=1008, reason="No user configuration")
            return
        
        # Create transport parameters with VAD
        transport_params = FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
        )
        
        # Create transport for this WebSocket connection
        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=transport_params,
        )
        
        # Create CheckyPipeline instance
        pipeline = CheckyPipeline(transport=transport)
        task = pipeline.create_task(idle_timeout_secs=300)
        
        # Store connection info
        active_connections[client_id] = {
            "websocket": websocket,
            "transport": transport,
            "pipeline": pipeline,
            "task": task,
            "config": config,
        }
        
        # Set up event handlers for connection lifecycle
        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info(f"Pipeline transport connected for: {client_id}")
            try:
                # Send initial welcome message
                from pipecat.frames.frames import TextFrame
                welcome_text = f"Hallo! Ich bin Checky, dein Assistent. Wie kann ich dir heute helfen?"
                await task.queue_frame(TextFrame(welcome_text))
            except Exception as e:
                logger.error(f"Error sending welcome message: {e}")
        
        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info(f"Pipeline transport disconnected for: {client_id}")
            try:
                await task.cancel()
            except Exception as e:
                logger.error(f"Error canceling task on disconnect: {e}")
        
        # Start the pipeline task
        runner = PipelineRunner()
        await runner.run(task)
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}", exc_info=True)
        try:
            if websocket.client_state.name != "DISCONNECTED":
                error_msg = f'{{"error": "Connection error: {str(e)[:100]}"}}'
                await websocket.send_text(error_msg)
                await websocket.close(code=1011, reason="Internal error")
        except Exception as cleanup_error:
            logger.error(f"Error during error handling for {client_id}: {cleanup_error}")
    finally:
        # Clean up connection
        await _cleanup_connection(client_id)


async def _cleanup_connection(client_id: str):
    """Clean up connection resources."""
    if client_id in active_connections:
        try:
            connection_info = active_connections[client_id]
            
            # Cancel the pipeline task
            if "task" in connection_info:
                try:
                    await connection_info["task"].cancel()
                except Exception as e:
                    logger.error(f"Error canceling task during cleanup for {client_id}: {e}")
            
            # Clean up transport
            if "transport" in connection_info:
                try:
                    transport = connection_info["transport"]
                    # Any additional transport cleanup if needed
                except Exception as e:
                    logger.error(f"Error cleaning up transport for {client_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error during cleanup for {client_id}: {e}")
        finally:
            # Always remove from active connections
            del active_connections[client_id]
            logger.info(f"Cleaned up connection: {client_id}")
    else:
        logger.debug(f"Connection {client_id} not found in active connections for cleanup")


# Mount static files for frontend (if public directory exists)
if FASTAPI_AVAILABLE and os.path.exists("public"):
    app.mount("/", StaticFiles(directory="public", html=True), name="static")


# Error handlers
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    
    # Configure logging  
    logging.basicConfig(level=logging.INFO)
    
    # Run the application
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        reload=DEBUG_MODE,
        log_level="debug" if DEBUG_MODE else "info",
    )
