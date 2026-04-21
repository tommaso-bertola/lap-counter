import logging
from typing import Any
from lap_counter.network.client import TCPClient
from lap_counter.display.protocols import DisplayProtocol, AlphaProtocol, GraphProtocol


class DisplayBoard:
    """
    Higher-level class for managing communication with a display board.
    Takes a protocol (ALPHA/GRAPH) and handles sending messages.
    """

    def __init__(self, ip: str, port: int, protocol: DisplayProtocol):
        self.ip = ip
        self.port = port
        self.protocol = protocol

    def reset(self, strong: bool = True, delay: bool = False, client: Any = None):
        """Hard reset the display board (clears everything)."""
        try:
            packet = self.protocol.get_reset_packet(strong=strong, delay=delay)
            if client:
                logging.info(
                    f"Sending reset packet (persistent) to {self.ip}:{self.port}")
                client.send(packet)
            else:
                with TCPClient(self.ip, self.port) as new_client:
                    logging.info(
                        f"Sending reset packet to {self.ip}:{self.port}")
                    new_client.send(packet)
        except Exception as e:
            logging.error(f"Error resetting display board: {e}")
            raise

    def send_text(self, text: str, reset: bool = True, delay: bool = False, client: Any = None, **kwargs):
        """Send formatted text to the display board, optionally clearing it first."""
        try:
            if reset:
                # Clear the whole board with a hard reset
                self.reset(strong=True, delay=delay, client=client)

            # Send the new text
            packet = self.protocol.format_text(text, delay=delay, **kwargs)
            clean_text = "".join(c for c in text if c.isprintable()).strip()

            if client:
                logging.info(
                    f"Packet (persistent): \"{clean_text}\"")
                client.send(packet)
            else:
                with TCPClient(self.ip, self.port) as new_client:
                    logging.info(f"Packet: \"{clean_text}\"")
                    new_client.send(packet)
            logging.debug("Message sent successfully!")
        except Exception as e:
            logging.error(f"Error sending message to display board: {e}")
            raise
