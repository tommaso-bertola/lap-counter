import logging
import time
import threading
from typing import List, Dict, Any, Optional
from lap_counter.display.board import DisplayBoard


class AthleteResult:
    def __init__(self, key: str, actions: List[Dict[str, Any]]):
        self.key = key
        self.actions = actions
        # Pre-calculate fields for O(1) lookup
        self.fields = {str(a.get('field')): str(a.get('text', ''))
                       for a in actions if 'field' in a}
        self.arrival_time = time.time()

    def __repr__(self):
        return f"AthleteResult(key={self.key}, arrival_time={self.arrival_time}, fields={list(self.fields.keys())})"


def get_field_text(athlete: Optional[AthleteResult], field_name: str) -> str:
    if not athlete:
        return ""
    return athlete.fields.get(field_name, "")


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

        self.total_height = self.board.total_height
        self.total_width = self.board.total_width

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

        # Register these rows with the board for logging purposes
        self.board.y_offsets = self.y_offsets

        if self.font_y_dimension == 9:
            self.board.athlete_font = 1
            self.status_font = 1
            self.vertical_padding_pixels = 0
        elif self.font_y_dimension == 15:
            self.board.athlete_font = 2
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

        # Use the bib and name as the key for deduplication
        name = actions[0].get('text', 'unknown')
        bib = actions[0].get('bib', 'unknown')
        key = f"{bib}{name}"

        with self.lock:
            logging.debug(f"PaginationManager: received new result {key}")

            # Remove previous result for this athlete if it exists (O(N) but small N)
            self.active_results = [
                r for r in self.active_results if r.key != key]

            # Insert at the top (maximum visibility for latest arrival)
            new_result = AthleteResult(key, actions)
            self.active_results.insert(0, new_result)

            # Reset scrolling to show the newest arrival
            self.scroll_offset = 0
            self.last_scroll_time = time.time()

            # Force repaint by clearing state
            self.last_display_state = [None] * self.total_slots

            # Copy data for painting outside the lock
            athletes_to_draw = self._get_athletes_to_draw()
            current_state = [
                f"{a.key}_{a.arrival_time}" if a else "" for a in athletes_to_draw]

        # Immediate repaint (outside lock if possible, but _paint_special has its own logic)
        self._paint_special(athletes_to_draw, current_state)

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        try:
            # Send a final reset when stopping to leave the board clean
            self.board.reset(strong=True)
        except Exception as e:
            logging.error(
                f"PaginationManager error resetting board during stop: {e}")

    def _get_athletes_to_draw(self) -> List[Optional[AthleteResult]]:
        """Determine which athletes should be on the screen based on current scroll offset."""
        num_athletes = len(self.active_results)
        athletes = []
        for i in range(self.total_slots):
            if i < num_athletes:
                idx = (self.scroll_offset + i) % num_athletes
                athletes.append(self.active_results[idx])
            else:
                athletes.append(None)
        return athletes

    def _run_loop(self):
        while not self._stop_event.is_set():
            # Sleep small interval to be responsive but not CPU heavy
            time.sleep(0.1)
            now = time.time()
            athletes_to_draw = []
            new_state = []
            should_paint = False

            with self.lock:
                # 1. Cleanup expired results (older than max_age_seconds)
                original_count = len(self.active_results)
                self.active_results = [r for r in self.active_results if (
                    now - r.arrival_time) < self.max_age]

                # Check if we need to rotate scrolling
                count_changed = len(self.active_results) != original_count

                if not self.active_results:
                    if count_changed:
                        self.board.reset(strong=True)
                        self.last_display_state = [None] * self.total_slots
                    self.scroll_offset = 0
                    continue

                # 2. Refresh and Pagination logic
                is_scrolling = len(self.active_results) > self.total_slots
                time_for_refresh = (
                    now - self.last_scroll_time) >= self.refresh_interval

                if count_changed or time_for_refresh:
                    if is_scrolling:
                        # Rotate to next page/athlete
                        self.scroll_offset = (
                            self.scroll_offset + self.offset_pagination) % len(self.active_results)
                    else:
                        # Static display, keep offset at 0
                        self.scroll_offset = 0

                    self.last_scroll_time = now
                    athletes_to_draw = self._get_athletes_to_draw()
                    new_state = [
                        f"{a.key}_{a.arrival_time}" if a else "" for a in athletes_to_draw]

                    # Only paint if the visual state actually changed
                    if new_state != self.last_display_state:
                        should_paint = True
                        # Update state while holding lock
                        self.last_display_state = new_state

            if should_paint:
                # Release lock before doing network I/O
                self._paint_special(athletes_to_draw, new_state)

    def _paint_special(self, athletes_to_draw: List[Optional[AthleteResult]], state: List[str]):
        """
        Special paint mode when n_rows > 0 and 2 columns are used.
        Expects a pre-calculated list of athletes to draw.
        """
        try:
            with self.board.connection() as client:
                logging.debug("PaginationManager: Starting paint_special")

                # 5. Reset to the whole board before redrawing
                # Use delay=True to batch everything until the final flush
                self.board.reset(strong=True, client=client, delay=True)

                for r in range(self.n_logical_rows):
                    ath1 = athletes_to_draw[r * 2]
                    ath2 = athletes_to_draw[r * 2 + 1]

                    if not ath1 and not ath2:
                        continue

                    y_offset = self.y_offsets[r]

                    # 1. First column
                    if ath1:
                        status1 = get_field_text(ath1, "msg")
                        bib1 = get_field_text(ath1, "id")

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
                            bib1,
                            x=self.font_x_dimension + self.spacing_between_status_and_bib_leds,
                            y=y_offset + self.vertical_padding_pixels,
                            font=self.board.athlete_font,
                            reset=False,
                            client=client,
                            delay=True)

                    # 2. Second column
                    if ath2:
                        status2 = get_field_text(ath2, "msg")
                        bib2 = get_field_text(ath2, "id")

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
                            bib2,
                            x=self.mid_point + self.font_x_dimension +
                            self.spacing_between_status_and_bib_leds,
                            y=y_offset + self.vertical_padding_pixels,
                            font=self.board.athlete_font,
                            reset=False,
                            client=client,
                            delay=True)

                # Final empty send with delay=False to trigger the board refresh
                self.board.send_text(
                    "", x=0, y=0, font=1, reset=False, client=client, delay=False)

        except Exception as e:
            logging.error(f"PaginationManager paint_special error: {e}")
