import time
import threading
import logging
from typing import List, Dict, Any, Optional
from lap_counter.display.board import DisplayBoard
from lap_counter.network.client import TCPClient


class AthleteResult:
    def __init__(self, key: str, actions: List[Dict[str, Any]]):
        self.key = key
        self.actions = actions
        self.arrival_time = time.time()

    def __repr__(self):
        return f"AthleteResult(key={self.key}, arrival_time={self.arrival_time}, actions={self.actions})"


class PaginationManager:
    """
    Dedicated module for display pagination.
    Supports the GRAPH protocol with a special layout when 2 columns are used.
    """

    def __init__(self, board: DisplayBoard, config: Dict[str, Any]):
        self.board = board
        self.n_cols =2

        # Load pagination settings
        pag_cfg = config.get("pagination", {})
        timing_cfg = pag_cfg.get("timing", {})
        self.max_age = timing_cfg.get("max_age_seconds", 15.0)
        self.refresh_interval = timing_cfg.get("refresh_rate_seconds", 2.0)
        self.n_rows = pag_cfg.get("n_rows", 2)
        self.offset_pagination = pag_cfg.get("step", 1)

        # Graph board dimension is in pixels. User board is 96x16 pixels.
        # We must convert pixels to characters based on the active font.
        self.board_width_px = 96
        self.board_height_px = 16
        font_id = getattr(board.protocol, "default_font", 1)
        # FONT_DIMENSIONS: FontID -> (Height, Column Width)
        font_dims = getattr(
            board.protocol, "FONT_DIMENSIONS", {0: (15, 10)})
        _, font_width = font_dims.get(font_id & 0x3F, font_dims.get(0))
        self.board_width = self.board_width_px // font_width

        self.cell_width = self.board_width // self.n_cols
        self.total_slots = self.n_rows * self.n_cols

        default_font = getattr(board.protocol, "default_font", 1)
        font_type = "small" if default_font == 1 else "large"
        font_height = 9 if font_type == "small" else 16

        if font_type == "large":
            self.logical_rows = self.n_rows
            self.y_offsets = [r * 17 for r in range(self.logical_rows)]
            self.bib_font = 3
            self.bib_right_font = 3 | 128
            self.msg_font = 2 | 64
        else:
            if self.n_rows == 1:
                self.logical_rows = 1
                self.y_offsets = [2]
            else:
                total_height = self.n_rows * 17 - 1
                self.logical_rows = total_height // font_height
                if self.logical_rows <= 1:
                    self.y_offsets = [2]
                else:
                    spacing = (total_height - (self.logical_rows *
                                               font_height)) / (self.logical_rows - 1)
                    self.y_offsets = [
                        int(round(i * (font_height + spacing))) for i in range(self.logical_rows)]
            self.bib_font = 1
            self.bib_right_font = 1 | 128
            self.msg_font = 1 | 64

        self.total_slots = self.logical_rows * 2

        self.active_results: List[AthleteResult] = []
        self.lock = threading.Lock()

        self.scroll_offset = 0
        self.last_scroll_time = 0.0
        self.last_display_state: List[Optional[str]] = [
            None] * self.total_slots

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
            if should_reset:
                logging.info(
                    "PaginationManager: should_reset received. Resetting hardware board and state cache.")
                # We do NOT clear self.active_results here because we want to keep
                # paginating athletes that are still within their display time.
                self.board.reset(strong=True)
                self.last_display_state = [None] * self.total_slots
                self.scroll_offset = 0

            # Remove previous result for this athlete if it exists
            self.active_results = [
                r for r in self.active_results if r.key != key]

            # Insert at the top (maximum visibility for latest arrival)
            new_result = AthleteResult(key, actions)
            self.active_results.insert(0, new_result)

            # Reset scrolling to show the newest arrival
            self.scroll_offset = 0
            self.last_scroll_time = time.time()

            # Immediate repaint
            self._paint_special()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        try:
            # Send a final reset when stopping to leave the board clean
            self.board.reset(strong=True)
        except Exception as e:
            logging.error(
                f"PaginationManager error resetting board during stop: {e}")

    def _run_loop(self):
        while not self._stop_event.is_set():
            # Sleep small interval to be responsive but not CPU heavy
            time.sleep(0.1)
            now = time.time()

            with self.lock:
                # 1. Cleanup expired results (older than 15s)
                original_count = len(self.active_results)
                self.active_results = [r for r in self.active_results if (
                    now - r.arrival_time) < self.max_age]

                # Check if we need to rotate scrolling
                needs_paint = len(self.active_results) != original_count

                if not self.active_results:
                    if needs_paint:
                        self.board.reset(strong=True)
                        self.last_display_state = [None] * self.total_slots
                    self.scroll_offset = 0
                    continue

                # 2. Refresh and Pagination logic
                is_scrolling = len(self.active_results) > self.total_slots
                time_for_refresh = (
                    now - self.last_scroll_time) >= self.refresh_interval

                if needs_paint or time_for_refresh:
                    if is_scrolling:
                        # Rotate to next page/athlete
                        self.scroll_offset = (
                            self.scroll_offset + self.offset_pagination) % len(self.active_results)
                    else:
                        # Static display, keep offset at 0
                        self.scroll_offset = 0

                    self.last_scroll_time = now

                    self._paint_special()

    def _paint_special(self):
        """
        Special paint mode when n_rows > 0 and 2 columns are used.
        Visualization per row:
        1. first bib/name in font 3 compact from x=0
        2. reset area from x=32 until end of board
        3. second bib in font 3 compact from x=96 (right aligned)
        4. msg info in center (string is center aligned)
        5. on pagination, full reset first.
        Gap between physical boards is 1 LED row.
        """

        num_athletes = len(self.active_results)

        total_slots = self.total_slots
        new_state = []
        athletes_to_draw = []

        for i in range(total_slots):
            if i < num_athletes:
                idx = (self.scroll_offset + i) % num_athletes
                ath = self.active_results[idx]
                state = f"{ath.key}_{ath.arrival_time}"
                athletes_to_draw.append(ath)
            else:
                state = ""
                athletes_to_draw.append(None)
            new_state.append(state)

        # If nothing changed since last paint, we don't repaint
        # However, to avoid 'list index out of range' with last_display_state,
        # let's just check the slots.
        if new_state == self.last_display_state[:total_slots]:
            return

        self.last_display_state[:total_slots] = new_state

        try:
            with TCPClient(self.board.ip, self.board.port) as client:

                # 5. Reset to the whole board before redrawing
                self.board.reset(strong=True, client=client)

                def get_field_text(athlete, field_name):
                    if not athlete:
                        return " "
                    for action in athlete.actions:
                        if action.get('field') == field_name:
                            return str(action.get('text', ''))
                    return " "

                for r in range(self.logical_rows):
                    y_offset = self.y_offsets[r]

                    ath1 = athletes_to_draw[r * 2]
                    ath2 = athletes_to_draw[r * 2 + 1]

                    if not ath1 and not ath2:
                        continue

                    # Fallback cleanly if the athlete object is None
                    bib1 = get_field_text(ath1, "id")
                    bib2 = get_field_text(ath2, "id")

                    msg1 = get_field_text(ath1, "msg")
                    msg2 = get_field_text(ath2, "msg")

                    # 1. First bib printed from x=0
                    if ath1:
                        self.board.send_text(
                            bib1, x=0, y=y_offset, font=self.bib_font, reset=False, client=client)

                    # 2. Reset area from x=32 to end of board (w=64) on this row
                    # if hasattr(self.board.protocol, 'get_reset_packet'):
                    #     packet = self.board.protocol.get_reset_packet(
                    #         strong=True, x=32, y=y_offset, width=64, height=16)
                    #     client.send(packet)

                    # 3. Second bib right aligned
                    if ath2:
                        self.board.send_text(
                            bib2, x=96, y=y_offset, font=self.bib_right_font, reset=False, client=client)

                    # 4. Center msg info
                    center_msg = f"{msg1} {msg2}"
                    if center_msg:
                        # 'center' alignment in Graph protocol is bit 6 (64)
                        self.board.send_text(
                            center_msg, x=48, y=y_offset, font=self.msg_font, reset=False, client=client)

        except Exception as e:
            logging.error(f"PaginationManager paint_special error: {e}")
