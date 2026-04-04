import socket
import json
import time
import logging

def start_mock_server(host='127.0.0.1', port=1234):
    """
    A simple mock server that sends JSON payloads to clients.
    """
    logging.basicConfig(level=logging.INFO)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        logging.info(f"Mock server listening on {host}:{port}")
        
        while True:
            conn, addr = s.accept()
            with conn:
                logging.info(f"Connected by {addr}")
                
                # Sample payloads
                payloads = [
                    {"dataType": "passing", "bib": "101", "brutetime": "12:34:56.789", "Mod": "1", "Entra": "1"},
                    {"dataType": "heartbeat", "status": "ok"},
                    {"dataType": "passing", "bib": "202", "brutetime": "12:35:10.123", "Mod": "1", "Entra": "1"}
                ]
                
                for p in payloads:
                    data = json.dumps(p).encode('utf-8')
                    logging.info(f"Sending: {data}")
                    conn.sendall(data)
                    time.sleep(2)
                
                logging.info("All payloads sent. Closing connection.")

if __name__ == "__main__":
    start_mock_server()
