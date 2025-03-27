# JobTracker MCP - Usage Guide

This guide provides detailed examples for using the JobTracker MCP application.

## Table of Contents

- [Setting Up](#setting-up)
- [Recording Call Audio](#recording-call-audio)
- [Processing Audio Files](#processing-audio-files)
- [Working with Emails](#working-with-emails)
- [Managing Companies](#managing-companies)
- [Tips and Best Practices](#tips-and-best-practices)

## Setting Up

Before using JobTracker, make sure you have properly configured your `.env` file and have the MCP servers running.

```
# Notion Configuration
NOTION_MCP_PATH=notion-mcp-server
NOTION_API_KEY=secret_abcd123...
NOTION_PAGE_ID=abcd1234...      # Optional, parent page ID

# Gmail Configuration
GMAIL_MCP_PATH=@gongrzhe/server-gmail-autoauth-mcp
GMAIL_CREDENTIALS_PATH=/path/to/credentials.json

# Audio Configuration
AUDIO_MCP_PATH=/path/to/Audio-MCP-Server/audio_server.py
WHISPER_MODEL=small  # Options: tiny, base, small, medium, large
```

**Notion API Key:** 
1. Go to [Notion Integrations page](https://www.notion.so/my-integrations) and create integration and get API Key
2. Create a page where you want to track job applications
3. Click "Share" in the top right
4. Under "Add connections", find and select your integration
5. Copy the page URL - the part after the last slash before the question mark is your NOTION_PAGE_ID (optional)

**Gmail Key:** 
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. **Create a new project**
3. Enable the [Gmail API](https://console.cloud.google.com/marketplace/product/google/gmail.googleapis.com?q=search&invt=AbtGjQ&project=dncpoc-326015)
4. Set up OAuth consent screen:
- Go to "APIs & Services" > "OAuth consent screen"
- Choose "External" user type
- Fill in the required information
- Add the Gmail API scope https://www.googleapis.com/auth/gmail.modify
- Add yourself as a test user
5. Create OAuth credentials:
- Go to "APIs & Services" > "Credentials"
- Click "Create Credentials" > "OAuth client ID"
- Select "Desktop application"
- Download the JSON file
- Rename it to credentials.json
- Save it to a secure location
- Set GMAIL_CREDENTIALS_PATH to this file's path

### Running MCP Servers

You can run the MCP servers manually or use a tool like `pm2` to manage them:

```bash
# Start Notion MCP server
npx notion-mcp-server

# Start Gmail MCP server
npx @gongrzhe/server-gmail-autoauth-mcp

# Start Audio MCP server
cd Audio-MCP-Server
python audio_server.py
```

Or using pm2 (for persistent servers):

```bash
# Install pm2
npm install -g pm2

# Start all servers
pm2 start npx -- notion-mcp-server
pm2 start npx -- @gongrzhe/server-gmail-autoauth-mcp
pm2 start python -- /path/to/Audio-MCP-Server/audio_server.py

# Save configuration
pm2 save

# Set pm2 to start on boot
pm2 startup
```

## Recording Call Audio

### Recording a Live Call

To record a call in real-time:

```bash
# Record for 30 minutes (1800 seconds)
job-tracker call --record 1800 --company "Acme Corp"
```

This will:
1. Start recording audio from your default microphone
2. Transcribe the recording once complete
3. Extract key points from the conversation
4. Create or update the Acme Corp page in Notion
5. Add the call notes with transcript

### Tips for Recording

1. Test your microphone before important calls
2. Use a headset for better audio quality
3. Try to reduce background noise
4. For long interviews, you can set a longer duration

```bash
# List available audio devices
job-tracker call --list-devices

# Record from a specific device
job-tracker call --record 1800 --device "Built-in Microphone" --company "Acme Corp"
```

## Processing Audio Files

If you already have a recording (e.g., from another call recording tool), you can process it directly:

```bash
# Process an existing audio file
job-tracker call /path/to/interview.mp3 --company "Acme Corp"
```

The tool will:
1. Transcribe the audio file
2. Extract key points
3. Update the company page in Notion

You can also process audio without specifying a company name, and the tool will attempt to extract the company name from the conversation:

```bash
job-tracker call /path/to/interview.mp3
```

## Working with Emails

### Processing Recent Emails

To process the most recent email from a specific company:

```bash
job-tracker email --company "Acme Corp"
```

This will search your Gmail for recent emails related to Acme Corp, process the most recent one, and update the Notion page.

### Processing a Specific Email

If you have a specific email ID (from Gmail):

```bash
job-tracker email --id "18abc123def456" --company "Acme Corp"
```

### Email Search Patterns

The tool uses certain patterns to identify job-related emails:

- Interview invitations
- Application confirmations
- Follow-up emails
- Rejection notices
- Offer letters

You can see what keywords are used by checking the `job_keywords` list in `gmail_client.py`.

## Managing Companies

### Searching for Companies

To search for companies in your Notion database:

```bash
job-tracker search "Acme"
```

This will return all companies with "Acme" in their name, along with their Notion page URLs.

### Checking Company Status

To see the current status of your application with a company:

```bash
job-tracker status "Acme Corp"
```

This will show:
- Notion page link
- Application status
- Last interaction type and date
- Next steps

## Tips and Best Practices

### Preparation Before Calls

1. **Set up the recorder before the call**:
   ```bash
   job-tracker call --list-devices
   ```
   Identify the right microphone to use.

2. **Test audio quality**:
   ```bash
   job-tracker call --record 10 --test
   ```
   This will record 10 seconds and play it back to check quality.

### Organizing Your Job Search

1. **Weekly summary**:
   ```bash
   job-tracker summary --period week
   ```
   Shows stats on applications, interviews, and progress for the week.

2. **Prioritizing follow-ups**:
   ```bash
   job-tracker followup
   ```
   Lists companies that need follow-up actions, sorted by priority.

### Transcription Quality

For better transcription quality:
- Use Whisper medium or large model by setting `WHISPER_MODEL=medium` in your `.env` file
- Ensure good audio quality with minimal background noise
- Speak clearly during the interview

### Backup Your Data

Regularly backup your state file:
```bash
cp ~/.job-tracker/state.json ~/.job-tracker/state.json.backup.$(date +%Y%m%d)
```

## Troubleshooting

### Common Issues

1. **Connection to MCP server failed**:
   - Make sure the MCP servers are running
   - Check server paths in the `.env` file
   - Verify authentication for Notion and Gmail

2. **Audio recording issues**:
   - Check microphone permissions
   - Try listing available devices and select a different one
   - Ensure the Audio MCP server is running

3. **Gmail authentication**:
   - Follow the OAuth setup process for Gmail
   - Check the credential files are in the right location
   - Ensure GMAIL_CREDENTIALS_PATH is correctly set

4. **Notion integration issues**:
   - Verify your Notion token has the right permissions
   - Ensure the integration is added to your workspace
   - Check database creation permissions

For more help, check the logs at `~/.job-tracker/logs/` or run commands with the `--verbose` flag.