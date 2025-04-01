#!/usr/bin/env python3
"""
Notion MCP client for JobTracker application.
Handles interaction with Notion through the Model Context Protocol.
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from typing import Any, Dict, Optional, List

#from openai import OpenAI, pydantic_function_tool
from anthropic import Anthropic

from mcp import StdioServerParameters, stdio_client, ClientSession
from job_tracker.mcp_client import MCPClient

# configure logging
logger = logging.getLogger("job-tracker.notion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class NotionClient(MCPClient):
    def __init__(self) -> None:
        super().__init__()
        self.server_key = "notion"

    async def get_company_page_id(self, company_name: str, timeout: float = 10.0) -> Optional[str]:
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
    
    async def get_or_create_company(self, company_name: str) -> Dict[str, Any]:
        """
        Get an existing company page or create a new one.
        
        Args:
            company_name: Name of the company
            
        Returns:
            Company page data
        """
        pass

    async def dynamic_append_content(self, page_id: str, text_content: str) -> str:
        """
        Helper to dynamically append content via an LLM call.

        Args:
            page_id: The ID of the Notion page.
            text_content: The content to append.

        Returns:
            The final accumulated text.
        """
        load_dotenv()
        anthropic = Anthropic()
        prompt = (
            f"Add the following content to the page: {text_content}. "
            f"The company's page ID is {page_id}. "
            "Decide whether to append this content to an existing section or new one on the page."
        )
        messages = [{"role": "user", "content": prompt}]
        tools_list = await self.session.list_tools()  # cache tools
        tools_serializable = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in tools_list.tools]
        llm_response = anthropic.messages.create(
            model='claude-3-5-sonnet-20241022',
            messages=messages,
            max_tokens=1000,
            tools=tools_serializable,
        )
        final_text = []
        while True:
            assistant_message_content = []
            for content in llm_response.content:
                if content.type == 'text':
                    final_text.append(content.text)
                    assistant_message_content.append(content)
                elif content.type == 'tool_use':
                    tool_name = content.name
                    tool_args = content.input
                    result = await self.session.call_tool(tool_name, tool_args)
                    final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                    
                    # Append assistant's message (including tool_use)
                    assistant_message_content.append(content)                   

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
        return "\n".join(final_text)

    async def add_content_to_company_page(self, company_name: str, content: str):
        """
        Adds content to a company's Notion page.

        Args:
            company_name: Name of the company.
            content: Content to add.

        Returns:
            The result text from the dynamic append operation.
        """
        page_id = await self.get_company_page_id(company_name)
        if not page_id:
            logger.error(f"Page ID not found for company: {company_name}")
            return False
        logger.info(f"Page ID for {company_name}: {page_id}")
        result_text = await self.dynamic_append_content(page_id, content)
        return result_text

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
            Updated company page data.
        """
        if not self.session:
            logger.error("Not connected to Notion MCP server")
            return company_page
        page_id = company_page.get("id")
        if not page_id:
            logger.error("Invalid company page: no ID found")
            return company_page
        # Preprocess call notes into a single text blob.
        notes_text = f"Call Notes - {call_date}\nKey Points:\n"
        for point in key_points:
            notes_text += f"- {point}\n"
        notes_text += "\nTranscript:\n" + transcript.strip()
        llm_result = await self.dynamic_append_content(page_id, notes_text)
        logger.info("Added call notes to company page")
        return llm_result

    async def add_email_notes(
        self, 
        company_page: Dict[str, Any], 
        email_data: Dict[str, Any],
        key_points: List[str]
    ) -> Dict[str, Any]:
        """
        Add email notes to a company page.

        Args:
            company_page: Company page data.
            email_data: Email data dictionary.
            key_points: List of key points from the email.

        Returns:
            Updated company page data.
        """
        if not self.session:
            logger.error("Not connected to Notion MCP server")
            return company_page
        page_id = company_page.get("id")
        if not page_id:
            logger.error("Invalid company page: no ID found")
            return company_page
        # Preprocess email data into a single text blob.
        subject = email_data.get("subject", "No Subject")
        sender = email_data.get("from", "Unknown Sender")
        date = email_data.get("date", datetime.now().isoformat())
        try:
            if "T" in date:
                date_obj = datetime.fromisoformat(date.replace("Z", "+00:00"))
                date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
        notes_text = f"Email - {date}\nFrom: {sender}\nSubject: {subject}\nKey Points:\n"
        for point in key_points:
            notes_text += f"- {point}\n"
        notes_text += "\nEmail Content:\n" + email_data.get("body", "").strip()
        llm_result = await self.dynamic_append_content(page_id, notes_text)
        # TODO: any properties to update?
        return llm_result