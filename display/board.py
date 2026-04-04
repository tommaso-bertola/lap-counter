import logging
from typing import Any
from network.client import TCPClient
from display.protocols import DisplayProtocol, AlphaProtocol

def _format_packet(packet: bytes) -> str:
    """Convert a byte packet into a human-readable string."""
    res = []
    for b in packet:
        if b == 0x1b: res.append("<ESC>")
        elif b == 0x03: res.append("<ETX>")
        elif 32 <= b <= 126: res.append(chr(b))
        else: res.append(f"<{b:02X}>")
    return "".join(res)

class DisplayBoard:
    """
    Higher-level class for managing communication with a display board.
    Takes a protocol (ALPHA/GRAPH) and handles sending messages.
    """
    def __init__(self, ip: str, port: int, protocol: DisplayProtocol = None):
        self.ip = ip
        self.port = port
        self.protocol = protocol or AlphaProtocol()

    def reset(self, strong: bool = True):
        """Hard reset the display board (clears everything)."""
        try:
            packet = self.protocol.get_reset_packet(strong=strong)
            with TCPClient(self.ip, self.port) as client:
                logging.info(f"Sending reset packet to {self.ip}:{self.port}: {_format_packet(packet)}")
                client.send(packet)
        except Exception as e:
            logging.error(f"Error resetting display board: {e}")
            raise

    def send_text(self, text: str, reset: bool = True, **kwargs):
        """Send formatted text to the display board, optionally clearing it first."""
        try:
            if reset:
                # Clear the whole board with a hard reset
                self.reset(strong=True)
            
            # Send the new text
            packet = self.protocol.format_text(text, **kwargs)
            with TCPClient(self.ip, self.port) as client:
                logging.info(f"Sending text packet to {self.ip}:{self.port}: {_format_packet(packet)}")
                client.send(packet)
            logging.info("Message sent successfully!")
        except Exception as e:
            logging.error(f"Error sending message to display board: {e}")
            raise
