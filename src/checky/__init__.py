"""
Checky multimodal assistant for children.

A child-friendly conversational AI assistant built on pipecat with German language support.
Follows pipecat best practices for maximum stability and compatibility.
"""

import logging

__version__ = "1.0.0"
__author__ = "Checky Development Team"

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import components with graceful degradation
try:
    from .pipeline import create_checky_bot, CheckyPipeline, scrub_pii
    from .web_app import app
    from . import db
    
    __all__ = [
        "create_checky_bot",
        "CheckyPipeline",  # Legacy compatibility
        "scrub_pii",
        "app",
        "db"
    ]
    logger.info("Checky components loaded successfully")
    
except ImportError as e:
    logger.warning(f"Some Checky components not available: {e}")
    __all__ = []

