import logging
from typing import Any
from lap_counter.network.client import TCPClient
from lap_counter.display.protocols import DisplayProtocol, AlphaProtocol, GraphProtocol


class DisplayBoard:
    """
    Higher-level class for managing communication with a display board.
    Supports multiple protocols (ALPHA/GRAPH) with lazy initialization.
    """

    PROTOCOL_REGISTRY = {
        "alpha": AlphaProtocol,
        "graph": GraphProtocol
    }

    def __init__(self, ip: str, port: int,
                 board_width: int = 128, board_height: int = 32,
                 n_vertical: int = 1, n_horizontal: int = 1,
                 default_protocol: str = "graph"):
        self.ip = ip
        self.port = port
        self.default_protocol_name = default_protocol.lower()
        self._protocol_cache = {}

        self.board_width = board_width
        self.board_height = board_height
        self.n_vertical = n_vertical
        self.n_horizontal = n_horizontal
        self.total_width = board_width * n_horizontal
        self.total_height = board_height * n_vertical

        self.athlete_font = 1
        self._log_buffer = []  # Buffer for unified logging
        self._all_y_offsets = set()  # Track all rows ever seen or registered

    def _get_protocol(self, name: str = None) -> DisplayProtocol:
        """Lazy-loads and returns the requested protocol instance."""
        proto_name = (name or self.default_protocol_name).lower()
        if proto_name not in self._protocol_cache:
            proto_cls = self.PROTOCOL_REGISTRY.get(proto_name)
            if not proto_cls:
                available = ", ".join(self.PROTOCOL_REGISTRY.keys())
                raise ValueError(
                    f"Unknown protocol: {proto_name}. Available: {available}")

            # Initialize with relevant dimensions/defaults
            if proto_name == "graph":
                self._protocol_cache[proto_name] = proto_cls(
                    width=self.total_width,
                    height=self.total_height,
                    default_font=self.athlete_font
                )
            elif proto_name == "alpha":
                # Alpha protocol uses characters/rows, but we can pass a default width
                self._protocol_cache[proto_name] = proto_cls(default_width=45)
            else:
                self._protocol_cache[proto_name] = proto_cls()

        return self._protocol_cache[proto_name]

    def connection(self):
        """Returns a context manager for a TCP connection to the board."""
        return TCPClient(self.ip, self.port)

    def send_packet(self, packet: bytes, client: Any = None):
        """Low-level method to send a raw packet to the board."""
        if client:
            client.send(packet)
        else:
            with self.connection() as new_client:
                new_client.send(packet)

    def reset(self, strong: bool = True, delay: bool = False, client: Any = None, protocol: str = None):
        """Reset the display board using the specified protocol."""
        try:
            proto = self._get_protocol(protocol)
            packet = proto.get_reset_packet(strong=strong, delay=delay)
            self._log_buffer = []  # Clear log buffer on reset

            logging.debug(
                f"Sending reset packet ({proto.__class__.__name__}) to {self.ip}:{self.port}")
            self.send_packet(packet, client=client)

            if not delay:
                logging.info(
                    f"DISPLAY RESET [{proto.__class__.__name__}] ({self.ip}:{self.port})")

        except Exception as e:
            logging.error(f"Error resetting display board: {e}")
            raise

    def send_text(self, text: str, reset: bool = True, delay: bool = False, client: Any = None, protocol: str = None, **kwargs):
        """Send formatted text to the display board using the specified protocol."""
        try:
            if reset:
                self.reset(strong=True, delay=delay,
                           client=client, protocol=protocol)

            proto = self._get_protocol(protocol)
            packet = proto.format_text(text, delay=delay, **kwargs)

            # Buffer text for unified logging
            clean_text = "".join(c for c in text if c.isprintable()).strip()
            x = kwargs.get('x', kwargs.get('col', 0))
            y = kwargs.get('y', kwargs.get('row', 0))

            # Record this y-coordinate as a known row (convert row letter to index if needed)
            if isinstance(y, str) and len(y) == 1 and y.isalpha():
                y_idx = ord(y.upper()) - ord('A')
            else:
                try:
                    y_idx = int(y)
                except (ValueError, TypeError):
                    y_idx = 0

            self._all_y_offsets.add(y_idx)

            if clean_text:
                display_text = clean_text
                if 'log_suffix' in kwargs:
                    display_text += str(kwargs['log_suffix'])
                self._log_buffer.append((x, y_idx, display_text))

            self.send_packet(packet, client=client)

            if not delay:
                self._flush_log()

            logging.debug(
                f"Message sent successfully using {proto.__class__.__name__}")
        except Exception as e:
            logging.error(f"Error sending message to display board: {e}")
            raise

    def send_command(self, method_name: str, *args, protocol: str = None, client: Any = None, **kwargs):
        """
        Generic method to call any protocol-specific method and send the resulting packet.
        Example: board.send_command("display_internal_clock", 1, protocol="graph")
        """
        try:
            proto = self._get_protocol(protocol)
            method = getattr(proto, method_name)
            packet = method(*args, **kwargs)

            self.send_packet(packet, client=client)
            logging.debug(
                f"Command '{method_name}' sent successfully using {proto.__class__.__name__}")
        except Exception as e:
            logging.error(f"Error sending command '{method_name}': {e}")
            raise

    def stop_graphic_object(self, x: int, y: int, delay: bool = False, client: Any = None):
        """
        Deactivate an active object at the specified coordinates.
        """
        self.send_command("stop_graphic_object", x=x, y=y,
                          delay=delay, client=client, protocol="graph")

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

            lines.append(f"  [Row {y:2}] | {line_text}")

        log_msg = f"Display update ({self.ip}:{self.port}):\n\n" + \
            "\n".join(lines)
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
