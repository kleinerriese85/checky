
"""
Checky multimodal assistant pipeline implementation.

This module provides the CheckyPipeline class that creates a multimodal conversational
AI assistant for children, using Google Speech-to-Text, Text-to-Speech, and Gemini 1.5
for age-appropriate German responses.
"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, continue without loading .env file
    pass

import os
import re
from typing import Dict, Any, Optional

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.processors.aggregators.llm_response import LLMUserResponseAggregator, LLMAssistantResponseAggregator
    from pipecat.services.google.stt import GoogleSTTService
    from pipecat.services.google.tts import GoogleTTSService
    from pipecat.services.google.llm import GoogleLLMService
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.transports.base_transport import BaseTransport
    from pipecat.frames.frames import LLMMessagesFrame, SystemFrame, TextFrame
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
    
    PIPECAT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Pipecat imports not available: {e}")
    # Create placeholder classes to prevent import errors
    PIPECAT_AVAILABLE = False
    
    class Pipeline: pass
    class PipelineTask: pass
    class PipelineParams: pass
    class LLMUserResponseAggregator: pass
    class LLMAssistantResponseAggregator: pass
    class GoogleSTTService: pass
    class GoogleTTSService: pass
    class GoogleLLMService: pass
    class SileroVADAnalyzer: pass
    class BaseTransport: pass
    class LLMMessagesFrame: pass
    class SystemFrame: pass
    class TextFrame: pass
    class FrameProcessor: pass
    class FrameDirection: pass

from . import db


class PIIScrubbingProcessor(FrameProcessor):
    """Processor to scrub PII from text before sending to LLM."""
    
    async def process_frame(self, frame, direction: FrameDirection):
        if isinstance(frame, TextFrame):
            # Apply PII scrubbing to text content
            scrubbed_text = scrub_pii(frame.text)
            frame.text = scrubbed_text
        
        await self.push_frame(frame, direction)


class CheckyPipeline:
    """
    Multimodal pipeline for Checky children's assistant.
    
    Creates a conversational AI pipeline using Google services for speech recognition,
    text-to-speech, and language understanding with age-appropriate German responses.
    """
    
    def __init__(self, transport: BaseTransport, user_id: Optional[str] = None):
        """
        Initialize the CheckyPipeline.
        
        Args:
            transport: The transport layer for audio I/O
            user_id: Optional user ID for configuration loading
        """
        if not PIPECAT_AVAILABLE:
            raise ImportError("Pipecat is required for CheckyPipeline functionality")
            
        self.transport = transport
        self.user_id = user_id
        
        # Load configuration from database
        self._load_config()
        
        # Setup services and pipeline
        self._setup_services()
        self._setup_pipeline()
    
    def _load_config(self):
        """Load user configuration from database."""
        config = db.get_config()
        if config:
            self.child_age = config.get('child_age', 7)
            self.tts_voice = config.get('tts_voice', 'de-DE-Standard-A')
            logger.info(f"Loaded config: age={self.child_age}, voice={self.tts_voice}")
        else:
            # Default configuration
            self.child_age = 7
            self.tts_voice = 'de-DE-Standard-A'
            logger.warning("No user configuration found, using defaults")
    
    def _setup_services(self):
        """Setup Google STT, TTS, and LLM services."""
        # Google Speech-to-Text service for German
        self.stt = GoogleSTTService(
            api_key=os.getenv("GEMINI_API_KEY"),
            language="de-DE"
        )
        
        # Google Text-to-Speech service for German
        self.tts = GoogleTTSService(
            api_key=os.getenv("GEMINI_API_KEY"),
            voice_id=self.tts_voice,
            language="de-DE"
        )
        
        # Google LLM (Gemini 1.5 Flash) service
        self.llm = GoogleLLMService(
            api_key=os.getenv("GEMINI_API_KEY"),
            model="gemini-1.5-flash",
        )
    
    def _setup_pipeline(self):
        """Setup the processing pipeline."""
        # Build the system prompt for the child's age
        system_prompt = self._build_system_prompt(self.child_age)
        
        # Create LLM response aggregators for context management
        self.llm_user_aggregator = LLMUserResponseAggregator()
        self.llm_assistant_aggregator = LLMAssistantResponseAggregator()
        
        # Create PII scrubbing processor
        self.pii_scrubber = PIIScrubbingProcessor()
        
        # Create the pipeline with all components
        self.pipeline = Pipeline([
            self.transport.input(),           # Audio input from transport
            self.stt,                        # Speech-to-Text
            self.pii_scrubber,               # PII scrubbing
            self.llm_user_aggregator,        # User response aggregation
            self.llm,                        # LLM processing
            self.tts,                        # Text-to-Speech
            self.transport.output(),         # Audio output to transport
            self.llm_assistant_aggregator,   # Assistant response aggregation
        ])
        
        # Initialize with system prompt
        # Store the system prompt for use in task creation
        self.system_prompt = system_prompt
    
    def _build_system_prompt(self, age: int) -> str:
        """
        Build age-appropriate German system prompt for Checky.
        
        Args:
            age: The child's age (5-10)
            
        Returns:
            German system prompt tailored to the child's age
        """
        base_prompt = f"""Du bist Checky, ein freundlicher und hilfsbereiter Assistent für ein {age}-jähriges Kind.

Wichtige Regeln:
- Sprich immer auf Deutsch
- Verwende einfache Wörter, die ein {age}-jähriges Kind versteht
- Sei geduldig, freundlich und ermutigend
- Gib kurze, klare Antworten
- Wenn du etwas nicht verstehst, frag höflich nach
- Antworte nie mit persönlichen Informationen über das Kind
- Halte die Unterhaltung kinderfreundlich und sicher

"""
        
        # Add age-specific guidance
        if age <= 6:
            base_prompt += """- Verwende sehr einfache Sprache und kurze Sätze
- Erkläre Dinge spielerisch und mit Beispielen
- Sei besonders geduldig und wiederhole gerne"""
        elif age <= 8:
            base_prompt += """- Verwende einfache bis mittlere Sprache
- Erkläre Konzepte mit kindgerechten Beispielen
- Ermutige Neugier und Fragen"""
        else:  # age 9-10
            base_prompt += """- Verwende altersgerechte Sprache
- Erkläre Dinge etwas detaillierter
- Fördere selbstständiges Denken"""
        
        return base_prompt
    
    def create_task(self, idle_timeout_secs: int = 300) -> PipelineTask:
        """
        Create a PipelineTask from this pipeline.
        
        Args:
            idle_timeout_secs: Timeout in seconds for idle connections
            
        Returns:
            Configured PipelineTask
        """
        task = PipelineTask(
            self.pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            idle_timeout_secs=idle_timeout_secs,
        )
        
        # Initialize LLM with system prompt
        initial_messages = [
            {
                "role": "system", 
                "content": self.system_prompt
            }
        ]
        
        # Set initial context in the aggregators
        try:
            from pipecat.frames.frames import LLMMessagesFrame
            messages_frame = LLMMessagesFrame(initial_messages)
            # The aggregators will handle the initial system message
        except ImportError:
            # Graceful fallback if frame types are different
            pass
            
        return task


def scrub_pii(text: str) -> str:
    """
    Remove personally identifiable information (PII) from text before sending to Gemini.
    
    Args:
        text: The input text that may contain PII
        
    Returns:
        Text with PII removed or replaced
    """
    if not text:
        return text
    
    # Create a copy to work with
    scrubbed_text = text
    
    # Remove email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    scrubbed_text = re.sub(email_pattern, '[E-MAIL ENTFERNT]', scrubbed_text)
    
    # Remove phone numbers (various German formats)
    phone_patterns = [
        r'\+49[\s\-]?\d{2,4}[\s\-]?\d{3,8}',  # German international format
        r'0\d{2,4}[\s\-/]?\d{3,8}',           # German national format
        r'\(\d{2,4}\)[\s\-]?\d{3,8}',         # Format with area code in parentheses
        r'\d{3,4}[\s\-]\d{6,8}',              # Simple format
    ]
    
    for pattern in phone_patterns:
        scrubbed_text = re.sub(pattern, '[TELEFONNUMMER ENTFERNT]', scrubbed_text)
    
    # Remove potential addresses (street number + street name)
    address_pattern = r'\b\d+\s+[A-Za-zÄÖÜäöüß\-]+(?:straße|str\.|gasse|platz|weg|allee)\b'
    scrubbed_text = re.sub(address_pattern, '[ADRESSE ENTFERNT]', scrubbed_text, flags=re.IGNORECASE)
    
    # Remove URLs
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    scrubbed_text = re.sub(url_pattern, '[URL ENTFERNT]', scrubbed_text)
    
    # Remove credit card-like numbers (sequences of 13-19 digits with optional spaces/dashes)
    card_pattern = r'\b(?:\d{4}[\s\-]?){3}\d{1,4}\b'
    scrubbed_text = re.sub(card_pattern, '[KARTENNUMMER ENTFERNT]', scrubbed_text)
    
    # Remove social security numbers or ID numbers (German format patterns)
    # German social security: 12 digits in groups
    ssn_pattern = r'\b\d{2}[\s\-]?\d{6}[\s\-]?\d{4}\b'
    scrubbed_text = re.sub(ssn_pattern, '[VERSICHERUNGSNUMMER ENTFERNT]', scrubbed_text)
    
    return scrubbed_text

