import socket
import logging


class TCPClient:
    """
    A simple TCP client that handles connection and receiving data in chunks.
    """

    def __init__(self, host: str, port: int, timeout: float = None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None

    def connect(self):
        """Establish the TCP connection."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.timeout is not None:
            self.sock.settimeout(self.timeout)
        self.sock.connect((self.host, self.port))
        logging.debug(f"Connected to {self.host}:{self.port}")

    def receive_chunks(self, chunk_size: int = 4096):
        """Generator that yields data chunks from the socket."""
        if not self.sock:
            raise RuntimeError("Socket not connected. Call connect() first.")

        while True:
            try:
                chunk = self.sock.recv(chunk_size)
                if not chunk:
                    logging.debug("Connection closed by server")
                    break
                yield chunk
            except socket.timeout:
                # On timeout, we just continue the loop to keep the connection alive
                continue
            except Exception as e:
                logging.error(f"Error receiving data: {e}")
                break

        self.close()

    def send(self, data: bytes):
        """Send data through the socket."""
        if not self.sock:
            raise RuntimeError("Socket not connected.")
        self.sock.sendall(data)

    def close(self):
        """Close the socket connection."""
        if self.sock:
            self.sock.close()
            self.sock = None
            logging.debug("Connection closed")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
