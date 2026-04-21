import argparse
import os
import pprint
import subprocess
import logging
import platform
import time
from pathlib import Path
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lap counter listener")
    parser.add_argument(
        "--config",
        dest="config_path",
        help="Path to the config JSON file. If omitted, ./config.json is used.",
    )
    return parser.parse_args()


def resolve_config_path(config_path_arg: str | None) -> tuple[str, str]:
    if config_path_arg:
        config_path = Path(config_path_arg).expanduser()
        source = "--config argument"
    else:
        config_path = Path("config.json")
        source = "current working directory"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}. "
            "Use --config /path/to/config.json or place config.json in the current working directory."
        )

    config_path = config_path.resolve()

    return str(config_path), source


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

    args = parse_args()

    try:
        config_path, config_source = resolve_config_path(args.config_path)
    except FileNotFoundError as e:
        logging.error(str(e))
        return

    print(f"Loaded config (absolute path): {config_path}")
    logging.info(f"Using configuration from {config_source}: {config_path}")

    # Initialize components
    config_handler = DisplayConfigHandler(config_path=config_path)

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
    board_dim = config_handler.board_config
    protocol = GraphProtocol(
        default_font=font_size,
        width=board_dim.get("width", 96),
        height=board_dim.get("height", 16)
    )

    parser = JSONStreamParser()
    store = MessageStore(directory="output")
    display_board = DisplayBoard(
        ip=DISPLAY_IP, port=DISPLAY_PORT, protocol=protocol)
    display_manager = make_display_manager(
        display_board, config=hw_block)

    while True:
        try:
            # Connect to the data source
            with TCPClient(HOST, PORT) as client:
                logging.info(f"Connected to data source at {HOST}:{PORT}")

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
                                        f"Queueing to DisplayManager: {action} (Reset: {should_reset})")
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
            break
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            logging.info("Attempting to reconnect in 5 seconds...")
            time.sleep(5)
        finally:
            if 'display_manager' in locals():
                # We don't necessarily want to stop the display manager on every disconnect
                # but if we are exiting the while loop (KeyboardInterrupt), it will be handled outside if needed.
                # However, cli.py used to stop it in finally.
                pass

    if 'display_manager' in locals():
        display_manager.stop()


if __name__ == "__main__":
    main()
