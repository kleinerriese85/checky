"""
Checky multimodal assistant pipeline implementation.

Contains ALL speech processing logic using standard pipecat components.
Follows pipecat standards exactly - minimal custom code, maximum stability.
"""

import os
import re
from typing import Optional

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

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

from . import db


class PIIScrubbingProcessor(FrameProcessor):
    """Minimal PII scrubbing processor following pipecat patterns."""
    
    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        
        if isinstance(frame, TextFrame) and direction == FrameDirection.DOWNSTREAM:
            scrubbed_text = scrub_pii(frame.text)
            frame.text = scrubbed_text
        
        await self.push_frame(frame, direction)


class CheckyPipeline:
    """
    Core CheckyPipeline class containing ALL speech processing logic.
    
    Follows pipecat standards exactly:
    - Loads configuration from database during initialization
    - Creates age-appropriate system prompt
    - Uses only standard pipecat components in linear pipeline
    - Handles WebSocket lifecycle properly
    """
    
    def __init__(self, websocket):
        """Initialize CheckyPipeline with WebSocket connection."""
        self.websocket = websocket
        self.config = None
        self.pipeline = None
        self.task = None
        self.runner = None
        
    async def run(self):
        """
        Run the pipeline following standard pipecat patterns.
        Based exactly on pipecat examples/foundational/07-interruptible.py
        """
        logger.info("Starting CheckyPipeline")
        
        # 1. Load configuration from database
        self.config = db.get_config()
        if not self.config:
            raise ValueError("Please complete onboarding first")
        
        child_age = self.config.get('child_age', 7)
        tts_voice = self.config.get('tts_voice', 'de-DE-Standard-C')
        
        # 2. Verify API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        
        # 3. Create transport exactly like pipecat examples
        transport_params = FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        )
        transport = FastAPIWebsocketTransport(self.websocket, transport_params)
        
        # 4. Initialize services like in pipecat examples
        stt = GoogleSTTService(api_key=api_key, language="de-DE")
        tts = GoogleTTSService(api_key=api_key, voice_id=tts_voice)
        llm = GoogleLLMService(api_key=api_key, model="gemini-1.5-flash")
        
        # 5. Build age-appropriate system prompt
        system_prompt = self._build_system_prompt(child_age)
        
        # 6. Create context exactly like pipecat examples
        messages = [{"role": "system", "content": system_prompt}]
        context = OpenAILLMContext(messages)
        context_aggregator = llm.create_context_aggregator(context)
        
        # 7. Create PII scrubbing processor
        pii_scrubber = PIIScrubbingProcessor()
        
        # 8. Create pipeline exactly like pipecat examples - linear list
        self.pipeline = Pipeline([
            transport.input(),
            stt,
            pii_scrubber,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ])
        
        # 9. Create task exactly like pipecat examples
        self.task = PipelineTask(
            self.pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            idle_timeout_secs=300,
        )
        
        # 10. Add event handlers following pipecat patterns
        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info("Client connected to Checky")
            messages.append({
                "role": "system", 
                "content": "Begrüße das Kind freundlich auf Deutsch."
            })
            await self.task.queue_frames([LLMRunFrame()])
        
        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            logger.info("Client disconnected from Checky")
            await self.task.cancel()
        
        # 11. Run pipeline exactly like pipecat examples
        self.runner = PipelineRunner()
        await self.runner.run(self.task)
        
    def _build_system_prompt(self, age: int) -> str:
        """Build age-appropriate German system prompt for Checky."""
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
    """Minimal PII scrubbing for child safety."""
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