import os
import pprint
import subprocess
import logging
from network.client import TCPClient
from parsing.json_stream import JSONStreamParser
from storage.disk import MessageStore
from display.board import DisplayBoard
from display.config_handler import DisplayConfigHandler

# Connection defaults
DEFAULT_HOST = "192.168.1.12"
DEFAULT_PORT = 1234
DEFAULT_DISPLAY_IP = "192.168.1.12"
DEFAULT_DISPLAY_PORT = 4422

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def play_sound():
    """Play a short 'bit' sound when data is received and parsed."""
    try:
        subprocess.Popen(['afplay', '/System/Library/Sounds/Bottle.aiff'], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def main():
    setup_logging()
    
    # Initialize components
    config_handler = DisplayConfigHandler(config_path="config.json")
    
    # Get configuration with environment variable overrides
    net_cfg = config_handler.network_config
    disp_cfg = config_handler.display_config
    
    HOST = os.environ.get("TCP_HOST", net_cfg.get("host", DEFAULT_HOST))
    PORT = int(os.environ.get("TCP_PORT", net_cfg.get("port", DEFAULT_PORT)))
    
    DISPLAY_IP = os.environ.get("DISPLAY_IP", disp_cfg.get("ip", DEFAULT_DISPLAY_IP))
    DISPLAY_PORT = int(os.environ.get("DISPLAY_PORT", disp_cfg.get("port", DEFAULT_DISPLAY_PORT)))

    parser = JSONStreamParser()
    store = MessageStore(directory="output")
    display_board = DisplayBoard(ip=DISPLAY_IP, port=DISPLAY_PORT)

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
                    display_actions = config_handler.get_display_actions(obj) if config_handler.should_process_for_display(data_type) else []
                    if display_actions:
                        if not is_in_race:
                            logging.info(f">>> {data_type.upper()} DETECTED <<<")
                        
                        should_reset = config_handler.reset_before_send
                        for action in display_actions:
                            try:
                                if not is_in_race:
                                    logging.info(f"Sending to Display: {action['text']} (Row: {action['row']}, Col: {action['col']}, Reset: {should_reset})")
                                display_board.send_text(action['text'], row=action['row'], col=action['col'], reset=should_reset)
                            except Exception as e:
                                logging.error(f"Failed to update display board: {e}")
                    elif data_type != "passing" and not is_in_race:
                        logging.info("Received data (no display rules applied):")
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

if __name__ == "__main__":
    main()
