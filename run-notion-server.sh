#!/bin/bash
# Run Notion MCP Server

# Set your Notion API token here (or it will use the one from .env)
if [ -f .env ]; then
    # Source the .env file
    source .env
    
    # If NOTION_API_KEY is set but NOTION_API_TOKEN is not, use NOTION_API_KEY
    if [ -n "$NOTION_API_KEY" ] && [ -z "$NOTION_API_TOKEN" ]; then
        export NOTION_API_TOKEN="$NOTION_API_KEY"
        echo "Using NOTION_API_KEY as NOTION_API_TOKEN."
    fi
fi

# Explicitly check if NOTION_API_TOKEN is set now
if [ -z "$NOTION_API_TOKEN" ]; then
    echo "Error: NOTION_API_TOKEN environment variable is not set."
    echo "Either set it in this script, export it before running, or set NOTION_API_TOKEN in .env file."
    exit 1
fi

# Debug output
echo "Using NOTION_API_TOKEN: ${NOTION_API_TOKEN:0:5}..."

# Path to the built index.js file
NOTION_INDEX_PATH="/Users/rushilsheth/Documents/portfolio/job-tracker-mcp/mcp-notion-server/notion/build/index.js"

# Verify the file exists
if [ ! -f "$NOTION_INDEX_PATH" ]; then
    echo "Error: The file at $NOTION_INDEX_PATH does not exist."
    echo "Please ensure the Notion MCP server has been built correctly."
    exit 1
fi

# Run the server
echo "Starting Notion MCP server..."
NOTION_API_TOKEN="$NOTION_API_TOKEN" node "$NOTION_INDEX_PATH"