
"""
FastAPI web application for Checky multimodal assistant.

Minimal FastAPI app that only handles REST endpoints and WebSocket connections.
All business logic is delegated to the pipeline module.
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field, validator
    FASTAPI_AVAILABLE = True
except ImportError:
    logger.error("FastAPI and Pydantic are required")
    FASTAPI_AVAILABLE = False
    raise ImportError("FastAPI and Pydantic are required for the web application")

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

from . import db
from .pipeline import create_checky_bot

# Configuration
DEBUG_MODE = os.getenv('DEBUG', 'false').lower() == 'true'
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Checky application")
    yield
    logger.info("Shutting down Checky application")


# Create minimal FastAPI app
app = FastAPI(
    title="Checky Assistant",
    description="Child-friendly voice assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# Add middleware
app.state.limiter = limiter
if SLOWAPI_AVAILABLE:
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log requests for monitoring."""
    start_time = time.time()
    logger.info(f"{request.method} {request.url}")
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} ({process_time:.3f}s)")
    return response


# Pydantic models
class OnboardRequest(BaseModel):
    age: int = Field(..., ge=5, le=10)
    pin: str = Field(..., min_length=4, max_length=4)
    tts_voice: str = Field(default="de-DE-Standard-C")
    
    @validator('pin')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('PIN must be 4 digits')
        return v
    
    @validator('tts_voice')
    def validate_tts_voice(cls, v):
        supported_voices = {'de-DE-Standard-C', 'de-DE-Standard-D'}
        if v not in supported_voices:
            raise ValueError(f'Voice must be one of: {", ".join(sorted(supported_voices))}')
        return v


class LoginRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=4)
    
    @validator('pin')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('PIN must be 4 digits')
        return v


class UpdateSettingsRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=4)
    age: Optional[int] = Field(None, ge=5, le=10)
    tts_voice: Optional[str] = None
    
    @validator('pin')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('PIN must be 4 digits')
        return v
    
    @validator('tts_voice')
    def validate_tts_voice(cls, v):
        if v is not None:
            supported_voices = {'de-DE-Standard-C', 'de-DE-Standard-D'}
            if v not in supported_voices:
                raise ValueError(f'Voice must be one of: {", ".join(sorted(supported_voices))}')
        return v


class SuccessResponse(BaseModel):
    success: bool = True
    message: str


# REST API endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Checky API",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/onboard", response_model=SuccessResponse)
@limiter.limit("10/minute")
async def onboard_user(request: Request, data: OnboardRequest):
    """Onboard new user."""
    try:
        success = db.create_user(data.age, data.pin, data.tts_voice)
        if not success:
            raise HTTPException(status_code=400, detail="User already exists")
        
        logger.info(f"User onboarded: age={data.age}")
        return SuccessResponse(message="User onboarded successfully")
    except Exception as e:
        logger.error(f"Onboarding failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/parent/login", response_model=SuccessResponse)
@limiter.limit("10/minute")
async def parent_login(request: Request, data: LoginRequest):
    """Parent authentication."""
    try:
        if not db.authenticate_pin(data.pin):
            raise HTTPException(status_code=401, detail="Invalid PIN")
        return SuccessResponse(message="Authentication successful")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/parent/settings", response_model=SuccessResponse)
@limiter.limit("10/minute")
async def update_settings(request: Request, data: UpdateSettingsRequest):
    """Update user settings."""
    try:
        if not db.authenticate_pin(data.pin):
            raise HTTPException(status_code=401, detail="Invalid PIN")
        
        success = db.update_config(age=data.age, tts_voice=data.tts_voice)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update settings")
        
        return SuccessResponse(message="Settings updated")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Settings update failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/config")
async def get_config():
    """Get configuration (without sensitive data)."""
    try:
        config = db.get_config()
        if not config:
            raise HTTPException(status_code=404, detail="No configuration found")
        return {k: v for k, v in config.items() if k != 'pin_hash'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Config retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """Health check."""
    return {"status": "healthy"}


# WebSocket endpoint for voice chat
@app.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """Minimal WebSocket endpoint that delegates to pipeline."""
    try:
        await websocket.accept()
        logger.info("WebSocket client connected")
        
        # Delegate all processing to pipeline
        await create_checky_bot(websocket)
        
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011)
        except:
            pass

# Mount static files if available
if os.path.exists("public"):
    app.mount("/", StaticFiles(directory="public", html=True), name="static")


# Global error handler
@app.exception_handler(Exception)
async def handle_exception(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        reload=DEBUG_MODE
    )
