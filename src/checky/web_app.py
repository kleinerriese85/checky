"""
FastAPI web application for Checky multimodal assistant.

Minimal FastAPI app that acts as a 'gatekeeper' - accepting WebSocket connections
and immediately delegating all processing to CheckyPipeline. Follows pipecat standards.
"""

import os
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from . import db
from .pipeline import CheckyPipeline

# Configuration
DEBUG_MODE = os.getenv('DEBUG', 'false').lower() == 'true'

# Create minimal FastAPI app
app = FastAPI(
    title="Checky Assistant",
    description="Child-friendly voice assistant",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for REST API
class OnboardRequest(BaseModel):
    age: int = Field(..., ge=5, le=10)
    pin: str = Field(..., min_length=4, max_length=4)
    tts_voice: str = Field(default="de-DE-Standard-C")
    
    @validator('pin')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('PIN must be 4 digits')
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

class SuccessResponse(BaseModel):
    success: bool = True
    message: str

# REST API endpoints for parent area
@app.post("/onboard", response_model=SuccessResponse)
async def onboard_user(data: OnboardRequest):
    """Onboard new user."""
    success = db.create_user(data.age, data.pin, data.tts_voice)
    if not success:
        raise HTTPException(status_code=400, detail="User already exists")
    return SuccessResponse(message="User onboarded successfully")

@app.post("/parent/login", response_model=SuccessResponse)  
async def parent_login(data: LoginRequest):
    """Parent authentication."""
    if not db.authenticate_pin(data.pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    return SuccessResponse(message="Authentication successful")

@app.put("/parent/settings", response_model=SuccessResponse)
async def update_settings(data: UpdateSettingsRequest):
    """Update user settings."""
    if not db.authenticate_pin(data.pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    success = db.update_config(age=data.age, tts_voice=data.tts_voice)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update settings")
    
    return SuccessResponse(message="Settings updated")

@app.get("/config")
async def get_config():
    """Get configuration (without sensitive data)."""
    config = db.get_config()
    if not config:
        raise HTTPException(status_code=404, detail="No configuration found")
    return {k: v for k, v in config.items() if k != 'pin_hash'}

@app.get("/health")
async def health_check():
    """Health check."""
    return {"status": "healthy"}

# WebSocket endpoint for voice chat - minimal gatekeeper
@app.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """
    Minimal WebSocket endpoint that acts as a gatekeeper.
    Accepts connection and immediately delegates to CheckyPipeline.
    """
    try:
        await websocket.accept()
        logger.info("WebSocket client connected")
        
        # Create and run pipeline - delegate all processing
        pipeline = CheckyPipeline(websocket)
        await pipeline.run()
        
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011)
        except:
            pass

# Global error handler
@app.exception_handler(Exception)
async def handle_exception(request, exc):
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
        host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', '8000')),
        reload=DEBUG_MODE
    )