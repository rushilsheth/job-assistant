#!/bin/bash
# Installation script for JobTracker MCP using Poetry

# Set colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}JobTracker MCP Installation (Poetry Version)${NC}"
echo "================================="
echo "This script will set up the JobTracker MCP application using Poetry."
echo ""

# Check for Python
echo -e "${YELLOW}Checking for Python 3.8+...${NC}"
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

    if [[ "$PYTHON_MAJOR" -gt 3 ]] || ([[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -ge 8 ]]); then
        echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"
        PYTHON=python3
    else
        echo -e "${RED}✗ Python $PYTHON_VERSION found, but 3.8+ is required${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi

# Check for Poetry
echo -e "${YELLOW}Checking for Poetry...${NC}"
if command -v poetry &>/dev/null; then
    POETRY_VERSION=$(poetry --version | cut -d' ' -f3)
    echo -e "${GREEN}✓ Poetry $POETRY_VERSION found${NC}"
else
    echo -e "${YELLOW}Poetry not found. Installing Poetry...${NC}"
    curl -sSL https://install.python-poetry.org | $PYTHON -
    export PATH="$HOME/.local/bin:$PATH"
fi

# Install project dependencies
echo -e "${YELLOW}Installing project dependencies with Poetry...${NC}"
poetry install

# Check for npm
echo -e "${YELLOW}Checking for npm...${NC}"
if command -v npm &>/dev/null; then
    NPM_VERSION=$(npm --version)
    echo -e "${GREEN}✓ npm $NPM_VERSION found${NC}"
else
    echo -e "${RED}✗ npm not found${NC}"
    exit 1
fi

# Handle npm permissions interactively
echo -e "${YELLOW}Checking npm global permissions...${NC}"
if ! npm config get prefix | grep -q "$HOME/.npm-global"; then
    echo -e "${YELLOW}Your npm global directory might require root permissions.${NC}"
    echo -e "${YELLOW}Would you like to configure npm to use your home directory instead? (recommended) (y/n)${NC}"
    read -r configure_npm
    if [[ $configure_npm =~ ^[Yy]$ ]]; then
        mkdir -p ~/.npm-global
        npm config set prefix '~/.npm-global'
        if ! grep -q 'npm-global/bin' ~/.bash_profile; then
            echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bash_profile
            source ~/.bash_profile
            echo -e "${GREEN}✓ npm global configuration updated successfully.${NC}"
        else
            echo -e "${YELLOW}⚠ npm global configuration already present, skipping.${NC}"
        fi
    fi
fi

# Check for git
echo -e "${YELLOW}Checking for git...${NC}"
if command -v git &>/dev/null; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    echo -e "${GREEN}✓ git $GIT_VERSION found${NC}"
else
    echo -e "${RED}✗ git not found${NC}"
    echo -e "${YELLOW}Please install git before continuing.${NC}"
    exit 1
fi

# Create .env file template first
echo -e "${YELLOW}Creating .env file template...${NC}"
if [ ! -f .env ]; then
    cat > .env << EOF
# Notion Configuration (REQUIRED)
NOTION_API_TOKEN=  # REQUIRED: Your Notion API token
NOTION_PAGE_ID=  # Optional: Parent page ID

# Gmail Configuration (REQUIRED)
GMAIL_MCP_PATH=@gongrzhe/server-gmail-autoauth-mcp
GMAIL_CREDENTIALS_PATH=  # REQUIRED: Path to your Gmail credentials.json

# Audio Configuration (REQUIRED)
AUDIO_MCP_PATH=  # REQUIRED: Path to audio_server.py
WHISPER_MODEL=small  # Options: tiny, base, small, medium, large
EOF
    echo -e "${GREEN}✓ .env template created${NC}"
    echo -e "${YELLOW}⚠ WARNING: You must edit the .env file to set required values before using the application!${NC}"
else
    echo -e "${YELLOW}⚠ .env file already exists, skipping${NC}"
fi

# Install MCP servers
echo -e "${YELLOW}Would you like to install the MCP servers now? (y/n)${NC}"
read -r install_servers
if [[ $install_servers =~ ^[Yy]$ ]]; then
    # Install the Gmail MCP Server
    echo -e "${YELLOW}Installing Gmail MCP Server...${NC}"
    npm install -g @gongrzhe/server-gmail-autoauth-mcp
    
    # Set up directory for mcp-notion-server
    NOTION_INSTALL_DIR="mcp-notion-server"
    echo -e "${YELLOW}Setting up Notion MCP installation directory: ${NOTION_INSTALL_DIR}${NC}"

    if [ -d "$NOTION_INSTALL_DIR" ]; then
        echo -e "${YELLOW}Directory already exists. Would you like to remove it and reinstall? (y/n)${NC}"
        read -r reinstall
        if [[ $reinstall =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Removing existing directory...${NC}"
            rm -rf "$NOTION_INSTALL_DIR"
        fi
    fi

    # Clone and build the Notion MCP server if needed
    if [ ! -d "$NOTION_INSTALL_DIR" ]; then
        echo -e "${YELLOW}Cloning mcp-notion-server repository...${NC}"
        git clone https://github.com/suekou/mcp-notion-server.git "$NOTION_INSTALL_DIR"
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to clone repository.${NC}"
            exit 1
        fi
        
        # Build the Notion MCP server
        cd "$NOTION_INSTALL_DIR"
        
        # Check if there's a package.json at the root
        if [ -f "package.json" ]; then
            echo -e "${YELLOW}Installing dependencies at root level...${NC}"
            npm install
            npm run build
            NOTION_BUILD_PATH="$(pwd)/build/index.js"
        else
            # If no root package.json, check for a notion directory
            if [ -d "notion" ]; then
                echo -e "${YELLOW}Found notion directory, checking for package.json...${NC}"
                cd notion
                if [ -f "package.json" ]; then
                    echo -e "${YELLOW}Installing dependencies in notion directory...${NC}"
                    npm install
                    npm run build
                    NOTION_BUILD_PATH="$(pwd)/build/index.js"
                else
                    echo -e "${RED}No package.json found in notion directory.${NC}"
                    cd ..
                    exit 1
                fi
                cd ..
            else
                echo -e "${RED}No package.json found at root and no notion directory found.${NC}"
                echo -e "${YELLOW}Manually checking the repository structure...${NC}"
                find . -name "package.json" -type f | sort
                echo -e "${RED}Please inspect the repository structure and modify this script accordingly.${NC}"
                cd ..
                exit 1
            fi
        fi
        
        cd ..
    else
        echo -e "${YELLOW}Using existing mcp-notion-server installation.${NC}"
        cd "$NOTION_INSTALL_DIR"
        
        # Determine the path to the built index.js file
        if [ -f "build/index.js" ]; then
            NOTION_BUILD_PATH="$(pwd)/build/index.js"
        elif [ -f "notion/build/index.js" ]; then
            NOTION_BUILD_PATH="$(pwd)/notion/build/index.js"
        else
            echo -e "${RED}Could not find built index.js file. Try reinstalling.${NC}"
            cd ..
            exit 1
        fi
        
        cd ..
    fi
    
    echo -e "${YELLOW}Notion MCP server build path: ${NOTION_BUILD_PATH}${NC}"
    
    echo -e "${YELLOW}Cloning Audio MCP Server...${NC}"
    git clone https://github.com/GongRzhe/Audio-MCP-Server.git
    cd Audio-MCP-Server
    poetry run pip install -r requirements.txt
    AUDIO_SERVER_PATH="$(pwd)/audio_server.py"
    cd ..
    
    # Update .env with the Audio server path
    if [ -f .env ]; then
        sed -i.bak "s|^AUDIO_MCP_PATH=.*|AUDIO_MCP_PATH=$AUDIO_SERVER_PATH|" .env
        echo -e "${GREEN}✓ Updated .env with Audio MCP Server path${NC}"
    fi
    
    echo -e "${GREEN}✓ MCP servers installed${NC}"
    
    # Generate mcp_config.json from .env (if .env exists)
    echo -e "${YELLOW}Generating MCP configuration file from .env...${NC}"
    if [ -f .env ] && [ ! -f mcp_config.json ]; then
        # Source the .env file
        set -o allexport
        source .env
        set +o allexport
        
        # Create mcp_config.json based on .env values
        cat > mcp_config.json << EOF
{
  "mcpServers": {
    "notion": {
      "command": "node",
      "args": ["${NOTION_BUILD_PATH}"],
      "env": {
        "NOTION_API_TOKEN": "${NOTION_API_TOKEN:-YOUR_NOTION_TOKEN}",
        "NOTION_PAGE_ID": "${NOTION_PAGE_ID:-YOUR_NOTION_PAGE_ID}",
        "NOTION_MARKDOWN_CONVERSION": "true"
      }
    },
    "gmail": {
      "command": "npx",
      "args": [
        "${GMAIL_MCP_PATH:-@gongrzhe/server-gmail-autoauth-mcp}"
      ],
      "env": {
        "GMAIL_CREDENTIALS_PATH": "${GMAIL_CREDENTIALS_PATH:-/path/to/gmail-server/credentials.json}"
      }
    },
    "audio": {
      "command": "poetry",
      "args": [
        "run",
        "python",
        "${AUDIO_MCP_PATH:-/path/to/your/audio_server.py}"
      ],
      "env": {
        "PYTHONPATH": "$(dirname "${AUDIO_MCP_PATH:-/path/to/your/audio_server.py}")"
      }
    }
  }
}
EOF
        echo -e "${GREEN}✓ MCP configuration generated from .env${NC}"
        
        # Check for missing required values
        MISSING_VALUES=false
        if [ -z "$NOTION_API_TOKEN" ]; then
            echo -e "${RED}⚠ NOTION_API_TOKEN is not set in .env${NC}"
            MISSING_VALUES=true
        fi
        if [ -z "$GMAIL_CREDENTIALS_PATH" ]; then
            echo -e "${RED}⚠ GMAIL_CREDENTIALS_PATH is not set in .env${NC}"
            MISSING_VALUES=true
        fi
        if [ -z "$AUDIO_MCP_PATH" ]; then
            echo -e "${RED}⚠ AUDIO_MCP_PATH is not set in .env${NC}"
            MISSING_VALUES=true
        fi
        
        if [ "$MISSING_VALUES" = true ]; then
            echo -e "${YELLOW}⚠ Some required values are missing in .env. Please edit the file before using the application.${NC}"
        fi
    else
        if [ ! -f .env ]; then
            echo -e "${RED}⚠ .env file not found, cannot generate mcp_config.json${NC}"
        elif [ -f mcp_config.json ]; then
            echo -e "${YELLOW}⚠ mcp_config.json already exists, skipping${NC}"
        fi
    fi
fi

# Create script to run the app with Poetry
echo -e "${YELLOW}Creating convenience script...${NC}"
cat > run-tracker.sh << EOF
#!/bin/bash
# Run JobTracker with Poetry

# Activate Poetry environment and run the app
poetry run job-tracker "\$@"
EOF
chmod +x run-tracker.sh
echo -e "${GREEN}✓ Convenience script created (./run-tracker.sh)${NC}"

# Create script to run mcp-notion-server
echo -e "${YELLOW}Creating script to run Notion MCP server...${NC}"
cat > run-notion-server.sh << EOF
#!/bin/bash
# Run Notion MCP Server

# Set your Notion API token here (or it will use the one from .env)
if [ -z "\$NOTION_API_TOKEN" ] && [ -f .env ]; then
    source .env
fi

if [ -z "\$NOTION_API_TOKEN" ]; then
    echo "Error: NOTION_API_TOKEN environment variable is not set."
    echo "Either set it in this script, export it before running, or set NOTION_API_TOKEN in .env file."
    exit 1
fi

# Path to the built index.js file
NOTION_INDEX_PATH="${NOTION_BUILD_PATH}"

# Run the server
echo "Starting Notion MCP server..."
node "\$NOTION_INDEX_PATH"
EOF
chmod +x run-notion-server.sh
echo -e "${GREEN}✓ Convenience script created (./run-notion-server.sh)${NC}"

echo ""
echo -e "${GREEN}Installation completed!${NC}"
echo "--------------------------------"
echo "Next steps:"
echo "1. Edit the .env file to set REQUIRED values:"
echo "   - NOTION_API_TOKEN (from Notion Integrations page)"
echo "   - GMAIL_CREDENTIALS_PATH (path to your Google credentials.json)"
echo "   - Ensure AUDIO_MCP_PATH is set correctly"
echo "2. Run the application using Poetry:"
echo "   poetry run job-tracker"
echo "   or use the convenience script:"
echo "   ./run-tracker.sh"
echo ""
echo "3. To run the Notion MCP server separately, use:"
echo "   ./run-notion-server.sh"
echo ""
echo "To activate the Poetry environment shell, run:"
echo "poetry shell"
echo ""
echo "Thank you for installing JobTracker MCP!"