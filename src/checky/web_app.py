"""
FastAPI web application for Checky multimodal assistant.

Provides REST API endpoints for onboarding and parent settings management,
plus WebSocket endpoint for real-time audio chat with the CheckyPipeline.
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from pipecat.pipeline.runner import PipelineRunner
from pipecat.runner.types import RunnerArguments
from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketTransport, FastAPIWebsocketParams
from pipecat.audio.vad.silero import SileroVADAnalyzer

from . import db
from .pipeline import CheckyPipeline


# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Global variables for pipeline management
active_connections: Dict[str, Dict[str, Any]] = {}


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
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Add CORS middleware
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
    return {"status": "healthy", "service": "checky"}


# WebSocket endpoint for voice chat
@app.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice chat with Checky.
    
    Handles audio input/output streaming through the CheckyPipeline.
    """
    await websocket.accept()
    client_id = f"client_{id(websocket)}"
    
    try:
        logger.info(f"WebSocket client connected: {client_id}")
        
        # Get user configuration
        config = db.get_config()
        if not config:
            await websocket.send_text('{"error": "No configuration found. Please onboard first."}')
            await websocket.close()
            return
        
        # Create transport for this WebSocket connection
        transport_params = FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=True,
            vad_analyzer=SileroVADAnalyzer(),
        )
        
        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=transport_params,
        )
        
        # Create CheckyPipeline with user configuration
        pipeline = CheckyPipeline(transport=transport, config=config)
        task = pipeline.create_task(idle_timeout_secs=300)
        
        # Store connection info
        active_connections[client_id] = {
            "websocket": websocket,
            "transport": transport,
            "pipeline": pipeline,
            "task": task,
            "config": config,
        }
        
        # Set up event handlers
        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info(f"Pipeline client connected: {client_id}")
            # Send welcome message in German
            from pipecat.frames.frames import LLMRunFrame
            await task.queue_frames([LLMRunFrame()])
        
        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info(f"Pipeline client disconnected: {client_id}")
            await task.cancel()
        
        # Run the pipeline
        runner = PipelineRunner()
        await runner.run(task)
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        try:
            await websocket.send_text(f'{{"error": "Connection error: {str(e)}"}}')
        except:
            pass
    finally:
        # Clean up connection
        if client_id in active_connections:
            try:
                connection_info = active_connections[client_id]
                if "task" in connection_info:
                    await connection_info["task"].cancel()
            except Exception as e:
                logger.error(f"Error during cleanup for {client_id}: {e}")
            finally:
                del active_connections[client_id]
        
        logger.info(f"Cleaned up connection: {client_id}")


# Mount static files for frontend (if public directory exists)
if os.path.exists("public"):
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
        "src.checky.web_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )