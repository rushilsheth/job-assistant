#!/usr/bin/env python3
"""
Gmail MCP client for JobTracker application.
Handles interaction with Gmail through the Model Context Protocol.
"""

import os
import logging
import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.types import Tool

logger = logging.getLogger("job-tracker.gmail")

class GmailClient:
    """Client for interacting with Gmail through MCP."""
    
    def __init__(self):
        """Initialize the Gmail client."""
        self.session = None
        self.exit_stack = None
        self.gmail_mcp_path = os.environ.get("GMAIL_MCP_PATH", "gmail-mcp-server")
        
        # Configure keywords to identify job-related emails
        self.job_keywords = [
            "interview", "application", "job opportunity", "position", 
            "employment", "recruiter", "recruiting", "talent", "hiring",
            "career", "job description", "resume", "CV", "cover letter",
            "follow-up", "follow up", "thank you", "offer", "salary",
            "job posting", "job listing"
        ]
        
        logger.info("Gmail client initialized")
    
    async def connect(self):
        """Connect to the Gmail MCP server."""
        try:
            # Setup Gmail MCP server connection
            logger.info("Connecting to Gmail MCP server...")
            
            # Using async with to properly handle the context manager
            async with stdio_client(self.gmail_mcp_path) as session:
                self.session = session
                
                # Verify connection by listing labels
                labels = await self.get_labels()
                if labels:
                    logger.info(f"Connected to Gmail MCP server, found {len(labels)} labels")
                    return True
                else:
                    logger.error("Connected to Gmail MCP server but no labels found")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to connect to Gmail MCP server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the Gmail MCP server."""
        if self.session:
            await self.session.aclose()
            self.session = None
            logger.info("Disconnected from Gmail MCP server")
    
    async def get_labels(self) -> List[Dict[str, Any]]:
        """Get all Gmail labels."""
        if not self.session:
            logger.error("Not connected to Gmail MCP server")
            return []
        
        try:
            # Call the list_labels tool from the Gmail MCP server
            result = await self.session.invoke_tool("list_labels")
            return result.get("labels", [])
        except Exception as e:
            logger.error(f"Failed to list Gmail labels: {e}")
            return []
    
    async def search_emails(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for emails using Gmail's search syntax.
        
        Args:
            query: Gmail search query
            limit: Maximum number of emails to return
            
        Returns:
            List of email data dictionaries
        """
        if not self.session:
            logger.error("Not connected to Gmail MCP server")
            return []
        
        try:
            # Prepare search parameters
            search_params = {
                "query": query,
                "max_results": limit
            }
            
            # Call the search_emails tool
            result = await self.session.invoke_tool("search_emails", search_params)
            emails = result.get("emails", [])
            
            logger.info(f"Found {len(emails)} emails matching query: {query}")
            return emails
        except Exception as e:
            logger.error(f"Failed to search emails: {e}")
            return []
    
    async def get_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific email by ID.
        
        Args:
            email_id: Gmail message ID
            
        Returns:
            Email data or None if not found/error
        """
        if not self.session:
            logger.error("Not connected to Gmail MCP server")
            return None
        
        try:
            # Parameters for getting a specific email
            params = {
                "message_id": email_id
            }
            
            # Call the get_email tool
            result = await self.session.invoke_tool("get_email", params)
            
            if "error" in result:
                logger.error(f"Error retrieving email: {result['error']}")
                return None
                
            return result
        except Exception as e:
            logger.error(f"Failed to get email {email_id}: {e}")
            return None
    
    async def search_company_emails(self, company_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for emails related to a specific company.
        
        Args:
            company_name: Company name to search for
            limit: Maximum number of emails to return
            
        Returns:
            List of email data dictionaries
        """
        # Create a search query that looks for the company name
        # and job-related keywords in the email
        query = f"({company_name})"
        
        # Add job keywords to search to filter for relevant emails
        job_terms = " OR ".join([f"\"{keyword}\"" for keyword in self.job_keywords[:5]])
        if job_terms:
            query += f" AND ({job_terms})"
        
        # Search for recent emails first
        query += " newer_than:3m"
        
        # Perform the search
        return await self.search_emails(query, limit)
    
    async def extract_company_from_email(self, email_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract company name from email data.
        Uses heuristics like sender domain, signature, etc.
        
        Args:
            email_data: Email data dictionary
            
        Returns:
            Company name or None if not found
        """
        if not email_data:
            return None
            
        # Try various methods to extract company name
        
        # Method 1: Check the sender's email domain (excluding common providers)
        common_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com"]
        sender = email_data.get("from", "")
        if "@" in sender:
            domain = sender.split("@")[1].lower()
            if domain not in common_domains:
                # Convert domain to company name format (remove .com, .org, etc. and capitalize)
                company = domain.split(".")[0].title()
                logger.info(f"Extracted company from email domain: {company}")
                return company
        
        # Method 2: Look for common signature patterns in email body
        body = email_data.get("body", "")
        signature_patterns = [
            r"(?i)(?:^|\n).*?([A-Z][A-Za-z0-9\s&]+)(?:\n|$).*?(?:Inc\.|LLC|Ltd\.|Limited|Corp\.|Corporation)",
            r"(?i)(?:work|working) (?:at|for|with) ([A-Z][A-Za-z0-9\s&]+)",
            r"(?i)(?:behalf|representative) of ([A-Z][A-Za-z0-9\s&]+)"
        ]
        
        for pattern in signature_patterns:
            matches = re.findall(pattern, body)
            if matches:
                company = matches[0].strip()
                logger.info(f"Extracted company from email body: {company}")
                return company
        
        # Method 3: Look for company name in subject
        subject = email_data.get("subject", "")
        subject_patterns = [
            r"(?i)(?:position|role|opportunity|application|interview) (?:at|with) ([A-Z][A-Za-z0-9\s&]+)",
            r"(?i)([A-Z][A-Za-z0-9\s&]+) (?:position|role|opportunity|application|interview)"
        ]
        
        for pattern in subject_patterns:
            matches = re.findall(pattern, subject)
            if matches:
                company = matches[0].strip()
                logger.info(f"Extracted company from email subject: {company}")
                return company
        
        logger.warning("Could not extract company name from email")
        return None
    
    async def extract_key_points(self, email_data: Dict[str, Any]) -> List[str]:
        """
        Extract key points from the email body.
        Looks for job-relevant information.
        
        Args:
            email_data: Email data dictionary
            
        Returns:
            List of key points from the email
        """
        if not email_data:
            return []
            
        body = email_data.get("body", "")
        if not body:
            return []
            
        key_points = []
        
        # Extract potential interview times/dates
        date_patterns = [
            r"(?:interview|meeting|call|discussion)(?:.*?)(?:scheduled|planned|arranged|set up)(?:.*?)(?:on|for) ([A-Za-z]+\s+\d+(?:st|nd|rd|th)?(?:,?\s+\d{4})?(?:\s+at\s+\d+(?::\d+)?(?:\s*[AP]M)?)?)",
            r"(\d{1,2}(?::\d{2})?\s*[AP]M\s*(?:EST|CST|MST|PST|EDT|CDT|MDT|PDT)?)(?:.*?)(?:interview|meeting|call|discussion)",
            r"([A-Za-z]+day,?\s+[A-Za-z]+\s+\d+(?:st|nd|rd|th)?(?:,?\s+\d{4})?)"
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, body)
            for match in matches:
                key_points.append(f"Scheduled: {match.strip()}")
        
        # Extract position information
        position_patterns = [
            r"(?:position|role|job)(?: for| of)? ([^.,;]+?)(?:\.|\n|,|;)",
            r"(?:applying|application|candidacy)(?: for| to)? ([^.,;]+?)(?:\.|\n|,|;)"
        ]
        
        for pattern in position_patterns:
            matches = re.findall(pattern, body)
            for match in matches:
                if len(match.strip()) > 3:  # Avoid very short matches
                    key_points.append(f"Position: {match.strip()}")
        
        # Extract next steps
        next_step_patterns = [
            r"(?:next steps?|follow(?:-| )up)(?: will be| is| are)? ([^.,;]+?)(?:\.|\n|,|;)",
            r"(?:looking forward to|please|kindly) ([^.,;]*?(?:schedule|confirm|respond|reply|review|send|submit)(?-)[^.,;]*?)(?:\.|\n|,|;)"
        ]
        
        for pattern in next_step_patterns:
            matches = re.findall(pattern, body)
            for match in matches:
                if len(match.strip()) > 10:  # Avoid very short matches
                    key_points.append(f"Next steps: {match.strip()}")
        
        # Add subject line as a key point if it's informative
        subject = email_data.get("subject", "")
        if len(subject) > 10 and not subject.startswith("Re:") and not subject.startswith("Fwd:"):
            key_points.append(f"Subject: {subject}")
        
        # Add sender information
        sender = email_data.get("from", "")
        if sender:
            key_points.append(f"From: {sender}")
        
        # Add date information
        date = email_data.get("date", "")
        if date:
            key_points.append(f"Date: {date}")
        
        return key_points