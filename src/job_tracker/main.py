#!/usr/bin/env python3
"""
JobTracker MCP - A job search tracking application using Model Context Protocol
to integrate with Notion and Gmail.
"""

import os
import sys
import asyncio
import argparse
import logging
from dotenv import load_dotenv

# Import our client modules
from job_tracker.notion_client import NotionClient
from job_tracker.gmail_client import GmailClient
from job_tracker.audio_proc import AudioProcessor
from job_tracker.state import StateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("job-tracker")

class JobTrackerApp:
    """Main application class for the JobTracker MCP application."""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize state manager
        self.state = StateManager()
        
        # Initialize clients
        self.notion = NotionClient()
        self.gmail = GmailClient()
        self.audio = AudioProcessor()
        
        logger.info("JobTracker MCP initialized")
    
    async def connect(self):
        """Connect to all MCP servers."""
        try:
            await self.notion.connect()
            await self.gmail.connect()
            await self.audio.connect()
            logger.info("Connected to all MCP servers")
            return True
        except Exception as e:
            logger.error(f"Error connecting to MCP servers: {e}")
            return False
    
    async def process_call_recording(self, file_path, company_name=None, transcript=None):
        """Process a call recording and update Notion."""
        logger.info(f"Processing call recording: {file_path if file_path else 'from live recording'}")
        
        # If transcript is provided, use it directly (from live recording)
        if not transcript and file_path:
            # Transcribe the audio file
            transcript = await self.audio.transcribe(file_path)
        
        if not transcript:
            logger.error("No transcript available")
            return None
        
        # If company name not provided, try to extract it from the transcript
        if not company_name:
            company_name = await self.audio.extract_company_name(transcript)
            if not company_name:
                logger.warning("Could not extract company name from transcript")
                company_name = input("Please enter the company name: ")
        
        # Get or create company page in Notion
        company_page = await self.notion.get_or_create_company(company_name)
        
        # Extract key points from transcript
        key_points = await self.audio.extract_key_points(transcript)
        
        # Update the company page with the call notes
        call_date = self.audio.extract_date_from_filename(file_path) if file_path else self.audio.get_current_date()
        
        await self.notion.add_call_notes(
            company_page,
            transcript=transcript,
            key_points=key_points,
            call_date=call_date
        )
        
        # Update application state
        self.state.update_company_state(company_name, {
            "last_interaction": "call",
            "last_interaction_date": call_date,
            "has_calls": True
        })
        
        logger.info(f"Successfully processed call for {company_name}")
        return company_page
    
    async def process_email(self, email_id=None, company_name=None):
        """Process an email and update Notion."""
        if email_id:
            # Fetch specific email
            email_data = await self.gmail.get_email(email_id)
        else:
            # If no email_id provided, search for emails related to the company
            if not company_name:
                logger.error("Either email_id or company_name must be provided")
                return None
            
            email_data = await self.gmail.search_company_emails(company_name, limit=1)
            if not email_data:
                logger.warning(f"No emails found for company: {company_name}")
                return None
            
            email_data = email_data[0]  # Get the most recent email
        
        # Extract company name from email if not provided
        if not company_name:
            company_name = await self.gmail.extract_company_from_email(email_data)
            if not company_name:
                logger.warning("Could not extract company name from email")
                company_name = input("Please enter the company name: ")
        
        # Get or create company page in Notion
        company_page = await self.notion.get_or_create_company(company_name)
        
        # Extract key information from email
        key_points = await self.gmail.extract_key_points(email_data)
        
        # Update the company page with the email information
        await self.notion.add_email_notes(
            company_page,
            email_data=email_data,
            key_points=key_points
        )
        
        # Update application state
        self.state.update_company_state(company_name, {
            "last_interaction": "email",
            "last_interaction_date": email_data.get("date"),
            "has_emails": True
        })
        
        logger.info(f"Successfully processed email for {company_name}")
        return company_page
    
    async def search_companies(self, query):
        """Search for companies in Notion."""
        companies = await self.notion.search_companies(query)
        return companies
    
    async def get_company_status(self, company_name):
        """Get the current status of a company application."""
        # Check Notion for company info
        company_page = await self.notion.get_company(company_name)
        
        # Get state information
        state_info = self.state.get_company_state(company_name)
        
        # Combine information
        status = {
            "company_name": company_name,
            "notion_page": company_page,
            "state": state_info,
        }
        
        return status
    
    async def test_connections(self):
        """Test connections to all MCP servers."""
        results = {}
        
        try:
            notion_connected = await self.notion.connect()
            results["notion"] = notion_connected
        except Exception as e:
            logger.error(f"Error connecting to Notion: {e}")
            results["notion"] = False
        
        try:
            gmail_connected = await self.gmail.connect()
            results["gmail"] = gmail_connected
        except Exception as e:
            logger.error(f"Error connecting to Gmail: {e}")
            results["gmail"] = False
        
        try:
            audio_connected = await self.audio.connect()
            results["audio"] = audio_connected
        except Exception as e:
            logger.error(f"Error connecting to Audio: {e}")
            results["audio"] = False
        
        return results
    
    async def cleanup(self):
        """Clean up and close connections."""
        await self.notion.disconnect()
        await self.gmail.disconnect()
        await self.audio.disconnect()
        logger.info("Disconnected from all MCP servers")


async def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="JobTracker MCP Application")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Add call command
    call_parser = subparsers.add_parser("call", help="Process a call recording or record a new one")
    call_parser.add_argument("file", nargs="?", help="Path to the audio file (optional if --record is used)")
    call_parser.add_argument("--record", type=int, help="Duration in seconds to record audio")
    call_parser.add_argument("--company", help="Company name (optional)")
    call_parser.add_argument("--device", help="Audio device ID (optional)")
    call_parser.add_argument("--list-devices", action="store_true", help="List available audio devices")
    
    # Add email command
    email_parser = subparsers.add_parser("email", help="Process an email")
    email_parser.add_argument("--id", help="Email ID (optional)")
    email_parser.add_argument("--company", help="Company name (optional)")
    
    # Add test-connections command
    test_parser = subparsers.add_parser("test-connections", help="Test connections to MCP servers")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Create app
    app = JobTrackerApp()
    
    # Connect to MCP servers
    if not await app.connect():
        print("Failed to connect to MCP servers. Exiting.")
        return 1
    
    try:
        if args.command == "call":
            # List devices if requested
            if args.list_devices:
                devices = await app.audio.list_audio_devices()
                print(f"Available audio devices:")
                for i, device in enumerate(devices):
                    print(f"  {i+1}. {device.get('name', 'Unknown')} (ID: {device.get('id', 'Unknown')})")
                return 0
                
            # Handle recording
            if args.record:
                print(f"Recording audio for {args.record} seconds...")
                transcript = await app.audio.record_call(args.record, args.device)
                if not transcript:
                    print("Failed to record or transcribe audio")
                    return 1
                
                # Process the transcript
                result = await app.process_call_recording(None, args.company, transcript=transcript)
                if result:
                    print(f"Recording processed successfully for company: {result.get('title', args.company)}")
                    print(f"View in Notion: {result.get('url', 'Unknown URL')}")
                else:
                    print("Failed to process recording")
                return 0
                    
            # Process existing audio file
            if not args.file:
                print("Error: Either file path or --record must be specified")
                call_parser.print_help()
                return 1
                
            result = await app.process_call_recording(args.file, args.company)
            if result:
                print(f"Call processed successfully for company: {result.get('title', args.company)}")
                print(f"View in Notion: {result.get('url', 'Unknown URL')}")
            else:
                print("Failed to process call recording")
                
        elif args.command == "email":
            result = await app.process_email(args.id, args.company)
            if result:
                print(f"Email processed successfully for company: {result.get('title', args.company)}")
                print(f"View in Notion: {result.get('url', 'Unknown URL')}")
            else:
                print("Failed to process email")
                
        elif args.command == "search":
            companies = await app.search_companies(args.query)
            print(f"Found {len(companies)} companies matching '{args.query}':")
            for company in companies:
                title = company.get('title', 'Unknown')
                url = company.get('url', 'No URL')
                print(f"- {title} ({url})")
                
        elif args.command == "status":
            status = await app.get_company_status(args.company)
            print(f"Status for {args.company}:")
            if status["notion_page"]:
                print(f"Notion Page: {status['notion_page'].get('url', 'No URL')}")
            else:
                print("Notion Page: Not created")
                
            print(f"Last Interaction: {status['state'].get('last_interaction', 'None')}")
            print(f"Last Interaction Date: {status['state'].get('last_interaction_date', 'Unknown')}")
            print(f"Has Calls: {status['state'].get('has_calls', False)}")
            print(f"Has Emails: {status['state'].get('has_emails', False)}")
        
        elif args.command == "test-connections":
            results = await app.test_connections()
            print("Connection test results:")
            for server, connected in results.items():
                status = "Connected" if connected else "Failed"
                print(f"- {server.capitalize()}: {status}")
            
        else:
            parser.print_help()
            
    finally:
        await app.cleanup()
    
    return 0


def run_main():
    """Entry point for the application that handles the asyncio event loop."""
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(run_main())