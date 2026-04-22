import logging
from typing import Any
from lap_counter.network.client import TCPClient
from lap_counter.display.protocols import DisplayProtocol, AlphaProtocol, GraphProtocol


class DisplayBoard:
    """
    Higher-level class for managing communication with a display board.
    Takes a protocol (ALPHA/GRAPH) and handles sending messages.
    """

    def __init__(self, ip: str, port: int, protocol: DisplayProtocol, 
                 board_width: int = 128, board_height: int = 32, 
                 n_vertical: int = 1, n_horizontal: int = 1):
        self.ip = ip
        self.port = port
        self.protocol = protocol
        
        self.board_width = board_width
        self.board_height = board_height
        self.n_vertical = n_vertical
        self.n_horizontal = n_horizontal
        self.total_width = board_width * n_horizontal
        self.total_height = board_height * n_vertical
        
        self.athlete_font = 1
        self._log_buffer = []  # Buffer for unified logging
        self._all_y_offsets = set()  # Track all rows ever seen or registered

    def connection(self):
        """Returns a context manager for a TCP connection to the board."""
        return TCPClient(self.ip, self.port)

    def reset(self, strong: bool = True, delay: bool = False, client: Any = None):
        """Hard reset the display board (clears everything)."""
        try:
            packet = self.protocol.get_reset_packet(strong=strong, delay=delay)
            self._log_buffer = []  # Clear log buffer on reset

            if client:
                logging.debug(
                    f"Sending reset packet (persistent) to {self.ip}:{self.port}")
                client.send(packet)
            else:
                with self.connection() as new_client:
                    logging.debug(
                        f"Sending reset packet to {self.ip}:{self.port}")
                    new_client.send(packet)

            if not delay:
                logging.info(f"DISPLAY RESET ({self.ip}:{self.port})")

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

            # Buffer text for unified logging
            clean_text = "".join(c for c in text if c.isprintable()).strip()
            x = kwargs.get('x', 0)
            y = kwargs.get('y', 0)

            # Record this y-coordinate as a known row
            self._all_y_offsets.add(y)

            if clean_text:
                self._log_buffer.append((x, y, clean_text))

            if client:
                client.send(packet)
            else:
                with self.connection() as new_client:
                    new_client.send(packet)

            if not delay:
                self._flush_log()

            logging.debug("Message sent successfully!")
        except Exception as e:
            logging.error(f"Error sending message to display board: {e}")
            raise

    def _flush_log(self):
        """Prints the buffered text as a single board update log, including empty rows."""
        # Sort by y (top to bottom) then x (left to right)
        self._log_buffer.sort(key=lambda item: (item[1], item[0]))

        # Group current buffer by y coordinate
        current_rows = {}
        for x, y, text in self._log_buffer:
            if y not in current_rows:
                current_rows[y] = []
            current_rows[y].append(text)

        # Determine max width for each column to ensure vertical alignment
        max_cols = 0
        for row_content in current_rows.values():
            max_cols = max(max_cols, len(row_content))
            
        col_widths = [0] * max_cols
        for row_content in current_rows.values():
            for i, text in enumerate(row_content):
                col_widths[i] = max(col_widths[i], len(text))

        lines = []
        # Always iterate over ALL known y-offsets to show empty rows
        for y in sorted(list(self._all_y_offsets)):
            row_content = current_rows.get(y, [])
            if row_content:
                # Pad each cell to match its column width
                padded_cells = [
                    text.ljust(col_widths[i]) 
                    for i, text in enumerate(row_content)
                ]
                line_text = '  |  '.join(padded_cells)
            else:
                line_text = "(empty)"
            
            lines.append(f"  [Row {y:2}] {line_text}")

        log_msg = f"DISPLAY UPDATE ({self.ip}:{self.port}):\n" + "\n".join(lines)
        logging.info(log_msg)

        # Clear buffer for next update
        self._log_buffer = []

    @property
    def y_offsets(self):
        """Get or set the known y-offsets (rows) for the board logging."""
        return sorted(list(self._all_y_offsets))

    @y_offsets.setter
    def y_offsets(self, values):
        if values:
            self._all_y_offsets.update(values)
