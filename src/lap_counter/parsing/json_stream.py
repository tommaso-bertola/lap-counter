import json
import codecs
import logging
from typing import Generator, Any

class JSONStreamParser:
    """
    Parses a stream of bytes and yields complete JSON objects.
    """
    def __init__(self):
        self.decoder = json.JSONDecoder()
        self.utf8_decoder = codecs.getincrementaldecoder("utf-8")()
        self.buffer = ""

    def feed(self, chunk: bytes) -> Generator[Any, None, None]:
        """
        Feeds a chunk of bytes into the parser and yields any completed JSON objects.
        """
        try:
            self.buffer += self.utf8_decoder.decode(chunk, final=False)
        except UnicodeDecodeError as e:
            logging.error(f"Unicode decode error: {e}")
            return

        while self.buffer:
            self.buffer = self.buffer.lstrip()
            if not self.buffer:
                break
            
            try:
                obj, index = self.decoder.raw_decode(self.buffer)
                yield obj
                self.buffer = self.buffer[index:]
            except json.JSONDecodeError:
                # Partial JSON, wait for more data
                break
            except Exception as e:
                logging.error(f"Unexpected error during parsing: {e}")
                self.buffer = "" # Clear buffer on error
                break
