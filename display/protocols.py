from abc import ABC, abstractmethod

class DisplayProtocol(ABC):
    """
    Abstract base class for display board protocols.
    """
    @abstractmethod
    def format_text(self, text: str, **kwargs) -> bytes:
        """Format the text according to the protocol."""
        pass

    @abstractmethod
    def get_reset_packet(self, strong: bool = True) -> bytes:
        """Get the packet for resetting/clearing the display."""
        pass


class AlphaProtocol(DisplayProtocol):
    """
    Microgate ALFA protocol implementation.
    """
    ESC = 0x1B
    ETX = 0x03

    def __init__(self, default_row: str = "A", default_col: int = 0, default_width: int = 45):
        self.default_row = default_row
        self.default_col = default_col
        self.default_width = default_width

    def _calculate_checksum(self, payload: str) -> int:
        """
        Calculates the Microgate ALFA protocol checksum.
        Initial value is 30. Each character (7-bit) is added to the sum,
        and then the sum is masked to 7-bit (modulo 128).
        """
        checksum = 30
        for char in payload:
            byte_val = ord(char) & 127
            checksum = (checksum + byte_val) & 127
        return checksum

    def format_text(self, text: str, row: str = None, col: int = None, width: int = None, **kwargs) -> bytes:
        """
        Formats the message for the Microtab LED display using ALPHA protocol.
        """
        r = row or self.default_row
        c = col if col is not None else self.default_col
        w = width if width is not None else (self.default_width - c)

        # Pad text to width to clear existing content in the cell
        padded_text = text.ljust(w)
        
        # Format the payload: Row ID + 'S' + Column ID (2 digits) + text
        payload = f"{r}S{c:02d}{padded_text}"
        
        checksum = self._calculate_checksum(payload)
        
        packet = bytearray()
        packet.append(self.ESC)
        packet.extend(payload.encode('ascii'))
        packet.append(self.ETX)
        packet.append(checksum)
        
        return bytes(packet)

    def get_reset_packet(self, strong: bool = True) -> bytes:
        """
        Get the packet for resetting/clearing the display according to ALPHA protocol.
        'r' is Strong Reset, 'R' is Weak Reset.
        Using ' ' (space) as row identifier for broadacst (whole board).
        """
        command = "r" if strong else "R"
        # Row identifier ' ' is broadcast for all rows
        payload = f" {command}"
        
        checksum = self._calculate_checksum(payload)
        
        packet = bytearray()
        packet.append(self.ESC)
        packet.extend(payload.encode('ascii'))
        packet.append(self.ETX)
        packet.append(checksum)
        
        return bytes(packet)


class GraphProtocol(DisplayProtocol):
    """
    Microgate GRAPH protocol implementation.
    """
    ESC = 0x1B
    ETX = 0x03
    ADDRESS = 0x40  # '@' identifier for graph mode

    # Font dimensions based on Microgate documentation (MicroTabLED_EN.md and graphic_protocol.md)
    # Mapping: FontID -> (Height, Column Width)
    FONT_DIMENSIONS = {
        0: (15, 10), # Default (assumed same as Medium)
        1: (9, 7),   # Small (9x7 non-proportional)
        2: (15, 10), # Medium Proportional (Height 15, Column width 10 per documentation)
        3: (31, 21), # Large (31xVar, estimated width)
        7: (16, 11), # Unicode (16xVar, estimated width)
    }

    def __init__(self, default_font: int = 1, default_bin_op: int = 0):
        self.default_font = default_font
        self.default_bin_op = default_bin_op

    def _calculate_checksum(self, packet: bytearray) -> int:
        """
        Calculates the Microgate GRAPH protocol checksum.
        7-bit checksum executed for the whole frame (sum of bytes & 0x7F).
        """
        return sum(packet) & 0x7F

    def _calculate_alpha_checksum(self, payload: str) -> int:
        """
        Calculates the Microgate ALFA protocol checksum.
        Used for legacy reset commands on graphical boards.
        """
        checksum = 30
        for char in payload:
            byte_val = ord(char) & 127
            checksum = (checksum + byte_val) & 127
        return checksum

    def _build_header(self, command: str, x: int, y: int, bin_op: int, font: int) -> bytearray:
        """
        Builds the standard GRAPH protocol header.
        """
        packet = bytearray()
        packet.append(self.ESC)
        packet.append(self.ADDRESS)
        packet.append(ord(command))
        
        packet.append(x & 0xFF)
        packet.append((x >> 8) & 0xFF)
        packet.append(y & 0xFF)
        packet.append((y >> 8) & 0xFF)
        
        packet.append(bin_op)
        packet.append(font)
        
        return packet

    def _finalize_packet(self, packet: bytearray) -> bytes:
        """
        Appends ETX and calculate/append Checksum.
        """
        packet.append(self.ETX)
        checksum = self._calculate_checksum(packet)
        packet.append(checksum)
        return bytes(packet)

    def format_text(self, text: str, x: int = None, y: int = None, font: int = None, bin_op: int = None, add_null_terminator: bool = True, invert: bool = False, width: int = None, **kwargs) -> bytes:
        """
        Formats a Write Fixed String command ('S') for the GRAPH protocol.
        Maps 'row' and 'col' from kwargs to x and y based on the selected font's dimensions.
        """
        f = font if font is not None else self.default_font
        w = width if width is not None else 81
        
        # If invert is requested, we use bin_op 1 (NOT) and pad the text
        if invert:
            bo = 1
            # Pad text to width to ensure the cell background is lit
            text = text.ljust(w)
        else:
            bo = bin_op if bin_op is not None else self.default_bin_op
        
        # Ensure text is not longer than width and total protocol limit (81)
        text = text[:min(w, 81)]
        
        # Determine dimensions for the current font
        base_font_id = f & 0x3F # Mask off alignment bits (128 right, 64 center)
        height, width = self.FONT_DIMENSIONS.get(base_font_id, self.FONT_DIMENSIONS[0])
        # remove the spacing between rows
        # height-=1
        
        # Map row/col to x/y if needed
        final_x = x
        final_y = y
        
        if final_x is None:
            col = kwargs.get('col', 0)
            try:
                final_x = int(col) * width
            except (ValueError, TypeError):
                final_x = 0
                
        if final_y is None:
            row = kwargs.get('row', 'A')
            try:
                if isinstance(row, str) and len(row) == 1 and row.isalpha():
                    # Map "A" -> 0, "B" -> 1, etc.
                    row_idx = ord(row.upper()) - ord('A')
                else:
                    row_idx = int(row)
                final_y = row_idx * height
            except (ValueError, TypeError):
                final_y = 0

        packet = self._build_header('S', final_x, final_y, bo, f)
        
        # String <= 81 bytes (including null terminator if added)
        # We truncate to 80 if null terminator is needed to stay within 81 byte limit
        max_len = 80 if add_null_terminator else 81
        encoded_text = text.encode('ascii', errors='ignore')[:max_len]
        packet.extend(encoded_text)
        
        if add_null_terminator:
            packet.append(0x00)
            
        return self._finalize_packet(packet)

    def get_reset_packet(self, strong: bool = True, x: int = 0, y: int = 0, width: int = 96, height: int = 16, **kwargs) -> bytes:
        """
        Get the packet for resetting/clearing the display.
        Uses the native GRAPH protocol 'Q' (Reset Area) command.
        """
        # Command 'Q' (Reset Area)
        # Data area: X Dimension (2 bytes), Y Dimension (2 bytes)
        packet = self._build_header('Q', x, y, 0, 0)
        
        packet.append(width & 0xFF)
        packet.append((width >> 8) & 0xFF)
        packet.append(height & 0xFF)
        packet.append((height >> 8) & 0xFF)
        
        return self._finalize_packet(packet)

    def display_date(self, mode: int, x: int = 0, y: int = 0, font: int = None, bin_op: int = None) -> bytes:
        """
        Display Date - Active Object ('A')
        mode: 1 = DD/MM/YY; 2 = DD MM YY
        """
        f = font if font is not None else self.default_font
        bo = bin_op if bin_op is not None else self.default_bin_op
        packet = self._build_header('A', x, y, bo, f)
        packet.append(mode & 0xFF)
        return self._finalize_packet(packet)

    def select_font(self, font: int, x: int = 0, y: int = 0, bin_op: int = 0) -> bytes:
        """
        Select Font ('F')
        """
        packet = self._build_header('F', x, y, bin_op, font)
        return self._finalize_packet(packet)

    def insert_images(self, image_data: bytes, width: int, height: int, x: int = 0, y: int = 0, bin_op: int = 0) -> bytes:
        """
        Insert Images ('I')
        """
        packet = self._build_header('I', x, y, bin_op, 0)
        packet.append(width & 0xFF)
        packet.append((width >> 8) & 0xFF)
        packet.append(height & 0xFF)
        packet.append((height >> 8) & 0xFF)
        packet.extend(image_data)
        return self._finalize_packet(packet)

    def display_internal_clock(self, display_format: int, delay: int = 0, x: int = 0, y: int = 0, font: int = None, bin_op: int = None) -> bytes:
        """
        Internal Clock Display (RTC) - Active Object ('N')
        display_format: 1=HH:MM:SS, 2=MM:SS, 3=HH:MM(24h), 4=HH:MM(12h)
        delay: Advance/delay in thousandths
        """
        f = font if font is not None else self.default_font
        bo = bin_op if bin_op is not None else self.default_bin_op
        packet = self._build_header('N', x, y, bo, f)
        
        packet.append(display_format & 0xFF)
        
        # 4 bytes delay, signed long (31 bit + symbol)
        try:
            delay_bytes = delay.to_bytes(4, byteorder='little', signed=True)
        except OverflowError:
            delay = max(min(delay, 2147483647), -2147483648)
            delay_bytes = delay.to_bytes(4, byteorder='little', signed=True)
        packet.extend(delay_bytes)
        
        return self._finalize_packet(packet)

    def write_scrolling_string(self, text: str, width: int, delay: int, display_width: int, x: int = 0, y: int = 0, font: int = None, bin_op: int = None) -> bytes:
        """
        Write Scrolling String - Active Object ('O')
        """
        f = font if font is not None else self.default_font
        bo = bin_op if bin_op is not None else self.default_bin_op
        packet = self._build_header('O', x, y, bo, f)
        
        packet.append(width & 0xFF)
        packet.append((width >> 8) & 0xFF)
        packet.append(delay & 0xFF)
        packet.append((delay >> 8) & 0xFF)
        packet.append(display_width & 0xFF)
        
        encoded_text = text.encode('ascii', errors='ignore')[:255]
        packet.extend(encoded_text)
        packet.append(0x00) # null terminator required
        
        return self._finalize_packet(packet)

    def deactivate_active_object(self, x: int, y: int) -> bytes:
        """
        Deactivating an active object ('t')
        """
        packet = self._build_header('t', x, y, 0, 0)
        return self._finalize_packet(packet)
