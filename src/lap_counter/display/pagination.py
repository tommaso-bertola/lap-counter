import logging
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


def get_field_text(athlete, field_name):
    if not athlete:
        return ""
    for action in athlete.actions:
        if action.get('field') == field_name:
            return str(action.get('text', ''))
    return ""


class PaginationManager:
    """
    Dedicated module for display pagination.
    Supports the GRAPH protocol with a special layout when 2 columns are used.
    """

    def __init__(self, board: DisplayBoard, config: Dict[str, Any]):
        self.board = board

        # Load pagination settings
        pag_cfg = config.get("pagination", {})
        timing_cfg = pag_cfg.get("timing", {})
        self.max_age = timing_cfg.get("max_age_seconds", 15.0)
        self.refresh_interval = timing_cfg.get("refresh_rate_seconds", 2.0)

        dimensions = config.get("board_dimension", {})
        self.board_height = dimensions.get("height", 32)
        self.board_width = dimensions.get("width", 128)
        self.n_vertical_boards = dimensions.get("n_vertical_boards", 1)
        self.n_horizonal_boards = dimensions.get("n_horizonal_boards", 1)

        self.total_height = self.board_height * self.n_vertical_boards
        self.total_width = self.board_width * self.n_horizonal_boards

        FONT_DIMENSIONS = {
            1: (9, 7),
            "small": (9, 7),
            2: (15, 14),
            "large": (15, 14)  # vertical, max horizontal width for fixed font
        }
        chosen_font = pag_cfg.get("font_size", 1)
        logging.info(f"PaginationManager: chosen_font={chosen_font}")

        self.font_y_dimension, self.font_x_dimension = FONT_DIMENSIONS.get(
            chosen_font)

        logging.info(
            f"PaginationManager: font_y_dimension={self.font_y_dimension} font_x_dimension={self.font_x_dimension}")

        self.n_logical_rows = self.total_height // (self.font_y_dimension + 1)
        self.mid_point = self.total_width // 2
        self.n_cols = 2
        self.total_slots = self.n_logical_rows * self.n_cols
        logging.info(
            f"PaginationManager: total_slots={self.total_slots}: {self.n_logical_rows} rows x {self.n_cols} cols")

        self.offset_pagination = pag_cfg.get("step", 1)
        logging.info(
            f"PaginationManager: offset_pagination={self.offset_pagination}")

        self.y_offsets = [
            i * (self.font_y_dimension + 2) for i in range(self.n_logical_rows)]
        logging.info(
            f"PaginationManager: y_offsets={self.y_offsets}")

        if self.font_y_dimension == 9:
            self.athlete_font = 1
            self.status_font = 1
            self.vertical_padding_pixels = 0
        elif self.font_y_dimension == 15:
            self.athlete_font = 2
            self.status_font = 5
            self.vertical_padding_pixels = 0
            # self.vertical_padding_pixels = self.font_y_dimension - 9

        self.invert_background = int(
            pag_cfg.get("invert_status_background", 0))

        self.spacing_between_status_and_bib_leds = int(
            pag_cfg.get("spacing_between_status_and_bib_leds", 2))
        logging.info(
            f"PaginationManager: spacing_between_status_and_bib_leds={self.spacing_between_status_and_bib_leds}")

        # athlete results handling
        self.active_results: List[AthleteResult] = []
        self.lock = threading.Lock()

        self.scroll_offset = 0
        self.last_scroll_time = 0.0
        self.last_display_state: List[Optional[str]] = [
            None] * self.total_slots

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def show_message(self, actions: List[Dict[str, Any]]):
        """
        New result arrived. Put it on top and trigger immediate refresh.
        """
        if not actions:
            return
        logging.debug(f"PaginationManager: received new result {actions}")
        # Use the bib and name as the key for deduplication
        name = actions[0].get('text', 'unknown')
        bib = actions[0].get('bib', 'unknown')
        key = bib + name

        with self.lock:
            logging.debug(f"PaginationManager: received new result {key}")
            logging.debug(
                f"PaginationManager: active_results={self.active_results}")
            self.last_display_state = [None] * self.total_slots

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
                # 1. Cleanup expired results (older than max_age_seconds)
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

                logging.debug(
                    f"PaginationManager: GOT THIS FAR")

                # 5. Reset to the whole board before redrawing
                self.board.reset(strong=True, client=client, delay=True)

                for r in range(self.n_logical_rows):
                    ath1 = athletes_to_draw[r * 2]
                    ath2 = athletes_to_draw[r * 2 + 1]

                    if not ath1 and not ath2:
                        continue

                    y_offset = self.y_offsets[r]

                    # Fallback cleanly if the athlete object is None
                    id1 = get_field_text(ath1, "id")
                    id2 = get_field_text(ath2, "id")

                    status1 = get_field_text(ath1, "msg")
                    status2 = get_field_text(ath2, "msg")

                    # 1. First bib printed from x=0
                    self.board.send_text(
                        status1,
                        x=0,
                        y=y_offset,
                        font=self.status_font,
                        reset=False,
                        client=client,
                        bin_op=self.invert_background,
                        delay=True)

                    self.board.send_text(
                        id1,
                        x=self.font_x_dimension + self.spacing_between_status_and_bib_leds,
                        y=y_offset + self.vertical_padding_pixels,
                        font=self.athlete_font,
                        reset=False,
                        client=client,
                        delay=True)

                    self.board.send_text(
                        status2,
                        x=self.mid_point,
                        y=y_offset,
                        font=self.status_font,
                        reset=False,
                        client=client,
                        bin_op=self.invert_background,
                        delay=True)

                    self.board.send_text(
                        id2,
                        x=self.mid_point + self.font_x_dimension +
                        self.spacing_between_status_and_bib_leds,
                        y=y_offset + self.vertical_padding_pixels,
                        font=self.athlete_font,
                        reset=False,
                        client=client,
                        delay=True)

                # this is needed to trigger the update of the board
                self.board.send_text(
                    "", x=0, y=0, font=1, reset=False, client=client, delay=False)

        except Exception as e:
            logging.error(f"PaginationManager paint_special error: {e}")
