"""
Checky multimodal assistant for children.

A child-friendly conversational AI assistant built on pipecat with German language support.
"""

from .pipeline import CheckyPipeline, scrub_pii

__all__ = ["CheckyPipeline", "scrub_pii"]