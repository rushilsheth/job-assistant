from datetime import datetime

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