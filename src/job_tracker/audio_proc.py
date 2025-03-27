#!/usr/bin/env python3
"""
Audio processing module for JobTracker application.
Handles audio recording, transcription, and extraction of key information.
"""

import os
import logging
import asyncio
import tempfile
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional

import whisper  # For transcription
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.types import Tool

logger = logging.getLogger("job-tracker.audio")

class AudioProcessor:
    """Handles audio recording and processing for job interview calls."""
    
    def __init__(self):
        """Initialize the audio processor."""
        self.session = None
        self.exit_stack = None
        self.audio_mcp_path = os.environ.get("AUDIO_MCP_PATH", "audio-mcp-server")
        self.transcription_model = None
        self.last_recording_path = None
        
        # Initialize whisper model for transcription (load small model by default)
        self.model_name = os.environ.get("WHISPER_MODEL", "small")
        logger.info(f"Initializing Whisper with model: {self.model_name}")
    
    async def connect(self):
        """Connect to the Audio MCP server."""
        try:
            # Setup Audio MCP server connection
            logger.info("Connecting to Audio MCP server...")
            
            # Using async with to properly handle the context manager
            async with stdio_client(self.audio_mcp_path) as session:
                self.session = session
                
                # Verify connection by listing available devices
                devices = await self.list_audio_devices()
                if devices:
                    logger.info(f"Connected to Audio MCP server, found {len(devices)} audio devices")
                    return True
                else:
                    logger.error("Connected to Audio MCP server but no audio devices found")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to connect to Audio MCP server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the Audio MCP server."""
        if self.session:
            await self.session.aclose()
            self.session = None
            logger.info("Disconnected from Audio MCP server")
    
    async def list_audio_devices(self) -> List[Dict[str, Any]]:
        """List available audio input/output devices."""
        if not self.session:
            logger.error("Not connected to Audio MCP server")
            return []
        
        try:
            # Call the list_devices tool from the Audio MCP server
            result = await self.session.invoke_tool("list_devices")
            return result.get("devices", [])
        except Exception as e:
            logger.error(f"Failed to list audio devices: {e}")
            return []
    
    async def start_recording(self, duration: int = 60, device_id: Optional[str] = None) -> bool:
        """
        Start recording audio from the specified device.
        
        Args:
            duration: Recording duration in seconds
            device_id: Optional specific device ID to record from
        
        Returns:
            bool: True if recording started successfully
        """
        if not self.session:
            logger.error("Not connected to Audio MCP server")
            return False
        
        try:
            # If device_id not specified, try to find the default input device
            if not device_id:
                devices = await self.list_audio_devices()
                input_devices = [d for d in devices if d.get("is_input", False)]
                if not input_devices:
                    logger.error("No input devices found")
                    return False
                device_id = input_devices[0].get("id")
                logger.info(f"Using default input device: {device_id}")
            
            # Start recording
            recording_params = {
                "device_id": device_id,
                "duration": duration,
                "sample_rate": 44100,
                "channels": 1
            }
            
            result = await self.session.invoke_tool("record_audio", recording_params)
            
            # Check if recording started successfully
            if result.get("status") == "recording":
                logger.info(f"Recording started for {duration} seconds")
                return True
            else:
                logger.error(f"Failed to start recording: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False
    
    async def get_recording(self) -> Optional[str]:
        """
        Get the path to the most recent recording.
        
        Returns:
            str: Path to recording file or None if not available
        """
        if not self.session:
            logger.error("Not connected to Audio MCP server")
            return None
        
        try:
            result = await self.session.invoke_tool("get_recording_path")
            self.last_recording_path = result.get("path")
            return self.last_recording_path
        except Exception as e:
            logger.error(f"Failed to get recording path: {e}")
            return None
    
    async def transcribe(self, audio_path: Optional[str] = None) -> str:
        """
        Transcribe audio file to text.
        
        Args:
            audio_path: Path to audio file (uses last recording if not specified)
            
        Returns:
            str: Transcribed text
        """
        # Use last recording path if not specified
        if not audio_path and self.last_recording_path:
            audio_path = self.last_recording_path
        elif not audio_path:
            logger.error("No audio path specified and no recent recording available")
            return ""
        
        logger.info(f"Transcribing audio file: {audio_path}")
        
        try:
            # Load whisper model lazily (only when needed)
            if self.transcription_model is None:
                self.transcription_model = whisper.load_model(self.model_name)
            
            # Perform transcription
            result = self.transcription_model.transcribe(audio_path)
            transcript = result.get("text", "")
            
            # Save transcript to file for reference
            transcript_path = f"{audio_path}.txt"
            with open(transcript_path, "w") as f:
                f.write(transcript)
            
            logger.info(f"Transcription saved to {transcript_path}")
            return transcript
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return f"Transcription error: {str(e)}"
    
    async def extract_company_name(self, transcript: str) -> Optional[str]:
        """
        Attempt to extract company name from the transcript.
        Uses heuristics and potential company name patterns.
        
        Args:
            transcript: Transcribed text of the call
            
        Returns:
            str: Company name or None if not found
        """
        # Common patterns in interviews like "I'm [name] from [company]"
        patterns = [
            r"(?:I'm|I am|this is)(?:[^,.]*)(?:from|with|at)\s+([A-Z][A-Za-z0-9\s&]+)",
            r"(?:welcome to|joining|interview with)\s+([A-Z][A-Za-z0-9\s&]+)",
            r"([A-Z][A-Za-z0-9\s&]+)(?:position|opportunity|role|job)"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, transcript)
            if matches:
                # Take the longest match as it's likely more complete
                company = max(matches, key=len).strip()
                logger.info(f"Extracted company name: {company}")
                return company
        
        # If patterns don't match, try to ask Claude for help extracting the company name
        # This would integrate with a function that uses Claude to analyze the transcript
        # and extract the company name
        
        logger.warning("Could not extract company name from transcript")
        return None
    
    async def extract_key_points(self, transcript: str) -> List[str]:
        """
        Extract key points from the interview transcript.
        This uses heuristics to identify important interview information.
        
        Args:
            transcript: Transcribed text of the call
            
        Returns:
            List[str]: List of key points from the interview
        """
        key_points = []
        
        # Look for role-related information
        role_patterns = [
            r"(?:the role|position|job)(?: is| involves| includes)([^.]*)",
            r"(?:looking for|seeking|need)(?:[^.]*?)(?:someone who|a person who|candidates who)([^.]*)",
            r"(?:responsibilities include|will be responsible for|duties are)([^.]*)"
        ]
        
        # Look for skills/requirements
        skill_patterns = [
            r"(?:require|need|looking for|must have)(?:[^.]*?)(?:experience with|background in|knowledge of)([^.]*)",
            r"(?:skills|qualifications|requirements)(?:[^.]*?)(?:include|are|should be)([^.]*)"
        ]
        
        # Look for company information
        company_patterns = [
            r"(?:our company|we are|the company)(?:[^.]*?)(?:focused on|specializes in|works on)([^.]*)",
            r"(?:founded|started|established)(?:[^.]*?)(?:in|on|around)([^.]*)"
        ]
        
        # Look for next steps
        next_step_patterns = [
            r"(?:next steps|next stage|what happens next|moving forward)([^.]*)",
            r"(?:follow up|get back to you|decision|hear from us)([^.]*)"
        ]
        
        # Extract matches for each pattern category
        for pattern in role_patterns:
            matches = re.findall(pattern, transcript)
            for match in matches:
                if match.strip():
                    key_points.append(f"Role: {match.strip()}")
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, transcript)
            for match in matches:
                if match.strip():
                    key_points.append(f"Required: {match.strip()}")
        
        for pattern in company_patterns:
            matches = re.findall(pattern, transcript)
            for match in matches:
                if match.strip():
                    key_points.append(f"Company: {match.strip()}")
        
        for pattern in next_step_patterns:
            matches = re.findall(pattern, transcript)
            for match in matches:
                if match.strip():
                    key_points.append(f"Next steps: {match.strip()}")
        
        return key_points
    
    def extract_date_from_filename(self, filepath: str) -> str:
        """
        Extract date from filename or use current date if not found.
        
        Args:
            filepath: Path to audio file
            
        Returns:
            str: Date in ISO format
        """
        # Try to find date pattern in filename (YYYY-MM-DD or YYYYMMDD)
        filename = os.path.basename(filepath)
        date_match = re.search(r'(\d{4}[-_]?\d{2}[-_]?\d{2})', filename)
        
        if date_match:
            date_str = date_match.group(1).replace('_', '-').replace(' ', '-')
            return date_str
        else:
            # Use current date if no date found in filename
            return datetime.now().strftime('%Y-%m-%d')
    
    async def record_call(self, duration: int = 60, device_id: Optional[str] = None) -> Optional[str]:
        """
        Record a call and return the transcript.
        
        Args:
            duration: Recording duration in seconds
            device_id: Optional specific device ID to record from
            
        Returns:
            str: Transcribed text or None if failed
        """
        # Start recording
        if not await self.start_recording(duration, device_id):
            return None
        
        # Wait for the recording to complete
        logger.info(f"Waiting for {duration} seconds for recording to complete...")
        await asyncio.sleep(duration)
        
        # Get recording path
        recording_path = await self.get_recording()
        if not recording_path:
            logger.error("Failed to get recording path")
            return None
        
        # Transcribe recording
        transcript = await self.transcribe(recording_path)
        return transcript