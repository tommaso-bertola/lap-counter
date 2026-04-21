"""
cli2.py — Interactive GRAPH protocol tester for the display board.

Usage:
    python -m lap_counter.cli2                         # uses config.json defaults
    python -m lap_counter.cli2 --ip 192.168.0.125 --port 21967
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from lap_counter.display.board import DisplayBoard
from lap_counter.display.protocols import GraphProtocol
from lap_counter.network.client import TCPClient

# ── Defaults ────────────────────────────────────────────────────────────────
DEFAULT_IP = "192.168.0.125"
DEFAULT_PORT = 21967

FONT_TABLE = {
    0: "Default (15×10)",
    1: "Small  (9×7, non-prop)",
    2: "Large (15×10, proportional)",
    3: "Compact  (31×21)",
    7: "Unicode (16×11)",
}


def _load_config_defaults() -> tuple[str, int, int, int]:
    """Try to pull connection and board dimensions from a local config.json."""
    cfg_path = Path("config.json")
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
            hw = cfg.get("hardware", {})
            conn = hw.get("connection", {})
            board = hw.get("board_dimension", {"width": 96, "height": 16})
            return (
                conn.get("ip", DEFAULT_IP),
                int(conn.get("port", DEFAULT_PORT)),
                int(board.get("width", 96)),
                int(board.get("height", 16))
            )
        except Exception:
            pass
    return DEFAULT_IP, DEFAULT_PORT, 96, 16


def _print_fonts():
    print("\n  Available fonts:")
    for fid, desc in FONT_TABLE.items():
        print(f"    {fid} → {desc}")
    print()


def _ask_int(prompt: str, default: int) -> int:
    raw = input(f"  {prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"    ⚠  invalid, using {default}")
        return default


def _ask_str(prompt: str, default: str) -> str:
    raw = input(f"  {prompt} [{default}]: ").strip()
    return raw if raw else default


# ── Commands ────────────────────────────────────────────────────────────────

def cmd_send_text(board: DisplayBoard, proto: GraphProtocol):
    """Send a text string — choose font, position, invert."""
    _print_fonts()
    font = _ask_int("Font ID", proto.default_font)
    text = _ask_str("Text", "Hello World")
    x = _ask_int("X (px)", 0)
    y = _ask_int("Y (px)", 0)
    invert = _ask_str("Invert? (y/n)", "n").lower().startswith("y")
    center = _ask_str("Center align? (y/n)", "n").lower().startswith("y")
    delay = _ask_str("Delay update? (y/n)", "n").lower().startswith("y")

    if center:
        font |= 64  # Graph Protocol: bit 6 (64) enables center alignment

    print(
        f"\n  → Sending \"{text}\" font={font} x={x} y={y} inv={invert} center={center} delay={delay}")
    board.send_text(text, reset=False, font=font, x=x, y=y, invert=invert, delay=delay)
    print("  ✓ sent\n")


def cmd_send_row_col(board: DisplayBoard, proto: GraphProtocol):
    """Send text using logical row/col (like the main app does)."""
    _print_fonts()
    font = _ask_int("Font ID", proto.default_font)
    text = _ask_str("Text", "123 Smith")
    row = _ask_str("Row (A/B/C… or 0/1/2…)", "A")
    col = _ask_int("Col", 0)
    invert = _ask_str("Invert? (y/n)", "n").lower().startswith("y")
    center = _ask_str("Center align? (y/n)", "n").lower().startswith("y")
    delay = _ask_str("Delay update? (y/n)", "n").lower().startswith("y")

    if center:
        font |= 64  # Graph Protocol: bit 6 (64) enables center alignment

    print(
        f"\n  → Sending \"{text}\" font={font} row={row} col={col} inv={invert} center={center} delay={delay}")
    board.send_text(text, reset=False, font=font,
                    row=row, col=col, invert=invert, delay=delay)
    print("  ✓ sent\n")


def cmd_font_showcase(board: DisplayBoard, proto: GraphProtocol):
    """Send the same string with every font so you can compare on-device."""
    text = _ask_str("Text to show in all fonts", "Abc123")
    reset_first = _ask_str("Reset board first? (y/n)",
                           "y").lower().startswith("y")
    delay = _ask_str("Delay update? (y/n)", "n").lower().startswith("y")

    if reset_first:
        board.reset(strong=True, delay=delay)
        print("  ✓ board reset")

    y_cursor = 0
    for fid, desc in FONT_TABLE.items():
        height = GraphProtocol.FONT_DIMENSIONS.get(fid, (15, 10))[0]
        label = f"F{fid}: {text}"
        print(f"  → font {fid} ({desc})  y={y_cursor}")
        board.send_text(label, reset=False, font=fid, x=0, y=y_cursor, delay=delay)
        y_cursor += height + 1  # +1 px gap

    print("  ✓ all fonts sent\n")


def cmd_reset(board: DisplayBoard, _proto: GraphProtocol):
    """Send a reset/clear command."""
    delay = _ask_str("Delay update? (y/n)", "n").lower().startswith("y")
    board.reset(strong=True, delay=delay)
    print("  ✓ board reset\n")


def cmd_multiline(board: DisplayBoard, proto: GraphProtocol):
    """Send multiple lines at once to fill the board."""
    _print_fonts()
    font = _ask_int("Font ID", proto.default_font)
    n_lines = _ask_int("Number of lines", 2)
    reset_first = _ask_str("Reset board first? (y/n)",
                           "y").lower().startswith("y")
    delay = _ask_str("Delay update? (y/n)", "n").lower().startswith("y")

    if reset_first:
        board.reset(strong=True, delay=delay)

    height = GraphProtocol.FONT_DIMENSIONS.get(font, (15, 10))[0]
    for i in range(n_lines):
        text = _ask_str(f"  Line {i} text", f"Line {i}")
        y = i * height
        print(f"    → \"{text}\" y={y}")
        board.send_text(text, reset=False, font=font, x=0, y=y, delay=delay)

    print("  ✓ all lines sent\n")


def cmd_narrow_test(board: DisplayBoard, proto: GraphProtocol):
    """Send narrow glyphs (1iIl|!.:) per font to test proportional spacing."""
    narrow = "1iIl|!.:;"
    wide = "MWQO0@#%"
    sample = _ask_str("Narrow string", narrow)
    ref = _ask_str("Wide ref string", wide)
    reset_first = _ask_str("Reset board first? (y/n)",
                           "y").lower().startswith("y")
    delay = _ask_str("Delay update? (y/n)", "n").lower().startswith("y")

    if reset_first:
        board.reset(strong=True, delay=delay)
        print("  ✓ board reset")

    y_cursor = 0
    for fid, desc in FONT_TABLE.items():
        h, w = GraphProtocol.FONT_DIMENSIONS.get(fid, (15, 10))
        # row 1: narrow chars, row 2: wide chars for comparison
        print(f"  → font {fid} ({desc})  y={y_cursor}  narrow")
        board.send_text(sample, reset=False, font=fid, x=0, y=y_cursor, delay=delay)
        y_cursor += h + 1
        print(f"  → font {fid} ({desc})  y={y_cursor}  wide")
        board.send_text(ref, reset=False, font=fid, x=0, y=y_cursor, delay=delay)
        y_cursor += h + 1

    print("  ✓ narrow test sent\n")


def cmd_scrolling_text(board: DisplayBoard, proto: GraphProtocol):
    """Send scrolling (running) text across the display."""
    _print_fonts()
    font = _ask_int("Font ID", proto.default_font)
    text = _ask_str("Text", "This is a scrolling text sample ... ")
    x = _ask_int("X (px)", 0)
    y = _ask_int("Y (px)", 0)
    width = _ask_int("Text area width (px)", 96)
    speed_delay = _ask_int("Delay/speed (ms)", 3)
    delay_update = _ask_str("Delay update? (y/n)", "n").lower().startswith("y")

    print(f"\n  → Sending scrolling text \"{text[:20]}...\" font={font} x={x} y={y} delay_update={delay_update}")
    packet = proto.write_scrolling_string(
        text=text,
        width=width,
        scroll_delay=speed_delay,
        display_width=width,
        x=x, y=y, font=font,
        delay=delay_update
    )

    with TCPClient(board.ip, board.port) as client:
        client.send(packet)
    print("  ✓ sent\n")


def cmd_reset_area(board: DisplayBoard, proto: GraphProtocol):
    """Reset a specific pixel area of the board."""
    x = _ask_int("Start X (px)", 0)
    y = _ask_int("Start Y (px)", 0)
    w = _ask_int("Width (px)", proto.width)
    h = _ask_int("Height (px)", proto.height)
    delay = _ask_str("Delay update? (y/n)", "n").lower().startswith("y")

    print(f"\n  → Sending area reset x={x} y={y} w={w} h={h} delay={delay}")
    packet = proto.reset_area(x=x, y=y, width=w, height=h, delay=delay)
    with TCPClient(board.ip, board.port) as client:
        client.send(packet)
    print("  ✓ area reset\n")


MENU = [
    ("Send text (x/y px)", cmd_send_text),
    ("Send text (row/col)", cmd_send_row_col),
    ("Font showcase", cmd_font_showcase),
    ("Narrow chars test", cmd_narrow_test),
    ("Running/scrolling text", cmd_scrolling_text),
    ("Multi-line fill", cmd_multiline),
    ("Reset full board", cmd_reset),
    ("Reset specific area", cmd_reset_area),
]


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    cfg_ip, cfg_port, cfg_w, cfg_h = _load_config_defaults()

    parser = argparse.ArgumentParser(
        description="GRAPH protocol display tester")
    parser.add_argument("--ip", default=cfg_ip, help=f"Display IP [{cfg_ip}]")
    parser.add_argument("--port", type=int, default=cfg_port,
                        help=f"Display port [{cfg_port}]")
    parser.add_argument("--font", type=int, default=1,
                        help="Default font ID [1]")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    proto = GraphProtocol(default_font=args.font, width=cfg_w, height=cfg_h)
    board = DisplayBoard(ip=args.ip, port=args.port, protocol=proto)

    print(f"\n  Display: {args.ip}:{args.port}  |  Default font: {args.font}")
    print("  ─────────────────────────────────────────────")

    while True:
        print()
        for idx, (label, _) in enumerate(MENU, 1):
            print(f"  {idx}. {label}")
        print(f"  q. Quit")

        choice = input("\n  > ").strip().lower()
        if choice in ("q", "quit", "exit"):
            print("  bye.\n")
            break

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(MENU):
                MENU[idx][1](board, proto)
            else:
                print("  ⚠  invalid choice")
        except ValueError:
            print("  ⚠  enter a number or 'q'")
        except KeyboardInterrupt:
            print("\n  bye.\n")
            break
        except Exception as e:
            logging.error(f"Command failed: {e}")


if __name__ == "__main__":
    main()
