import os
import json
import logging
from datetime import datetime
from typing import Any

class MessageStore:
    """
    Handles saving received messages (JSON objects) to a directory.
    """
    def __init__(self, directory: str = "output"):
        self.directory = directory
        os.makedirs(self.directory, exist_ok=True)
        logging.info(f"Initialized MessageStore at {self.directory}/")

    def save_message(self, message: Any):
        """
        Saves a single JSON object to a timestamped file.
        """
        timestamp = datetime.now().isoformat().replace(':', '-')
        filename = os.path.join(self.directory, f"{timestamp}.json")
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(message, f, indent=4)
            logging.info(f"Saved message to {filename}")
        except Exception as e:
            logging.error(f"Error saving to {filename}: {e}")
            raise
