import time
import threading
import logging
from typing import List, Dict, Any, Optional
from display.board import DisplayBoard

class AthleteResult:
    def __init__(self, key: str, actions: List[Dict[str, Any]]):
        self.key = key
        self.actions = actions
        self.arrival_time = time.time()

class PaginationManager:
    """
    Dedicated module for display pagination.
    Supports both ALPHA and GRAPH protocols by using unified row/col syntax.
    """
    def __init__(self, board: DisplayBoard, config: Dict[str, Any]):
        self.board = board
        
        # Load pagination settings
        pag_cfg = config.get("pagination", {})
        self.close_threshold = pag_cfg.get("close_threshold_seconds", 10.0)
        self.max_age = pag_cfg.get("max_age_seconds", 15.0)
        self.refresh_interval = pag_cfg.get("refresh_interval_seconds", 2.0)
        self.n_rows = pag_cfg.get("n_display_rows", 2)
        
        self.active_results: List[AthleteResult] = []
        self.lock = threading.Lock()
        
        self.scroll_offset = 0
        self.last_scroll_time = 0.0
        self.last_display_state: List[Optional[str]] = [None] * self.n_rows
        
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def show_message(self, actions: List[Dict[str, Any]], should_reset: bool = False):
        """
        New result arrived. Put it on top and trigger immediate refresh.
        """
        if not actions:
            return

        # Use the first text field (bib) as the key for deduplication
        key = actions[0].get('text', 'unknown')
        
        with self.lock:
            # Remove previous result for this athlete if it exists
            self.active_results = [r for r in self.active_results if r.key != key]
            
            # Insert at the top (maximum visibility for latest arrival)
            new_result = AthleteResult(key, actions)
            self.active_results.insert(0, new_result)
            
            # Reset scrolling to show the newest arrival
            self.scroll_offset = 0
            self.last_scroll_time = time.time()
            
            # Immediate repaint
            self._paint()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        try:
            # Send a final reset when stopping to leave the board clean
            self.board.reset(strong=True)
        except Exception as e:
            logging.error(f"PaginationManager error resetting board during stop: {e}")

    def _run_loop(self):
        while not self._stop_event.is_set():
            # Sleep small interval to be responsive but not CPU heavy
            time.sleep(0.1)
            now = time.time()
            
            with self.lock:
                # 1. Cleanup expired results (older than 15s)
                original_count = len(self.active_results)
                self.active_results = [r for r in self.active_results if (now - r.arrival_time) < self.max_age]
                
                # Check if we need to rotate scrolling
                needs_paint = len(self.active_results) != original_count
                
                if not self.active_results:
                    if needs_paint:
                        self.board.reset(strong=True)
                        self.last_display_state = [None] * self.n_rows
                    self.scroll_offset = 0
                    continue

                # 2. Scrolling logic
                if len(self.active_results) <= self.n_rows:
                    # No scrolling needed if we can fit everyone
                    if self.scroll_offset != 0 or needs_paint:
                        self.scroll_offset = 0
                        self._paint()
                else:
                    # Rotate every 2 seconds
                    if (now - self.last_scroll_time) >= self.refresh_interval:
                        self.scroll_offset = (self.scroll_offset + 1) % len(self.active_results)
                        self.last_scroll_time = now
                        self._paint()
                    elif needs_paint:
                        # Repaint to reflect expired entries
                        self._paint()

    def _paint(self):
        """
        Renders the current window of results to the board.
        Only sends updates if content actually changed.
        """
        current_view_keys = []
        num_athletes = len(self.active_results)
        
        for i in range(self.n_rows):
            if i < num_athletes:
                # Wrap around for scrolling
                idx = (self.scroll_offset + i) % num_athletes
                athlete = self.active_results[idx]
                
                # Create a cache key for this row: athlete_key + arrival_time (to detect updates)
                row_state = f"{athlete.key}_{athlete.arrival_time}"
            else:
                row_state = "" # Empty row
            
            current_view_keys.append(row_state)

        # Check for redundant refresh
        if current_view_keys == self.last_display_state:
            return

        # Perform the actual update
        try:
            for i, state in enumerate(current_view_keys):
                if state == self.last_display_state[i]:
                    continue # Skip unchanged rows
                
                row_letter = chr(ord('A') + i)
                
                if state == "":
                    # Clear this row
                    self.board.send_text("", row=row_letter, col=0, reset=False)
                else:
                    idx = (self.scroll_offset + i) % num_athletes
                    athlete = self.active_results[idx]
                    
                    # Assemble row text from actions.
                    # We merge all actions for one athlete into a single string for that row.
                    # This ensures that for inverted rows (white on black), the whole background
                    # is lit and the text blocks are correctly subtracted.
                    row_buffer = list(" " * 81)
                    for action in athlete.actions:
                        text = str(action.get('text', ''))
                        try:
                            col = int(action.get('col', 0))
                        except (ValueError, TypeError):
                            col = 0
                        for j, char in enumerate(text):
                            if 0 <= col + j < len(row_buffer):
                                row_buffer[col + j] = char
                    
                    row_text = "".join(row_buffer).rstrip()
                    
                    # Even rows (2nd, 4th, etc. -> index 1, 3, ...) are inverted
                    is_even_row = (i % 2 == 1)
                    
                    self.board.send_text(row_text, row=row_letter, col=0, reset=False, invert=is_even_row)
                
                self.last_display_state[i] = state
                
        except Exception as e:
            logging.error(f"PaginationManager paint error: {e}")
