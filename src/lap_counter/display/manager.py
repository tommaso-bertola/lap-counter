from typing import Dict, Any

from lap_counter.display.board import DisplayBoard
from lap_counter.display.pagination import PaginationManager



def make_display_manager(board: DisplayBoard, config: Dict[str, Any] = None) -> Any:
    """
    Factory function to create a DisplayManager based on configuration.
    """
    if config is None:
        config = {}

    return PaginationManager(board, config)
