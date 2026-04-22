import json
import logging
from typing import Dict, Any, List


class DisplayConfigHandler:
    """
    Handles display board configuration and data transformation.
    """

    def __init__(self, config_path: str):
        logging.info(
            f"Initializing DisplayConfigHandler with config path: {config_path}")
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(
                f"Failed to load display configuration from {self.config_path}: {e}")
            return {}

    @property
    def source_config(self) -> Dict[str, Any]:
        """Returns the source network configuration."""
        return self.config.get("source", {}).get("connection", {"host": "127.0.0.1", "port": 1234})

    @property
    def pagination_config(self) -> Dict[str, Any]:
        """Returns the pagination settings."""
        return self.config.get("pagination", {})

    @property
    def board_config(self) -> Dict[str, Any]:
        """Returns the physical board dimensions."""
        return self.config.get("hardware", {}).get("board_dimension", {"height": 16, "width": 96})

    @property
    def hardware_config(self) -> Dict[str, Any]:
        """Returns the hardware/display connection configuration."""
        return self.config.get("hardware", {}).get("connection", {"ip": "127.0.0.1", "port": 4422})

    def should_save_to_disk(self, data_type: str) -> bool:
        """Returns True if the message should be saved to disk based on its type."""
        type_cfg = self.config.get("processing", {}).get(
            "rules", {}).get(data_type, {})
        return type_cfg.get("storage", {}).get("save_to_disk", True)

    def should_process_for_display(self, message: Dict[str, Any]) -> bool:
        """Returns True if the message should be processed for display based on its type and filter."""
        data_type = message.get("dataType", "DATA")
        type_cfg = self.config.get("processing", {}).get(
            "rules", {}).get(data_type, {})
        display_cfg = type_cfg.get("display", {})

        # Check if display processing is enabled for this data type
        if not display_cfg.get("enabled", True):
            logging.debug(
                f"Display processing disabled for dataType: {data_type}")
            return False

        # Apply display filter if configured and enabled
        filter_cfg = display_cfg.get("filter")
        if filter_cfg and filter_cfg.get("enabled", False):
            field = filter_cfg.get("field", "display")
            expected_value = filter_cfg.get("value", "True")

            # If the field is missing or does not match the expected value, filter it out
            if message.get(field) != expected_value:
                logging.debug(f"Message filtered out by display filter.")
                return False

        logging.debug(f"Message passed display filter.")
        return True

    def get_display_actions(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Processes a message and returns a list of actions (text)
        based on the configuration.
        """
        data_type = message.get("dataType")
        if not data_type:
            return []

        rules = self.config.get("processing", {}).get(
            "rules", {}).get(data_type, {})
        layout = rules.get("layout", [])

        actions = []
        for rule in layout:
            field_name = rule.get("field")
            value = str(message.get(field_name, ""))
            bib_number = str(message.get("bib", ""))

            # Apply transforms
            transforms = rule.get("transforms", [])
            for transform_name in transforms:
                value = self._apply_transform(transform_name, value, message)

            actions.append({
                "text": value,
                "field": field_name,
                "bib": bib_number
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
        elif name == 'pad_bib_space_4':
            # add spaces to the left until length is 4
            return value.rjust(4)
        elif name == 'pad_bib_space_3':
            # add spaces to the left until length is 3
            return value.rjust(3)
        elif name == 'pad_bib_zero_3':
            # add zeros to the left until length is 4
            return value.zfill(3)
        elif name == 'pad_bib_zero_4':
            # add zeros to the left until length is 4
            return value.zfill(4)
        elif name == 'trim_3':
            # trim to 3 characters
            return value[:3]
        elif name == 'trim_4':
            # trim to 4 characters
            return value[:4]
        elif name == 'trim_5':
            # trim to 5 characters
            return value[:5]
        elif name == 'trim_6':
            # trim to 4 characters
            return value[:6]
        elif name == 'trim_7':
            # trim to 4 characters
            return value[:7]
        elif name == 'to_lower':
            return value.lower()
        elif name == 'to_upper':
            return value.upper()
        elif name == 'capitalize':
            return value.capitalize()

        return value
