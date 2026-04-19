import os
import pprint
import subprocess
import logging
import platform
from pathlib import Path
from importlib import resources
from lap_counter.network.client import TCPClient
from lap_counter.parsing.json_stream import JSONStreamParser
from lap_counter.storage.disk import MessageStore
from lap_counter.display.board import DisplayBoard
from lap_counter.display.config_handler import DisplayConfigHandler
from lap_counter.display.protocols import GraphProtocol
from lap_counter.display.manager import make_display_manager

# Connection defaults
DEFAULT_HOST = "192.168.1.12"
DEFAULT_PORT = 1234
DEFAULT_DISPLAY_IP = "192.168.1.12"
DEFAULT_DISPLAY_PORT = 4422
DEFAULT_PROTOCOL = "graph"


def _default_user_config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        base_dir = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        base_dir = Path(os.environ.get("APPDATA", str(
            Path.home() / "AppData" / "Roaming")))
    else:
        base_dir = Path(os.environ.get(
            "XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base_dir / "lap-counter" / "config.json"


def _bootstrap_user_config(target_path: Path) -> bool:
    try:
        default_content = resources.files("lap_counter.display").joinpath(
            "default_config.json").read_text(encoding="utf-8")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(default_content, encoding="utf-8")
        return True
    except Exception as e:
        logging.error(f"Could not create default config at {target_path}: {e}")
        return False


def resolve_config_path() -> str:
    env_path = os.environ.get("LAP_COUNTER_CONFIG")
    if env_path:
        return env_path

    local_path = Path("config.json")
    if local_path.exists():
        return str(local_path)

    user_path = _default_user_config_path()
    if not user_path.exists() and _bootstrap_user_config(user_path):
        logging.info(f"Created default config at {user_path}")

    if user_path.exists():
        return str(user_path)

    return "config.json"


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def play_sound():
    """Play a short 'bit' sound when data is received and parsed."""
    try:
        if platform.system() == "Darwin":  # macOS
            subprocess.Popen(['afplay', '/System/Library/Sounds/Purr.aiff'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif platform.system() == "Windows":
            import winsound
            winsound.Beep(1000, 100)  # Frequency: 1000Hz, Duration: 100ms
    except Exception:
        pass


def main():
    setup_logging()

    # Initialize components
    config_handler = DisplayConfigHandler(config_path=resolve_config_path())

    # Get configuration with environment variable overrides
    source_cfg = config_handler.source_config
    hw_cfg = config_handler.hardware_config
    # Full hardware block for pagination settings
    hw_block = config_handler.config.get("hardware", {})

    HOST = os.environ.get("TCP_HOST", source_cfg.get("host", DEFAULT_HOST))
    PORT = int(os.environ.get("TCP_PORT", source_cfg.get("port", DEFAULT_PORT)))

    DISPLAY_IP = os.environ.get(
        "DISPLAY_IP", hw_cfg.get("ip", DEFAULT_DISPLAY_IP))
    DISPLAY_PORT = int(os.environ.get(
        "DISPLAY_PORT", hw_cfg.get("port", DEFAULT_DISPLAY_PORT)))

    font_size = os.environ.get(
        "DISPLAY_FONT_SIZE", hw_block.get("rendering", {}).get("font", 1))
    protocol = GraphProtocol(default_font=font_size)

    parser = JSONStreamParser()
    store = MessageStore(directory="output")
    display_board = DisplayBoard(
        ip=DISPLAY_IP, port=DISPLAY_PORT, protocol=protocol)
    display_manager = make_display_manager(
        display_board, config=hw_block)

    try:
        # Connect to the data source
        with TCPClient(HOST, PORT) as client:
            logging.info(f"Listening for data on {HOST}:{PORT}")

            for chunk in client.receive_chunks():
                # Parse JSON messages from the incoming chunks
                for obj in parser.feed(chunk):

                    # Process data (quietly for "inRace" dataType)
                    data_type = obj.get("dataType", "DATA")
                    is_in_race = data_type == "inRace"

                    # Process display updates based on configuration
                    display_actions = config_handler.get_display_actions(
                        obj) if config_handler.should_process_for_display(obj) else []
                    if display_actions:
                        if not is_in_race:
                            logging.info(
                                f">>> {data_type.upper()} DETECTED <<<")

                        should_reset = config_handler.reset_before_send
                        if not is_in_race:
                            for action in display_actions:
                                logging.info(
                                    f"Queueing to DisplayManager: {action} (Row: {action['row']}, Col: {action['col']}, Reset: {should_reset})")
                        try:
                            display_manager.show_message(
                                display_actions, should_reset)
                        except Exception as e:
                            logging.error(
                                f"Failed to queue message to DisplayManager: {e}")
                    elif data_type != "passing" and not is_in_race:
                        logging.info(
                            "Received data (no display rules applied):")
                        pprint.pprint(obj)

                    # Store message on disk
                    if config_handler.should_save_to_disk(data_type):
                        store.save_message(obj)

                    # Feedback sound and separator (suppressed for "inRace")
                    if not is_in_race:
                        play_sound()
                        logging.info("-" * 20)

    except KeyboardInterrupt:
        logging.info("\nMain listener stopped by user.")
    except Exception as e:
        logging.error(f"Major error in main loop: {e}")
    finally:
        if 'display_manager' in locals():
            display_manager.stop()


if __name__ == "__main__":
    main()
