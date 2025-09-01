"""

Checky - A lightweight, API-driven service for validation and monitoring.

This package provides the core functionality for the checky application,
including pipeline processing and web API endpoints.
"""

__version__ = "1.0.0"
__author__ = "Checky Development Team"

from .pipeline import Pipeline
from .web_app import app

__all__ = ["Pipeline", "app"]
=======
Checky multimodal assistant for children.

A child-friendly conversational AI assistant built on pipecat with German language support.
"""

from .pipeline import CheckyPipeline, scrub_pii

__all__ = ["CheckyPipeline", "scrub_pii"]

