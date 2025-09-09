"""
Checky multimodal assistant for children.

A stable, child-friendly conversational AI assistant built on pipecat 
following strict pipecat standards for maximum stability and compatibility.
"""

import logging

__version__ = "2.0.0"
__author__ = "Checky Development Team"

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from .pipeline import CheckyPipeline, scrub_pii
    from .web_app import app
    from . import db
    
    __all__ = [
        "CheckyPipeline",
        "scrub_pii", 
        "app",
        "db"
    ]
    
    logger.info("Checky components loaded successfully")
    
except ImportError as e:
    logger.warning(f"Some Checky components not available: {e}")
    __all__ = []