#!/usr/bin/env python3
"""
Notion MCP client for JobTracker application.
Handles interaction with Notion through the Model Context Protocol.
"""
import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from datetime import datetime
from dotenv import load_dotenv
from typing import Any, Dict, Optional, List

#from openai import OpenAI, pydantic_function_tool
from anthropic import Anthropic

from mcp import ClientSession, StdioServerParameters, stdio_client
from job_tracker.utils import JsonUtils

# configure logging
logger = logging.getLogger("job-tracker.notion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


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
    def __init__(self) -> None:
        self.session = None
        self.exit_stack = AsyncExitStack()

    async def connect(self) -> bool:
        """
        Establish a connection with the MCP server for Notion.
        
        Returns:
            True if the connection is successful, False otherwise.
        """
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../../mcp_config.json"
        )
        try:
            with open(config_path, 'r') as config_file:
                mcp_config = json.load(config_file)
        except Exception as e:
            logger.error("Error reading MCP config: %s", e)
            return False

        notion_config = mcp_config.get("mcpServers", {}).get("notion", {})
        if not notion_config:
            logger.error("No MCP configuration for Notion found in the config file.")
            return False

        # Prepare MCP connection parameters for Notion
        params = {
            "command": notion_config.get("command"),
            "args": notion_config.get("args", []),
            "env": notion_config.get("env"),
            "cwd": notion_config.get("cwd"),
            "encoding": notion_config.get("encoding", "utf-8"),
            "encoding_error_handler": notion_config.get("encoding_error_handler", "strict"),
        }

        try:
            mcp_params = StdioServerParameters(**params)
            # Create the streams and initialize the session
            streams_cm = stdio_client(mcp_params)
            transport = await self.exit_stack.enter_async_context(streams_cm)
            read, write = transport
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.session = session
            return True
        except Exception as e:
            logger.error("Error connecting to Notion MCP server: %s", e)
            await self.cleanup()
            return False

    async def cleanup(self):
        """Cleanup resources associated with the connection."""
        await self.exit_stack.aclose()
        self.session = None

    async def get_page_id(self, company_name: str, timeout: float = 10.0) -> Optional[str]:
        """
        Retrieve the page ID for a given company by searching its name using the Notion API search endpoint.

        Args:
            company_name: The company name to search.
            timeout: Maximum time (in seconds) to wait for a response.

        Returns:
            The page ID if found, or None otherwise.
        """
        if not self.session:
            logger.error("Session is not initialized.")
            return None

        # Prepare the search parameters.
        search_params = {"query": company_name}

        try:
            # Call the tool 'notion_search' which proxies the Notion /search endpoint.
            search_result = await asyncio.wait_for(
                self.session.call_tool("notion_search", search_params), timeout=timeout
            )
            logger.info("Search result: %s", search_result)
        except asyncio.TimeoutError:
            logger.error("Timeout occurred during notion_search for company: %s", company_name)
            return None
        except Exception as e:
            logger.error("Error calling notion_search: %s", e)
            return None

        if not getattr(search_result, "content", None):
            logger.error("No page found for company: %s", company_name)
            return None

        try:
            return search_result.content[0]
        except (KeyError, IndexError) as e:
            logger.error("Error parsing search result: %s", e)
            return None


    async def add_content_to_company_page(self, company_name: str, content: str):
        """
        Adds content to a company's Notion page by:
        1. Finding the page corresponding to the company.
        2. Retrieving existing blocks on that page.
        3. Determining if the content should be appended to existing blocks or added as new blocks.
        4. Updating the page with the new content.
        """

        # Step 1: Find the company's page
        page_id = await self.get_page_id(company_name)
        if not page_id:
            logger.error(f"Page ID not found for company: {company_name}")
            return False
        logger.info(f"Page ID for {company_name}: {page_id}")

        # dynamically add content to company page
        load_dotenv()
        anthropic = Anthropic()
        # Prepare the prompt for the AI model

        initial_prompt = (
            f"Add the following content to the page: {content}. "
            f"The company's page ID is {page_id}. "
            "Decide whether to append this content to an existing section or new one on the page."
        )

        messages = [
            {"role": "user", "content": initial_prompt}]
        logger.info(f"prepping prompt...")
        
        tools_list = await self.session.list_tools() # gotta cache

        tools_serializable = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in tools_list.tools]

        
        logger.info('calling LLM...')
        llm_response = anthropic.messages.create(
            model='claude-3-5-sonnet-20241022',
            messages=messages,
            max_tokens=1000,
            tools=tools_serializable,
        )
        logger.info(f"LLM response: {llm_response}")

        # Process response and handle tool calls
        final_text = []

        while True:
            assistant_message_content = []
            for content in llm_response.content:
                logger.info(f"Processing content: {content}")
                if content.type == 'text':
                    logger.info(f"Adding text content: {content.text}")
                    final_text.append(content.text)
                    assistant_message_content.append(content)

                elif content.type == 'tool_use':
                    tool_name = content.name
                    tool_args = content.input

                    # Execute tool call asynchronously
                    result = await self.session.call_tool(tool_name, tool_args)
                    final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                    assistant_message_content.append(content)

                    # Append assistant's message (including tool_use)
                    messages.append({
                        "role": "assistant",
                        "content": assistant_message_content
                    })

                    # Append tool result
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": result.content
                            }
                        ]
                    })

                    # Call Claude again after tool execution
                    llm_response = anthropic.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1000,
                        messages=messages,
                        tools=tools_serializable
                    )

                    # Break inner loop to process next response
                    break
            else:
                # No tool use found, exit loop
                break

        # Return final accumulated text
        return "\n".join(final_text)

    
    
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
            
            result = await self.session.call_tool("search_notion", search_params)
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
            result = await self.session.call_tool("create_page", page_params)
            
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
            
            blocks_result = await self.session.call_tool("get_block_children", children_params)
            
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
                await self.session.call_tool("append_block_children", append_params)
            else:
                append_params = {
                    "block_id": page_id,
                    "children": call_blocks
                }
                await self.session.call_tool("append_block_children", append_params)
            
            # Update page properties
            properties_update = {
                "Status": {"select": {"name": "Interview"}},
                "Next Step": {"select": {"name": "Follow Up"}}
            }
            
            update_params = {
                "page_id": page_id,
                "properties": properties_update
            }
            
            result = await self.session.call_tool("update_page", update_params)
            
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
            
            blocks_result = await self.session.call_tool("get_block_children", children_params)
            
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
                await self.session.call_tool("append_block_children", append_params)
            else:
                append_params = {
                    "block_id": page_id,
                    "children": email_blocks
                }
                await self.session.call_tool("append_block_children", append_params)
            
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
                
                result = await self.session.call_tool("update_page", update_params)
            else:
                result = company_page
            
            logger.info(f"Added email notes to company page")
            return result
        except Exception as e:
            logger.error(f"Error adding email notes: {e}")
            return company_page