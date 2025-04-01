import asyncio
import logging
from job_tracker.notion_client import NotionClient

# Configure the root logger to display INFO level logs from all modules
logging.getLogger().setLevel(logging.INFO)

async def main():
    client = NotionClient()
    print("Connecting to Notion client...")
    connected = await client.connect()
    if not connected:
        print("Failed to connect.")
        return
    print("Connected to Notion client.")

    company_name = "Acme Org"
    content = "I spoke with the manager, Zyra, and decided was informed on next steps. I will have a 3 hour tech assessment in both ML and coding."

    try:
        print("Uploading content page ID...")
        success = await client.add_content_to_company_page(company_name, content)
        if success:
            print(f"Updated page for {company_name} with content: {content}")
        else:
            print("Page ID not found.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.cleanup()
        print("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
