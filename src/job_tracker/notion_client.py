#!/usr/bin/env python3
"""
Notion MCP client for JobTracker application.
Handles interaction with Notion through the Model Context Protocol.
"""

import os
import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client_from_command
from mcp.types import Tool

logger = logging.getLogger("job-tracker.notion")

# Template for company pages
COMPANY_TEMPLATE = {
    "title": "",  # Will be filled with company name
    "properties": {
        "Status": {"select": {"name": "Applied"}},
        "Application Date": {"date": {"start": datetime.now().isoformat()}},
        "Position": {"title": [{"text": {"content": "Unknown"}}]},
        "Contact": {"rich_text": [{"text": {"content": ""}}]},
        "Next Step": {"select": {"name": "Follow Up"}},
        "Priority": {"select": {"name": "Medium"}},
    },
    "children": [
        {
            "object": "block",
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"type": "text", "text": {"content": "Interactions"}}]
            }
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": "Record of interactions with the company."}}]
            }
        }
    ]
}

class NotionClient:
    """Client for interacting with Notion through MCP."""
    
    def __init__(self):
        """Initialize the Notion client."""
        self.session = None
        self.exit_stack = None
        self.notion_mcp_path = os.environ.get("NOTION_MCP_PATH", "notion-mcp-server")
        
        # Configuration
        self.workspace_id = os.environ.get("NOTION_WORKSPACE_ID")
        self.database_id = os.environ.get("NOTION_DATABASE_ID")
        
        logger.info("Notion client initialized")
    
    async def connect(self):
        """Connect to the Notion MCP server."""
        try:
            # Setup Notion MCP server connection
            logger.info("Connecting to Notion MCP server...")
            
            # Using async with to properly handle the context manager
            command = {
                "command": "npx",
                "args": ["-y", self.xyz_mcp_path],
            }

            self.session = await stdio_client_from_command(command)
            
            # If database_id not set, try to find or create the job applications database
            if not self.database_id:
                self.database_id = await self._get_or_create_job_database()
            
            logger.info(f"Connected to Notion MCP server, using database: {self.database_id}")
            return True
                
        except Exception as e:
            logger.error(f"Failed to connect to Notion MCP server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the Notion MCP server."""
        if self.session:
            await self.session.aclose()
            self.session = None
            logger.info("Disconnected from Notion MCP server")
    
    async def _get_or_create_job_database(self) -> str:
        """
        Find or create a job applications database in Notion.
        
        Returns:
            str: Database ID of the job applications database
        """
        try:
            # Search for existing "Job Applications" database
            search_params = {
                "query": "Job Applications",
                "filter": {"object": "database"}
            }
            result = await self.session.invoke_tool("search_notion", search_params)
            
            # Check if we found a job applications database
            results = result.get("results", [])
            for item in results:
                if item.get("object") == "database" and "Job Applications" in item.get("title", ""):
                    database_id = item.get("id")
                    logger.info(f"Found existing Job Applications database: {database_id}")
                    return database_id
            
            # If not found, create a new database
            logger.info("Job Applications database not found, creating a new one")
            
            # Create new database
            db_params = {
                "parent": {"type": "workspace", "workspace": True},
                "title": [{"type": "text", "text": {"content": "Job Applications"}}],
                "properties": {
                    "Name": {"title": {}},
                    "Status": {
                        "select": {
                            "options": [
                                {"name": "Not Applied", "color": "gray"},
                                {"name": "Applied", "color": "blue"},
                                {"name": "Interview", "color": "yellow"},
                                {"name": "Offer", "color": "green"},
                                {"name": "Rejected", "color": "red"},
                                {"name": "Declined", "color": "purple"}
                            ]
                        }
                    },
                    "Position": {"rich_text": {}},
                    "Application Date": {"date": {}},
                    "Contact": {"rich_text": {}},
                    "Notes": {"rich_text": {}},
                    "Next Step": {"select": {
                        "options": [
                            {"name": "Apply", "color": "blue"},
                            {"name": "Follow Up", "color": "yellow"},
                            {"name": "Prepare", "color": "orange"},
                            {"name": "Interview", "color": "green"},
                            {"name": "Wait", "color": "gray"}
                        ]
                    }},
                    "Priority": {"select": {
                        "options": [
                            {"name": "Low", "color": "gray"},
                            {"name": "Medium", "color": "yellow"},
                            {"name": "High", "color": "red"}
                        ]
                    }}
                }
            }
            
            result = await self.session.invoke_tool("create_database", db_params)
            database_id = result.get("id")
            
            if database_id:
                logger.info(f"Created new Job Applications database: {database_id}")
                return database_id
            else:
                logger.error("Failed to create Job Applications database")
                raise Exception("Failed to create database")
                
        except Exception as e:
            logger.error(f"Error finding/creating database: {e}")
            raise
    
    async def search_companies(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for company pages in the job applications database.
        
        Args:
            query: Search query (company name)
            
        Returns:
            List of matching company pages
        """
        if not self.session:
            logger.error("Not connected to Notion MCP server")
            return []
        
        if not self.database_id:
            logger.error("No database ID set")
            return []
        
        try:
            # Search for pages in the database
            search_params = {
                "query": query,
                "filter": {
                    "property": "object",
                    "value": "page"
                }
            }
            
            result = await self.session.invoke_tool("search_notion", search_params)
            pages = []
            
            # Filter for pages in our job database
            for page in result.get("results", []):
                if page.get("parent", {}).get("database_id") == self.database_id:
                    pages.append(page)
            
            logger.info(f"Found {len(pages)} company pages matching '{query}'")
            return pages
        except Exception as e:
            logger.error(f"Error searching companies: {e}")
            return []
    
    async def get_company(self, company_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a company page by name.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Company page data or None if not found
        """
        # Search for the company
        companies = await self.search_companies(company_name)
        
        # Find exact or close match
        for company in companies:
            page_title = company.get("properties", {}).get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", "")
            if page_title.lower() == company_name.lower() or company_name.lower() in page_title.lower():
                return company
        
        return None if not companies else companies[0]
    
    async def get_or_create_company(self, company_name: str) -> Dict[str, Any]:
        """
        Get an existing company page or create a new one.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Company page data
        """
        # Try to find existing company
        company = await self.get_company(company_name)
        
        if company:
            logger.info(f"Found existing company page: {company_name}")
            return company
        
        # Create new company page
        logger.info(f"Creating new company page: {company_name}")
        
        # Copy the template and update the title
        company_data = COMPANY_TEMPLATE.copy()
        company_data["title"] = company_name
        
        # Create page in the database
        page_params = {
            "parent": {"database_id": self.database_id},
            "properties": {
                "Name": {"title": [{"text": {"content": company_name}}]},
                "Status": {"select": {"name": "Not Applied"}},
                "Application Date": {"date": {"start": datetime.now().isoformat()}},
                "Position": {"rich_text": [{"text": {"content": "Unknown"}}]},
                "Contact": {"rich_text": [{"text": {"content": ""}}]},
                "Next Step": {"select": {"name": "Apply"}},
                "Priority": {"select": {"name": "Medium"}}
            },
            "children": company_data["children"]
        }
        
        try:
            result = await self.session.invoke_tool("create_page", page_params)
            
            if result.get("id"):
                logger.info(f"Created new company page: {company_name}")
                return result
            else:
                logger.error(f"Failed to create company page: {company_name}")
                raise Exception(f"Failed to create company page: {result}")
        except Exception as e:
            logger.error(f"Error creating company page: {e}")
            raise
    
    async def add_call_notes(
        self, 
        company_page: Dict[str, Any], 
        transcript: str, 
        key_points: List[str],
        call_date: str
    ) -> Dict[str, Any]:
        """
        Add call notes to a company page.
        
        Args:
            company_page: Company page data
            transcript: Call transcript
            key_points: List of key points from the call
            call_date: Date of the call
            
        Returns:
            Updated company page data
        """
        if not self.session:
            logger.error("Not connected to Notion MCP server")
            return company_page
        
        page_id = company_page.get("id")
        if not page_id:
            logger.error("Invalid company page: no ID found")
            return company_page
        
        try:
            # Prepare call notes blocks
            call_blocks = [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": f"Call Notes - {call_date}"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": "Key points from the call:"}}]
                    }
                }
            ]
            
            # Add key points as bullet points
            for point in key_points:
                call_blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": point}}]
                    }
                })
            
            # Add transcript (might need to be broken up if too long)
            call_blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": "Transcript"}}]
                }
            })
            
            # Split transcript into paragraphs (Notion has size limits)
            paragraphs = transcript.split('\n\n')
            for paragraph in paragraphs:
                if paragraph.strip():
                    # Further chunk long paragraphs (Notion has a ~2000 char limit per block)
                    if len(paragraph) > 1900:
                        chunks = [paragraph[i:i+1900] for i in range(0, len(paragraph), 1900)]
                        for chunk in chunks:
                            call_blocks.append({
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [{"type": "text", "text": {"content": chunk.strip()}}]
                                }
                            })
                    else:
                        call_blocks.append({
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"type": "text", "text": {"content": paragraph.strip()}}]
                            }
                        })
            
            # Find the "Interactions" heading to append after
            children_params = {
                "block_id": page_id,
                "recursive": False
            }
            
            blocks_result = await self.session.invoke_tool("get_block_children", children_params)
            
            # Look for Interactions heading or append at the end
            append_after_id = None
            for block in blocks_result.get("results", []):
                if block.get("type") == "heading_1":
                    heading_text = block.get("heading_1", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
                    if heading_text == "Interactions":
                        append_after_id = block.get("id")
                        break
            
            # If found, append after that block, otherwise append to the page
            if append_after_id:
                append_params = {
                    "block_id": append_after_id,
                    "children": call_blocks
                }
                await self.session.invoke_tool("append_block_children", append_params)
            else:
                append_params = {
                    "block_id": page_id,
                    "children": call_blocks
                }
                await self.session.invoke_tool("append_block_children", append_params)
            
            # Update page properties
            properties_update = {
                "Status": {"select": {"name": "Interview"}},
                "Next Step": {"select": {"name": "Follow Up"}}
            }
            
            update_params = {
                "page_id": page_id,
                "properties": properties_update
            }
            
            result = await self.session.invoke_tool("update_page", update_params)
            
            logger.info(f"Added call notes to company page")
            return result
        except Exception as e:
            logger.error(f"Error adding call notes: {e}")
            return company_page
    
    async def add_email_notes(
        self, 
        company_page: Dict[str, Any], 
        email_data: Dict[str, Any],
        key_points: List[str]
    ) -> Dict[str, Any]:
        """
        Add email notes to a company page.
        
        Args:
            company_page: Company page data
            email_data: Email data dictionary
            key_points: List of key points from the email
            
        Returns:
            Updated company page data
        """
        if not self.session:
            logger.error("Not connected to Notion MCP server")
            return company_page
        
        page_id = company_page.get("id")
        if not page_id:
            logger.error("Invalid company page: no ID found")
            return company_page
        
        try:
            # Get email metadata
            subject = email_data.get("subject", "No Subject")
            sender = email_data.get("from", "Unknown Sender")
            date = email_data.get("date", datetime.now().isoformat())
            
            # Format as human-readable date if it's an ISO string
            try:
                if "T" in date:
                    date_obj = datetime.fromisoformat(date.replace("Z", "+00:00"))
                    date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass  # Keep original format if parsing fails
            
            # Prepare email notes blocks
            email_blocks = [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": f"Email - {date}"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": f"From: {sender}\nSubject: {subject}"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": "Key points from the email:"}}]
                    }
                }
            ]
            
            # Add key points as bullet points
            for point in key_points:
                email_blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": point}}]
                    }
                })
            
            # Add email body
            email_blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": "Email Content"}}]
                }
            })
            
            body = email_data.get("body", "")
            if body:
                # Split body into paragraphs (Notion has size limits)
                paragraphs = body.split('\n\n')
                for paragraph in paragraphs:
                    if paragraph.strip():
                        # Further chunk long paragraphs
                        if len(paragraph) > 1900:
                            chunks = [paragraph[i:i+1900] for i in range(0, len(paragraph), 1900)]
                            for chunk in chunks:
                                email_blocks.append({
                                    "object": "block",
                                    "type": "paragraph",
                                    "paragraph": {
                                        "rich_text": [{"type": "text", "text": {"content": chunk.strip()}}]
                                    }
                                })
                        else:
                            email_blocks.append({
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [{"type": "text", "text": {"content": paragraph.strip()}}]
                                }
                            })
            
            # Find the "Interactions" heading to append after
            children_params = {
                "block_id": page_id,
                "recursive": False
            }
            
            blocks_result = await self.session.invoke_tool("get_block_children", children_params)
            
            # Look for Interactions heading or append at the end
            append_after_id = None
            for block in blocks_result.get("results", []):
                if block.get("type") == "heading_1":
                    heading_text = block.get("heading_1", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
                    if heading_text == "Interactions":
                        append_after_id = block.get("id")
                        break
            
            # If found, append after that block, otherwise append to the page
            if append_after_id:
                append_params = {
                    "block_id": append_after_id,
                    "children": email_blocks
                }
                await self.session.invoke_tool("append_block_children", append_params)
            else:
                append_params = {
                    "block_id": page_id,
                    "children": email_blocks
                }
                await self.session.invoke_tool("append_block_children", append_params)
            
            # Update page properties based on email content
            properties_update = {}
            
            # Update status if it looks like a response to an application
            if any(kw in body.lower() for kw in ["interview", "schedule", "meet", "discuss"]):
                properties_update["Status"] = {"select": {"name": "Interview"}}
                properties_update["Next Step"] = {"select": {"name": "Prepare"}}
            elif any(kw in body.lower() for kw in ["offer", "compensation", "salary", "package"]):
                properties_update["Status"] = {"select": {"name": "Offer"}}
                properties_update["Next Step"] = {"select": {"name": "Follow Up"}}
            elif any(kw in body.lower() for kw in ["unfortunately", "not moving forward", "other candidates", "not selected"]):
                properties_update["Status"] = {"select": {"name": "Rejected"}}
                properties_update["Next Step"] = {"select": {"name": "Apply"}}
            else:
                # Default update for other emails
                properties_update["Status"] = {"select": {"name": "Applied"}}
                properties_update["Next Step"] = {"select": {"name": "Follow Up"}}
            
            # Only update if we have properties to change
            if properties_update:
                update_params = {
                    "page_id": page_id,
                    "properties": properties_update
                }
                
                result = await self.session.invoke_tool("update_page", update_params)
            else:
                result = company_page
            
            logger.info(f"Added email notes to company page")
            return result
        except Exception as e:
            logger.error(f"Error adding email notes: {e}")
            return company_page