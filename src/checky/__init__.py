"""
Checky multimodal assistant for children.

A child-friendly conversational AI assistant built on pipecat with German language support.
"""

__version__ = "1.0.0"
__author__ = "Checky Development Team"

from .pipeline import CheckyPipeline, scrub_pii
from .web_app import app

__all__ = ["CheckyPipeline", "scrub_pii", "app"]

