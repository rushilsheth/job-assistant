import logging
import json
from typing import Dict, Any, Optional

logger = logging.getLogger("job-tracker.utils")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class JsonUtils:
    @staticmethod
    def to_json(obj):
        """Convert an object to a JSON string."""
        import json
        return json.dumps(obj)

    @staticmethod
    def from_json(json_str):
        """Convert a JSON string to an object."""
        import json
        return json.loads(json_str)
    @staticmethod
    def convert_to_json(raw_text) -> Optional[Dict[str, Any]]:
        """Convert an object to a JSON string."""
        json_start = raw_text.find('{')
        if json_start == -1:
            logger.error("No JSON object found in the search result.")
            return None

        json_text = raw_text[json_start:]
        try:
            page_data = json.loads(json_text)
            return page_data
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error("Error parsing raw text: %s", e)
            return None
