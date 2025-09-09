
"""
Checky multimodal assistant pipeline implementation.

Minimal, standards-compliant pipecat pipeline following official examples.
Uses built-in pipecat components for maximum stability and compatibility.
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os
import re
from typing import Optional

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.services.google.stt import GoogleSTTService
    from pipecat.services.google.tts import GoogleTTSService
    from pipecat.services.google.llm import GoogleLLMService
    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
    from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketTransport, FastAPIWebsocketParams
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.frames.frames import TextFrame, LLMRunFrame
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
    PIPECAT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Pipecat not available: {e}")
    PIPECAT_AVAILABLE = False
    
    # Placeholder classes for graceful degradation
    class Pipeline: pass
    class FrameProcessor: pass
    class FrameDirection: pass

from . import db


class PIIScrubbingProcessor(FrameProcessor):
    """Minimal PII scrubbing processor following pipecat patterns."""
    
    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        
        if isinstance(frame, TextFrame) and direction == FrameDirection.DOWNSTREAM:
            scrubbed_text = scrub_pii(frame.text)
            frame.text = scrubbed_text
        
        await self.push_frame(frame, direction)


async def create_checky_bot(websocket):
    """
    Create Checky bot following standard pipecat patterns.
    
    Based on the official pipecat examples with minimal customization.
    This function follows the exact pattern from examples/foundational/07-interruptible.py
    """
    if not PIPECAT_AVAILABLE:
        raise ImportError("Pipecat is required for voice chat functionality")
        
    logger.info("Starting Checky bot initialization")
    
    # Load configuration from database
    config = db.get_config()
    if not config:
        raise ValueError("Please complete onboarding first")
    
    child_age = config.get('child_age', 7)
    tts_voice = config.get('tts_voice', 'de-DE-Standard-A')
    
    # Verify API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    
    # Create transport exactly like pipecat examples
    transport_params = FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=True,
        vad_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
    )
    transport = FastAPIWebsocketTransport(websocket, transport_params)
    
    # Initialize services like in pipecat examples
    stt = GoogleSTTService(api_key=api_key)
    tts = GoogleTTSService(api_key=api_key, voice_id=tts_voice)
    llm = GoogleLLMService(api_key=api_key, model="gemini-1.5-flash")
    
    # Build age-appropriate system prompt
    system_prompt = build_system_prompt(child_age)
    
    # Create context exactly like pipecat examples
    messages = [{"role": "system", "content": system_prompt}]
    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)
    
    # Create PII scrubbing processor
    pii_scrubber = PIIScrubbingProcessor()
    
    # Create pipeline exactly like pipecat examples
    pipeline = Pipeline([
        transport.input(),
        stt,
        pii_scrubber,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant(),
    ])
    
    # Create task exactly like pipecat examples
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=300,
    )
    
    # Add event handler for client connection (from pipecat examples)
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected to Checky")
        messages.append({"role": "system", "content": "Begrüße das Kind freundlich auf Deutsch."})
        await task.queue_frames([LLMRunFrame()])
    
    # Run pipeline exactly like pipecat examples
    runner = PipelineRunner()
    await runner.run(task)


def build_system_prompt(age: int) -> str:
    """
    Build age-appropriate German system prompt for Checky.
    """
    base_prompt = f"""Du bist Checky, ein freundlicher Assistent für ein {age}-jähriges Kind.

Regeln:
- Sprich immer auf Deutsch
- Verwende einfache Wörter für ein {age}-jähriges Kind
- Sei freundlich und geduldig
- Gib kurze, klare Antworten
- Halte die Unterhaltung kinderfreundlich
- Keine persönlichen Informationen über das Kind verwenden
"""
    
    if age <= 6:
        base_prompt += "- Verwende sehr einfache Sprache und kurze Sätze"
    elif age <= 8:
        base_prompt += "- Erkläre Konzepte mit einfachen Beispielen"
    else:
        base_prompt += "- Fördere selbstständiges Denken mit altersgerechter Sprache"
    
    return base_prompt


def scrub_pii(text: str) -> str:
    """
    Minimal PII scrubbing for child safety.
    """
    if not text:
        return text
    
    scrubbed = text
    
    # Remove email addresses
    scrubbed = re.sub(r'\b[\w.-]+@[\w.-]+\.\w+\b', '[E-MAIL ENTFERNT]', scrubbed)
    
    # Remove phone numbers
    scrubbed = re.sub(r'\b\d{3,4}[\s\-/]?\d{3,8}\b', '[TELEFON ENTFERNT]', scrubbed)
    
    # Remove URLs
    scrubbed = re.sub(r'https?://\S+', '[URL ENTFERNT]', scrubbed)
    
    return scrubbed


# Legacy compatibility class for existing code
class CheckyPipeline:
    """Legacy compatibility wrapper - use create_checky_bot instead."""
    
    def __init__(self, websocket, user_id: Optional[str] = None):
        self.websocket = websocket
        self.user_id = user_id
    
    async def run(self):
        """Run pipeline using new standardized approach."""
        await create_checky_bot(self.websocket)

