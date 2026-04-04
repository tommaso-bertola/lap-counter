import json
import logging
from typing import Dict, Any, List

class DisplayConfigHandler:
    """
    Handles display board configuration and data transformation.
    """
    def __init__(self, config_path: str):
        logging.info(f"Initializing DisplayConfigHandler with config path: {config_path}")
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load display configuration from {self.config_path}: {e}")
            return {}

    @property
    def reset_before_send(self) -> bool:
        """Returns True if the display should be reset before sending new data."""
        return self.config.get("display", {}).get("settings", {}).get("reset_before_send", True)

    @property
    def network_config(self) -> Dict[str, Any]:
        """Returns the network configuration."""
        return self.config.get("network", {"host": "127.0.0.1", "port": 1234})

    @property
    def display_config(self) -> Dict[str, Any]:
        """Returns the display configuration."""
        return self.config.get("display", {"ip": "127.0.0.1", "port": 4422})

    def should_save_to_disk(self, data_type: str) -> bool:
        """Returns True if the message should be saved to disk based on its type."""
        settings_key = f"{data_type}_settings"
        return self.config.get(settings_key, {}).get("save_to_disk", True)

    def should_process_for_display(self, data_type: str) -> bool:
        """Returns True if the message should be processed for display based on its type."""
        settings_key = f"{data_type}_settings"
        return self.config.get(settings_key, {}).get("process_for_display", True)

    def get_display_actions(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Processes a message and returns a list of actions (text, row, col)
        based on the configuration.
        """
        data_type = message.get("dataType")
        if not data_type or data_type not in self.config:
            return []

        actions = []
        rules = self.config[data_type]
        
        for rule in rules:
            field_name = rule.get("field")
            value = str(message.get(field_name, ""))
            
            # Apply transforms
            transforms = rule.get("transforms", [])
            for transform_name in transforms:
                value = self._apply_transform(transform_name, value, message)
            
            actions.append({
                "text": value,
                "row": rule.get("row", "A"),
                "col": rule.get("col", 0)
            })
            
        return actions

    def _apply_transform(self, name: str, value: str, message: Dict[str, Any]) -> str:
        """
        Applies a predefined transformation to a field value.
        """
        if name == "strip_bib_prefix":
            return value.replace("BIB:", "").strip()
        
        elif name == "append_mod_if_no_entra":
            mod = str(message.get("Mod", ""))
            # If the msg field does not contain "<-Entra", append the Mod value
            if "<-Entra" not in value:
                return f"{value} {mod}".strip()
            return value
        
        elif name == "do_not_transform":
            return value
        
        elif name=='pad_bib_space':
            # add spaces to the left until length is 4
            return value.rjust(4)
        elif name=='pad_bib_zero':
            # add zeros to the left until length is 4
            return value.zfill(4)
            
        return value
