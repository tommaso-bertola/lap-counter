import time
import threading
import logging
from typing import List, Dict, Any

from display.board import DisplayBoard

class DisplayEvent:
    def __init__(self, actions: List[Dict[str, Any]], should_reset: bool):
        self.actions = actions
        self.should_reset = should_reset
        self.arrival_time = time.time()
        self.display_time = 0.0
        self.last_shown_time = 0.0
        self.is_currently_shown = False

class DisplayManager:
    """
    Manages the display board, allowing for rotation of events 
    if multiple happen within a short time threshold.
    """
    def __init__(self, board: DisplayBoard, config: Dict[str, Any] = None):
        if config is None:
            config = {}
        self.board = board
        # Time threshold to consider events "close" (seconds)
        self.close_threshold = config.get("close_threshold_seconds", 5.0)
        # Time to show each event before switching (seconds)
        self.rotation_interval = config.get("rotation_interval_seconds", 3.0)
        # Minimum total display time for any single event (seconds)
        self.min_display_time = config.get("min_display_time_seconds", 5.0)
        
        self.active_events: List[DisplayEvent] = []
        self.lock = threading.Lock()
        
        self.current_index = -1
        self.rotation_start_time = 0.0
        
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def show_message(self, actions: List[Dict[str, Any]], should_reset: bool):
        """
        Submits a new message (a set of actions) to be displayed.
        """
        if not actions:
            return
            
        with self.lock:
            # Add to the queue of active events
            new_event = DisplayEvent(actions, should_reset)
            self.active_events.append(new_event)
            
            # If it's the only one, we can immediately show it
            if len(self.active_events) == 1:
                self._switch_to_event(0)

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2.0)

    def _switch_to_event(self, index: int):
        now = time.time()
        
        # Turn off currently shown event
        if self.current_index >= 0 and self.current_index < len(self.active_events):
            curr = self.active_events[self.current_index]
            if curr.is_currently_shown:
                curr.display_time += (now - curr.last_shown_time)
                curr.is_currently_shown = False
                
        self.current_index = index
        self.rotation_start_time = now
        
        new_event = self.active_events[self.current_index]
        new_event.is_currently_shown = True
        new_event.last_shown_time = now
        
        self._send_to_board(new_event)

    def _send_to_board(self, event: DisplayEvent):
        try:
            if event.should_reset:
                self.board.reset(strong=True)
                
            for action in event.actions:
                row = action.get('row')
                col = action.get('col')
                text = action.get('text', '')
                self.board.send_text(text, row=row, col=col, reset=False)
        except Exception as e:
            logging.error(f"DisplayManager error sending to board: {e}")

    def _run_loop(self):
        while not self._stop_event.is_set():
            time.sleep(0.1)
            now = time.time()
            
            with self.lock:
                if not self.active_events:
                    continue
                    
                # Accrue display time for currently shown event
                current_event = None
                if self.current_index >= 0 and self.current_index < len(self.active_events):
                    current_event = self.active_events[self.current_index]
                    if current_event.is_currently_shown:
                        current_event.display_time += (now - current_event.last_shown_time)
                        current_event.last_shown_time = now
                
                # Cleanup old events
                active_to_keep = []
                for event in self.active_events:
                    # Keep if hasn't reached min display time OR hasn't been in list for threshold time
                    if event.display_time < self.min_display_time or (now - event.arrival_time) < self.close_threshold:
                        active_to_keep.append(event)
                    else:
                        if event.is_currently_shown:
                            event.is_currently_shown = False
                            
                # Check if the list changed
                events_changed = len(self.active_events) != len(active_to_keep)
                self.active_events = active_to_keep
                
                if not self.active_events:
                    self.current_index = -1
                    continue
                    
                # Adjust current index after deletion
                if events_changed:
                    if current_event in self.active_events:
                        self.current_index = self.active_events.index(current_event)
                    else:
                        self.current_index = -1
                
                # Determine if we need to rotate
                need_switch = False
                if self.current_index == -1:
                    need_switch = True
                elif len(self.active_events) > 1 and (now - self.rotation_start_time) >= self.rotation_interval:
                    need_switch = True
                    
                if need_switch:
                    next_index = (self.current_index + 1) % len(self.active_events)
                    self._switch_to_event(next_index)
