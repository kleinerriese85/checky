"""
Checky multimodal assistant pipeline implementation.

This module provides the CheckyPipeline class that creates a multimodal conversational
AI assistant for children, using Google Speech-to-Text, Text-to-Speech, and Gemini 1.5
for age-appropriate German responses.
"""

import os
import re
from typing import Dict, Any, Optional

from loguru import logger

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.google.stt import GoogleSTTService
from pipecat.services.google.tts import GoogleTTSService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import BaseTransport


class CheckyPipeline:
    """
    Multimodal pipeline for Checky children's assistant.
    
    Creates a conversational AI pipeline using Google services for speech recognition,
    text-to-speech, and language understanding with age-appropriate German responses.
    """
    
    def __init__(self, transport: BaseTransport, config: Dict[str, Any]):
        """
        Initialize the CheckyPipeline.
        
        Args:
            transport: The transport layer for audio I/O
            config: Configuration dictionary containing child_age, tts_voice, etc.
        """
        self.transport = transport
        self.config = config
        self.child_age = config.get('child_age', 7)
        self.tts_voice = config.get('tts_voice', 'de-DE-Standard-A')
        
        self._setup_services()
        self._setup_pipeline()
    
    def _setup_services(self):
        """Setup Google STT, TTS, and LLM services."""
        # Google Speech-to-Text service for German
        self.stt = GoogleSTTService(
            params=GoogleSTTService.InputParams(languages=Language.DE),
            credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        )
        
        # Google Text-to-Speech service for German
        self.tts = GoogleTTSService(
            voice_id=self.tts_voice,
            params=GoogleTTSService.InputParams(language=Language.DE),
            credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
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
        
        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]
        
        context = OpenAILLMContext(messages)
        context_aggregator = self.llm.create_context_aggregator(context)
        
        # Create the pipeline with all components
        self.pipeline = Pipeline([
            self.transport.input(),  # Audio input from transport
            self.stt,               # Speech-to-Text
            context_aggregator.user(),  # User context processing
            self.llm,               # LLM processing with PII scrubbing
            self.tts,               # Text-to-Speech
            self.transport.output(),     # Audio output to transport
            context_aggregator.assistant(),  # Assistant context processing
        ])
    
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
        return PipelineTask(
            self.pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            idle_timeout_secs=idle_timeout_secs,
        )


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