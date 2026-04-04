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

    def format_text(self, text: str, row: str = None, col: int = None, width: int = None) -> bytes:
        """
        Formats the message for the Microtab LED display using ALPHA protocol.
        """
        r = row or self.default_row
        c = col if col is not None else self.default_col
        w = width if width is not None else self.default_width

        # Format the payload: Row ID + 'S' + Column ID (2 digits) + text
        payload = f"{r}S{c:02d}{text}"
        
        # Pad with spaces to clear any existing long strings
        if len(payload) < w:
            payload = payload.ljust(w)
        
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
    Placeholder for the Microgate GRAPH protocol.
    To be implemented in the future.
    """
    def format_text(self, text: str, x: int = 0, y: int = 0, font: int = 1, bin_op: int = 0) -> bytes:
        # Implementation details for Graph Protocol go here
        raise NotImplementedError("Graph protocol not yet implemented.")

    def get_reset_packet(self, strong: bool = True) -> bytes:
        # Implementation details for Graph Protocol go here
        raise NotImplementedError("Graph protocol reset not yet implemented.")
