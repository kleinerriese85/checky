"""
Checky multimodal assistant for children.

A child-friendly conversational AI assistant built on pipecat with German language support.
"""

__version__ = "1.0.0"
__author__ = "Checky Development Team"

# Import main components that are actually used
try:
    from .pipeline import CheckyPipeline, PIIScrubbingProcessor, scrub_pii
    from .web_app import app
    from . import db
    
    __all__ = [
        "CheckyPipeline", 
        "PIIScrubbingProcessor",
        "scrub_pii", 
        "app", 
        "db"
    ]
    
except ImportError as e:
    # Graceful degradation if dependencies are missing
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Some Checky components not available: {e}")
    
    __all__ = []

