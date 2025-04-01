import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters, stdio_client

logger = logging.getLogger("job-tracker.mcp")

class MCPClient:
    def __init__(self) -> None:
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.server_key = ""  # Derived classes should set this

    async def connect(self) -> bool:
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

        server_config = mcp_config.get("mcpServers", {}).get(self.server_key, {})
        if not server_config:
            logger.error("No MCP configuration for %s found", self.server_key)
            return False

        params = {
            "command": server_config.get("command"),
            "args": server_config.get("args", []),
            "env": server_config.get("env"),
            "cwd": server_config.get("cwd"),
            "encoding": server_config.get("encoding", "utf-8"),
            "encoding_error_handler": server_config.get("encoding_error_handler", "strict"),
        }

        try:
            mcp_params = StdioServerParameters(**params)
            streams_cm = stdio_client(mcp_params)
            transport = await self.exit_stack.enter_async_context(streams_cm)
            read, write = transport
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.session = session
            return True
        except Exception as e:
            logger.error("Error connecting to %s MCP server: %s", self.server_key, e)
            await self.cleanup()
            return False

    async def cleanup(self):
        await self.exit_stack.aclose()
        self.session = None
