
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
    from pipecat.services.google.stt import GoogleSTTService
    from pipecat.services.google.tts import GoogleTTSService
    from pipecat.services.google.llm import GoogleLLMService
    from pipecat.transports.base_transport import BaseTransport
    from pipecat.frames.frames import TextFrame, ErrorFrame
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
    
    PIPECAT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Pipecat imports not available: {e}")
    # Create placeholder classes to prevent import errors
    PIPECAT_AVAILABLE = False
    
    class Pipeline: pass
    class PipelineTask: pass
    class PipelineParams: pass
    class GoogleSTTService: pass
    class GoogleTTSService: pass
    class GoogleLLMService: pass
    class BaseTransport: pass
    class TextFrame: pass
    class ErrorFrame: pass
    class FrameProcessor: pass
    class FrameDirection: pass

from . import db


class PIIScrubbingProcessor(FrameProcessor):
    """Pipecat-compliant processor to scrub PII from text before sending to LLM."""
    
    def __init__(self, **kwargs):
        """Initialize the PII scrubbing processor."""
        super().__init__(**kwargs)
    
    async def process_frame(self, frame, direction: FrameDirection):
        """Process frames with proper pipecat patterns."""
        # Always call parent first for proper pipeline integration
        await super().process_frame(frame, direction)
        
        try:
            # Only process text frames in downstream direction
            if isinstance(frame, TextFrame) and direction == FrameDirection.DOWNSTREAM:
                # Safely get text content with defensive programming
                text_content = getattr(frame, 'text', None)
                if text_content is None:
                    logger.warning("TextFrame missing 'text' attribute, passing through unchanged")
                    await self.push_frame(frame, direction)
                    return
                
                # Apply PII scrubbing to text content
                scrubbed_text = scrub_pii(text_content)
                
                # Create new frame with scrubbed content
                scrubbed_frame = TextFrame(text=scrubbed_text)
                
                # Safely preserve metadata if present
                if hasattr(frame, 'metadata') and frame.metadata is not None:
                    try:
                        scrubbed_frame.metadata = frame.metadata.copy()
                    except (AttributeError, TypeError) as meta_error:
                        logger.warning(f"Could not copy frame metadata: {meta_error}")
                
                await self.push_frame(scrubbed_frame, direction)
            else:
                # Pass through all other frames unchanged (SystemFrames, StartFrames, etc.)
                await self.push_frame(frame, direction)
                
        except KeyError as key_error:
            # Handle specific KeyError exceptions
            logger.error(f"KeyError in PIIScrubbingProcessor accessing frame data: {key_error}")
            await self.push_frame(frame, direction)  # Pass through original frame
        except Exception as e:
            # Proper error handling - don't crash the pipeline
            logger.error(f"Error in PIIScrubbingProcessor: {e}")
            try:
                from pipecat.frames.frames import ErrorFrame
                await self.push_error(ErrorFrame(str(e)))
            except Exception as error_handling_error:
                logger.critical(f"Failed to handle PII scrubbing error: {error_handling_error}")
                # As last resort, pass through the original frame
                await self.push_frame(frame, direction)


class CheckyPipeline:
    """
    Multimodal pipeline for Checky children's assistant.
    
    Creates a conversational AI pipeline using Google services for speech recognition,
    text-to-speech, and language understanding with age-appropriate German responses.
    """
    
    def __init__(self, websocket, user_id: Optional[str] = None):
        """
        Initialize the CheckyPipeline.
        
        Args:
            websocket: The WebSocket connection for audio I/O
            user_id: Optional user ID for configuration loading
        """
        if not PIPECAT_AVAILABLE:
            raise ImportError("Pipecat is required for CheckyPipeline functionality")
            
        self.websocket = websocket
        self.user_id = user_id
        self.transport = None
        self.pipeline = None
        self.task = None
        
        # Load configuration from database (moved from websocket handler)
        self._load_config()
        
        # Validate configuration and setup services
        self._validate_config()
        self._setup_services()
        self._setup_transport()
        self._setup_pipeline()
    
    def _load_config(self):
        """Load user configuration from database."""
        self.config = db.get_config()
        if self.config:
            self.child_age = self.config.get('child_age', 7)
            self.tts_voice = self.config.get('tts_voice', 'de-DE-Standard-A')
            logger.info(f"Loaded config: age={self.child_age}, voice={self.tts_voice}")
        else:
            # Default configuration
            self.config = None
            self.child_age = 7
            self.tts_voice = 'de-DE-Standard-A'
            logger.warning("No user configuration found, using defaults")
    
    def _validate_config(self):
        """Validate that required configuration is available."""
        if not self.config:
            raise ValueError("Please complete onboarding first")
            
        # Validate pipecat availability (moved from websocket handler)
        if not PIPECAT_AVAILABLE:
            raise ImportError("Voice chat not available - missing pipecat")
            
        # Validate required config keys with defaults
        self.child_age = self.config.get('child_age')
        if self.child_age is None:
            logger.warning("Missing child_age in config, using default of 7")
            self.child_age = 7
            
        self.tts_voice = self.config.get('tts_voice')
        if self.tts_voice is None:
            logger.warning("Missing tts_voice in config, using default")
            self.tts_voice = 'de-DE-Standard-A'
    
    def _setup_transport(self):
        """Setup the WebSocket transport with pipecat configuration."""
        try:
            from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketTransport, FastAPIWebsocketParams
            from pipecat.audio.vad.silero import SileroVADAnalyzer
            
            # Create transport with configuration from original websocket handler
            transport_params = FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=True,
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer(),
            )
            
            self.transport = FastAPIWebsocketTransport(self.websocket, transport_params)
            logger.info("WebSocket transport configured successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup transport: {e}")
            raise
    
    def _setup_services(self):
        """Setup Google STT, TTS, and LLM services with proper pipecat configuration."""
        try:
            # Verify API key is available
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable is required")
            
            # Google Speech-to-Text service for German
            self.stt = GoogleSTTService(
                api_key=api_key
                # Let pipecat handle language detection or set via params
            )
            
            # Google Text-to-Speech service for German
            self.tts = GoogleTTSService(
                api_key=api_key,
                voice_id=self.tts_voice
                # Language will be inferred from voice_id
            )
            
            # Google LLM (Gemini 1.5 Flash) service with system prompt
            self.llm = GoogleLLMService(
                api_key=api_key,
                model="gemini-1.5-flash"
            )
            
            logger.info("Google services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup Google services: {e}")
            raise
    
    def _setup_pipeline(self):
        """Setup the processing pipeline with minimal pipecat standard components."""
        try:
            # Build the age-appropriate system prompt
            system_prompt = self._build_system_prompt(self.child_age)
            
            # Create LLM context for system prompt initialization
            from pipecat.processors.aggregators.llm_response import OpenAILLMContext
            
            # Initialize context with system message
            initial_messages = [
                {
                    "role": "system", 
                    "content": system_prompt
                }
            ]
            self.context = OpenAILLMContext(messages=initial_messages)
            
            # Create context aggregator
            self.context_aggregator = self.llm.create_context_aggregator(self.context)
            
            # Create PII scrubbing processor
            self.pii_scrubber = PIIScrubbingProcessor()
            
            # Create the pipeline as simple list of processors
            # Flow: transport.input → STT → PII Scrubbing → Context User → LLM → TTS → transport.output → Context Assistant  
            self.pipeline = Pipeline([
                self.transport.input(),              # Audio input from transport
                self.stt,                           # Google Speech-to-Text
                self.pii_scrubber,                  # PII scrubbing (our custom processor)
                self.context_aggregator.user(),    # User context aggregation
                self.llm,                           # Google LLM (Gemini 1.5 Flash)
                self.tts,                           # Google Text-to-Speech
                self.transport.output(),            # Audio output to transport
                self.context_aggregator.assistant() # Assistant context aggregation
            ])
            
            logger.info("Pipeline setup completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup pipeline: {e}")
            raise
    
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
            Configured PipelineTask ready to run
        """
        try:
            self.task = PipelineTask(
                self.pipeline,
                params=PipelineParams(
                    enable_metrics=True,
                    enable_usage_metrics=True,
                ),
                idle_timeout_secs=idle_timeout_secs,
            )
            
            logger.info(f"PipelineTask created with {idle_timeout_secs}s timeout")
            return self.task
            
        except Exception as e:
            logger.error(f"Failed to create PipelineTask: {e}")
            raise
    
    async def run(self):
        """
        Run the complete message processing pipeline.
        
        This method handles the complete message processing lifecycle:
        1) Creates the pipeline task if not already created
        2) Runs the pipeline using PipelineRunner
        3) Handles WebSocket disconnections and errors gracefully
        """
        try:
            # Create task if not already created
            if not self.task:
                self.create_task(idle_timeout_secs=300)
            
            # Run the pipeline using pipecat's PipelineRunner
            from pipecat.pipeline.runner import PipelineRunner
            runner = PipelineRunner()
            
            logger.info("Starting pipeline execution")
            await runner.run(self.task)
            logger.info("Pipeline execution completed")
            
        except ValueError as ve:
            # Handle configuration errors (like missing onboarding)
            logger.error(f"Configuration error: {ve}")
            try:
                await self.websocket.send_text(f'{{"error": "{str(ve)}"}}')
                await self.websocket.close(code=1008)  # Policy violation
            except:
                pass
            raise
        except ImportError as ie:
            # Handle missing dependencies
            logger.error(f"Dependency error: {ie}")
            try:
                await self.websocket.send_text(f'{{"error": "{str(ie)}"}}')
                await self.websocket.close(code=1011)  # Internal error
            except:
                pass
            raise
        except KeyError as ke:
            # Handle KeyError exceptions specifically
            logger.error(f"KeyError in pipeline execution: {ke}")
            try:
                await self.websocket.send_text('{"error": "Configuration or data access error - please try again"}')
                await self.websocket.close(code=1011)
            except:
                pass
            raise
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            # Send generic error message to WebSocket if possible
            try:
                await self.websocket.send_text(f'{{"error": "Pipeline error: {str(e)}"}}')
                await self.websocket.close(code=1011)
            except:
                pass
            raise


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

