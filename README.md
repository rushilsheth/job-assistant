# JobTracker MCP

A job search tracking application that uses the Model Context Protocol (MCP) to integrate with Notion and Gmail. This tool helps you manage your job search by automatically capturing audio from interviews, processing emails, and organizing everything in Notion.

## Features

- **Audio Recording & Transcription**: Capture audio from interviews and video calls
- **Email Processing**: Extract job-related information from emails
- **Notion Integration**: Add to content from audio or email to correct page
- **State Management**: Track your job search progress

## Prerequisites

- Python 3.8 or higher
- Poetry (dependency management)
- Node.js and npm (for MCP servers)
- Notion account with API access
- Gmail account with API access
- MCP servers:
  - [Notion MCP Server](https://github.com/suekou/mcp-notion-server)
  - [Gmail MCP Server](https://github.com/GongRzhe/Gmail-MCP-Server)
  - [Audio MCP Server](https://github.com/GongRzhe/Audio-MCP-Server)

## Toy Example

<video src="artifacts/fake_transcript_notion.mov" width="320" height="240" controls></video>



## Setup

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/job-tracker-mcp.git
cd job-tracker-mcp
```

2. **Run the installation script**

Make the installation script executable and run it:

```bash
chmod +x install.sh
make install
```

The script will:
- Check for Poetry and install it if needed
- Install project dependencies using Poetry
- Set up MCP servers (optional)
- Create configuration templates

3. **Configure environment variables**

Edit the `.env` file created by the installation script:

```env
# Notion Configuration
NOTION_MCP_PATH=mcp-notion-server
NOTION_WORKSPACE_ID=your_workspace_id
NOTION_DATABASE_ID=your_database_id  # Optional, will create one if not provided

# Gmail Configuration
GMAIL_MCP_PATH=@gongrzhe/server-gmail-autoauth-mcp

# Audio Configuration
AUDIO_MCP_PATH=audio-mcp-server
WHISPER_MODEL=small  # Options: tiny, base, small, medium, large
```

## Usage

Run the application using Poetry:

```bash
# Using Poetry run command
poetry run job-tracker call --help

# Or with the convenience script
./run-tracker.sh call --help
```

### Recording a call

```bash
poetry run job-tracker call /path/to/audio_file.mp3 --company "Example Company"
```

If you want to record directly:

```bash
poetry run job-tracker call --record 60 --company "Example Company"
```

This will record for 60 seconds, transcribe the audio, and add the notes to the company's Notion page.

### Processing an email

```bash
poetry run job-tracker email --id "email_id" --company "Example Company"
```

or

```bash
poetry run job-tracker email --company "Example Company"
```

This will search for recent emails related to the company and process the most recent one.

### Add Company Content

```bash
poetry run job-tracker add-content "COMPANY NAME" --email email_id
```

### Checking company status

```bash
poetry run job-tracker status "Company Name"
```

## Project Structure

```
job-tracker-mcp/
├── src/
│   └── job_tracker/
│       ├── __init__.py
│       ├── main.py          # Main application
│       ├── notion_client.py # Notion integration
│       ├── gmail_client.py  # Gmail integration
│       ├── audio_proc.py    # Audio processing
│       └── state.py         # State management
├── .env                     # Environment variables
├── pyproject.toml           # Poetry configuration
├── mcp_config.json          # MCP servers configuration
├── install.sh               # Installation script
├── run-tracker.sh           # Convenience script
└── README.md                # This file
```

## How It Works

1. **Recording Interview Calls**:
   - The Audio MCP Server captures audio from your microphone during video calls
   - The audio is transcribed using OpenAI's Whisper model
   - Key points are extracted from the transcript
   - A new entry is added to the company's Notion page

2. **Processing Emails**:
   - The Gmail MCP Server fetches emails related to your job search
   - Key information is extracted from emails
   - The information is added to the company's Notion page
   - Application status is updated based on email content

3. **Organizing in Notion**:
   - Company pages are created in a "Job Applications" database
   - Each company page includes sections for calls, emails, and notes
   - Application status is tracked (Not Applied, Applied, Interview, Offer, Rejected)
   - Next steps are automatically suggested

4. **State Management**:
   - Local state tracks your job search progress
   - Statistics on applications, interviews, and offers are maintained
   - Historical interaction data is stored for reference