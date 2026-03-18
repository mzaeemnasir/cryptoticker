#!/usr/bin/env python3
"""
CryptoTicker - Real-time cryptocurrency futures price tracker.

Streams live price data from Binance Futures WebSocket and displays
a rich terminal UI with large ASCII price display, sparklines, and
24h market statistics.

Cross-platform: Works on Windows, macOS, and Linux.

Usage:
    python cryptoticker.py              # Interactive symbol prompt
    python cryptoticker.py btc          # Track BTC/USDT
    python cryptoticker.py ethusdt      # Track ETH/USDT
    python cryptoticker.py sol --compact # Compact single-line price
"""

import sys
import os
import re
import json
import time
import signal
import shutil
import atexit
import logging
import argparse
import threading
import unicodedata
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field

try:
    import websocket
except ImportError:
    print("\n  [ERROR] websocket-client is required.")
    print("  Install it with: pip install websocket-client\n")
    sys.exit(1)

__version__ = "1.0.0"

# ── Logging ────────────────────────────────────────────────────────────────────

logger = logging.getLogger("cryptoticker")

# ── Cross-Platform Terminal ────────────────────────────────────────────────────


def enable_windows_ansi():
    """Enable ANSI escape code support on Windows 10+."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # STD_OUTPUT_HANDLE = -11
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def get_terminal_size():
    """Get terminal dimensions, with safe defaults."""
    try:
        cols, rows = shutil.get_terminal_size()
        return max(cols, 60), max(rows, 20)
    except Exception:
        return 80, 24


def hide_cursor():
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


# ── ANSI Color Palette ────────────────────────────────────────────────────────

RST = "\033[0m"
BLD = "\033[1m"
DIM = "\033[2m"
GRN = "\033[92m"
RED = "\033[91m"
YEL = "\033[93m"
CYN = "\033[96m"
MAG = "\033[95m"
WHT = "\033[97m"
BLU = "\033[94m"
ORG = "\033[38;5;214m"
GRY = "\033[90m"

# Bright / bold variants for the big price
BGRN = "\033[1;92m"
BRED = "\033[1;91m"
BWHT = "\033[1;97m"
BYEL = "\033[1;93m"

_NO_COLOR = False


def strip_ansi(s):
    return re.sub(r"\033\[[0-9;]*m", "", s)


def char_width(ch):
    """Return the display width of a character in a terminal."""
    eaw = unicodedata.east_asian_width(ch)
    if eaw in ("W", "F"):
        return 2
    return 1


def visible_len(s):
    """Return the visible display width of a string (accounting for wide chars)."""
    clean = strip_ansi(s)
    return sum(char_width(ch) for ch in clean)


def set_no_color():
    global RST, BLD, DIM, GRN, RED, YEL, CYN, MAG, WHT, BLU, ORG, GRY
    global BGRN, BRED, BWHT, BYEL, _NO_COLOR
    RST = BLD = DIM = GRN = RED = YEL = CYN = MAG = WHT = BLU = ORG = GRY = ""
    BGRN = BRED = BWHT = BYEL = ""
    _NO_COLOR = True


# ── ASCII Big Digit Font (5 lines tall) ───────────────────────────────────────
# Each digit/symbol maps to a tuple of 5 strings, each the same width.

BIG_FONT = {
    "0": (
        " $$$ ",
        "$   $",
        "$   $",
        "$   $",
        " $$$ ",
    ),
    "1": (
        "  $  ",
        " $$  ",
        "  $  ",
        "  $  ",
        " $$$.",
    ),
    "2": (
        " $$$ ",
        "$   $",
        "  $$ ",
        " $   ",
        "$$$$$",
    ),
    "3": (
        " $$$ ",
        "$   $",
        "  $$ ",
        "$   $",
        " $$$ ",
    ),
    "4": (
        "$   $",
        "$   $",
        "$$$$$",
        "    $",
        "    $",
    ),
    "5": (
        "$$$$$",
        "$    ",
        "$$$$ ",
        "    $",
        "$$$$ ",
    ),
    "6": (
        " $$$ ",
        "$    ",
        "$$$$ ",
        "$   $",
        " $$$ ",
    ),
    "7": (
        "$$$$$",
        "    $",
        "   $ ",
        "  $  ",
        "  $  ",
    ),
    "8": (
        " $$$ ",
        "$   $",
        " $$$ ",
        "$   $",
        " $$$ ",
    ),
    "9": (
        " $$$ ",
        "$   $",
        " $$$$",
        "    $",
        " $$$ ",
    ),
    ".": (
        "  ",
        "  ",
        "  ",
        "  ",
        "$$",
    ),
    ",": (
        "  ",
        "  ",
        "  ",
        " $",
        "$ ",
    ),
    "$": (
        " $$$ ",
        "$ $  ",
        " $$$ ",
        "  $ $",
        " $$$ ",
    ),
    " ": (
        "   ",
        "   ",
        "   ",
        "   ",
        "   ",
    ),
    "-": (
        "     ",
        "     ",
        "$$$$$",
        "     ",
        "     ",
    ),
    "+": (
        "  $  ",
        "  $  ",
        "$$$$$",
        "  $  ",
        "  $  ",
    ),
    "%": (
        "$  $",
        "  $ ",
        " $  ",
        "$  $",
        "    ",
    ),
}


def render_big_price(text, color=""):
    """Render text as 5-line-tall ASCII art. Returns list of 5 strings."""
    lines = ["", "", "", "", ""]
    for ch in text:
        glyph = BIG_FONT.get(ch)
        if glyph is None:
            glyph = BIG_FONT.get(" ")
        for i in range(5):
            lines[i] += glyph[i] + " "
    # Apply color: replace '$' with '#' block char, colored
    result = []
    for line in lines:
        colored = ""
        for ch in line:
            if ch == "$":
                colored += f"{color}#{RST}"
            elif ch == ".":
                colored += f"{color}#{RST}"
            else:
                colored += ch
        result.append(colored)
    return result


# ── Data Model ────────────────────────────────────────────────────────────────


@dataclass
class TickerData:
    price: float = 0.0
    change_percent: float = 0.0
    change_abs: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    volume_quote: float = 0.0
    volume_base: float = 0.0
    trade_count: int = 0
    open_price: float = 0.0
    weighted_avg: float = 0.0
    best_bid: float = 0.0
    best_ask: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_binance(cls, data: dict) -> "TickerData":
        try:
            return cls(
                price=float(data.get("c", 0)),
                change_percent=float(data.get("P", 0)),
                change_abs=float(data.get("p", 0)),
                high_24h=float(data.get("h", 0)),
                low_24h=float(data.get("l", 0)),
                volume_quote=float(data.get("q", 0)),
                volume_base=float(data.get("v", 0)),
                trade_count=int(data.get("n", 0)),
                open_price=float(data.get("o", 0)),
                weighted_avg=float(data.get("w", 0)),
                best_bid=float(data.get("b", 0)),
                best_ask=float(data.get("a", 0)),
                timestamp=datetime.now(),
            )
        except (ValueError, TypeError) as e:
            logger.warning("Failed to parse ticker data: %s", e)
            return cls()


# ── Symbol Normalization ──────────────────────────────────────────────────────

ALIASES = {
    "BITCOIN": "BTC",
    "ETHEREUM": "ETH",
    "SOLANA": "SOL",
    "RIPPLE": "XRP",
    "DOGECOIN": "DOGE",
    "CARDANO": "ADA",
    "POLKADOT": "DOT",
    "AVALANCHE": "AVAX",
    "CHAINLINK": "LINK",
    "POLYGON": "MATIC",
    "LITECOIN": "LTC",
}


def normalize_symbol(raw: str) -> str:
    """Normalize user input to Binance Futures symbol format (e.g. BTCUSDT)."""
    sym = raw.strip().upper()

    # Check aliases
    if sym in ALIASES:
        sym = ALIASES[sym]

    # Strip common suffixes
    for suffix in (".P", ".PERP", "/USDT", "/USD", "-USDT", "-USD", ":USDT"):
        if sym.endswith(suffix):
            sym = sym[: -len(suffix)]
            break

    # Append USDT if no quote currency
    if not sym.endswith("USDT") and not sym.endswith("BUSD"):
        sym += "USDT"

    return sym


# ── Formatting Helpers ────────────────────────────────────────────────────────


def fmt_price(p):
    if p >= 10000:
        return f"{p:,.2f}"
    if p >= 100:
        return f"{p:,.3f}"
    if p >= 1:
        return f"{p:.4f}"
    if p >= 0.01:
        return f"{p:.6f}"
    return f"{p:.8f}"


def fmt_vol(v):
    if v >= 1e12:
        return f"${v / 1e12:.2f}T"
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"${v / 1e6:.2f}M"
    if v >= 1e3:
        return f"${v / 1e3:.2f}K"
    return f"${v:.2f}"


def fmt_number(n):
    if n >= 1e9:
        return f"{n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{n / 1e6:.2f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}K"
    return f"{n:,}"


# ── Display Widgets ───────────────────────────────────────────────────────────


def price_bar(lo, hi, cur, width=34):
    """Gradient bar showing current price position in 24h range."""
    if hi == lo:
        pct = 0.5
    else:
        pct = (cur - lo) / (hi - lo)
    pct = max(0.0, min(1.0, pct))
    filled = int(pct * width)
    empty = width - filled - 1

    bar = (
        f"{DIM}[{RST}"
        f"{GRN}{'=' * filled}"
        f"{YEL}>"
        f"{DIM}{'-' * max(0, empty)}"
        f"{DIM}]{RST}"
    )
    pct_tag = f" {BLD}{pct * 100:.1f}%{RST}"
    return bar + pct_tag


def sparkline(history, width=30):
    """Mini sparkline from recent price history."""
    data = list(history)[-width:]
    if len(data) < 2:
        return f"{DIM}{'-' * width}{RST}"
    lo = min(data)
    hi = max(data)
    bars = " ._-~*#@"
    line = ""
    for val in data:
        idx = int((val - lo) / (hi - lo + 1e-9) * (len(bars) - 1))
        c = GRN if val >= data[0] else RED
        line += f"{c}{bars[idx]}{RST}"
    return line


# ── Box Drawing ───────────────────────────────────────────────────────────────


class BoxRenderer:
    """Renders content inside a Unicode box, dynamically sized to terminal."""

    def __init__(self, width=None):
        if width is None:
            term_w, _ = get_terminal_size()
            self.W = min(term_w - 4, 80)
            self.W = max(self.W, 58)
        else:
            self.W = width

    def line(self, content="", align="left"):
        vis = visible_len(content)
        pad = self.W - vis
        if align == "center":
            lp = pad // 2
            rp = pad - lp
            return f"{CYN}{BLD}|{RST}{' ' * lp}{content}{' ' * rp}{CYN}{BLD}|{RST}"
        return f"{CYN}{BLD}|{RST}{content}{' ' * max(0, pad)}{CYN}{BLD}|{RST}"

    def sep(self, left="+", right="+", fill="-"):
        h = fill * self.W
        return f"{CYN}{BLD}{left}{h}{right}{RST}"

    @property
    def top(self):
        h = "-" * self.W
        return f"{CYN}{BLD}+{h}+{RST}"

    @property
    def bottom(self):
        h = "-" * self.W
        return f"{CYN}{BLD}+{h}+{RST}"


# ── Main Display Renderer ────────────────────────────────────────────────────

SPINNERS = ["|", "/", "-", "\\", "|", "/", "-", "\\"]


class TickerDisplay:
    """Renders the full ticker TUI frame."""

    def __init__(self, symbol: str, base: str, compact: bool = False):
        self.symbol = symbol
        self.base = base
        self.compact = compact
        self.tick = 0
        self.prev_price = None
        self.blink = True
        self.price_history = deque(maxlen=60)
        self.box = BoxRenderer()
        self.last_frame = ""

    def render(self, td: TickerData) -> str:
        """Build one complete frame as a string."""
        self.tick += 1
        self.blink = not self.blink

        is_up = td.change_percent >= 0
        PC = GRN if is_up else RED
        BPC = BGRN if is_up else BRED
        arrow = "^" if is_up else "v"

        # Price direction tick
        if self.prev_price is not None:
            if td.price > self.prev_price:
                pdiff = f" {GRN}^{RST}"
            elif td.price < self.prev_price:
                pdiff = f" {RED}v{RST}"
            else:
                pdiff = f" {DIM}-{RST}"
        else:
            pdiff = ""
        self.prev_price = td.price

        self.price_history.append(td.price)

        spinner = SPINNERS[self.tick % len(SPINNERS)]
        dot = f"{RED}o{RST}" if self.blink else f"{DIM}o{RST}"
        now = td.timestamp.strftime("%Y-%m-%d  %H:%M:%S")

        b = self.box
        lines = []

        # ── Header ──
        lines.append(b.top)
        lines.append(b.line())
        hdr = f"  {YEL}{BLD}>> BINANCE FUTURES{RST}   {DIM}|{RST}   {dot} {BLD}LIVE{RST}   {DIM}|{RST}   {CYN}{spinner}{RST}"
        lines.append(b.line(hdr))
        lines.append(b.line())
        lines.append(b.sep())

        # ── Symbol + Timestamp ──
        sym_line = f"  {WHT}{BLD}{self.base}/USDT{RST}  {DIM}PERPETUAL{RST}"
        ts_line = f"  {DIM}{now}{RST}"
        lines.append(b.line(sym_line))
        lines.append(b.line(ts_line))
        lines.append(b.sep())

        # ── Price Display ──
        price_str = fmt_price(td.price)
        lines.append(b.line())

        if not self.compact:
            # Big ASCII price
            big_text = f"${price_str}"
            big_lines = render_big_price(big_text, BPC)

            # Check if big price fits
            max_visible = max(visible_len(bl) for bl in big_lines)
            if max_visible + 6 <= b.W:
                for bl in big_lines:
                    lines.append(b.line(f"   {bl}", align="left"))
            else:
                # Fallback: large single-line price
                lines.append(
                    b.line(f"       {BPC}$ {price_str}{RST}{pdiff}", align="left")
                )
        else:
            lines.append(
                b.line(f"       {BPC}$ {price_str}{RST}{pdiff}", align="left")
            )

        lines.append(b.line())

        # ── 24h Change ──
        chg_line = (
            f"  {PC}{BLD}{arrow} {td.change_percent:+.2f}%{RST}"
            f"  {DIM}({PC}${abs(td.change_abs):,.2f}{RST}{DIM} 24h){RST}"
            f"{pdiff}"
        )
        lines.append(b.line(chg_line))
        lines.append(b.line())
        lines.append(b.sep())

        # ── Bid / Ask Spread ──
        if td.best_bid > 0 and td.best_ask > 0:
            spread = td.best_ask - td.best_bid
            spread_pct = (spread / td.price * 100) if td.price > 0 else 0
            bid_ask = (
                f"  {GRN}Bid: ${fmt_price(td.best_bid)}{RST}"
                f"  {DIM}|{RST}  "
                f"{RED}Ask: ${fmt_price(td.best_ask)}{RST}"
                f"  {DIM}(spread: {spread_pct:.4f}%){RST}"
            )
            lines.append(b.line(bid_ask))
            lines.append(b.sep())

        # ── 24h Range Bar ──
        lines.append(b.line(f"  {DIM}24h Range:{RST}"))
        bar_width = min(b.W - 16, 40)
        bar = price_bar(td.low_24h, td.high_24h, td.price, width=bar_width)
        lines.append(b.line(f"  {bar}"))
        lo_hi = (
            f"  {RED}Lo: ${fmt_price(td.low_24h)}{RST}"
            f"   {DIM}|{RST}   "
            f"{GRN}Hi: ${fmt_price(td.high_24h)}{RST}"
        )
        lines.append(b.line(lo_hi))
        lines.append(b.sep())

        # ── Sparkline ──
        spark_width = min(b.W - 20, 40)
        spark = sparkline(self.price_history, width=spark_width)
        lines.append(b.line(f"  {DIM}Price trend:{RST} {spark}"))
        lines.append(b.sep())

        # ── Stats Grid ──
        lines.append(
            b.line(
                f"  {CYN}Volume (USDT){RST}  {BLD}{fmt_vol(td.volume_quote)}{RST}"
            )
        )
        lines.append(
            b.line(
                f"  {BLU}Volume ({self.base:>4}){RST}  {BLD}{fmt_vol(td.volume_base)}{RST}"
            )
        )
        lines.append(
            b.line(
                f"  {MAG}Trades (24h) {RST}  {BLD}{fmt_number(td.trade_count)}{RST}"
            )
        )
        lines.append(
            b.line(
                f"  {ORG}Open Price   {RST}  {BLD}${fmt_price(td.open_price)}{RST}"
            )
        )
        if td.weighted_avg > 0:
            lines.append(
                b.line(
                    f"  {YEL}VWAP (24h)   {RST}  {BLD}${fmt_price(td.weighted_avg)}{RST}"
                )
            )
        lines.append(b.sep())

        # ── Footer ──
        footer = f"  {DIM}fstream.binance.com  |  Press Ctrl+C to exit{RST}"
        lines.append(b.line(footer))
        lines.append(b.bottom)

        return "\n".join(lines)

    def draw(self, td: TickerData):
        """Render and display a frame with flicker-free update."""
        frame = self.render(td)
        # Cursor home + write frame + clear to end of screen
        sys.stdout.write(f"\033[H{frame}\n\033[J")
        sys.stdout.flush()


# ── WebSocket Manager with Reconnection ───────────────────────────────────────


class ConnectionManager:
    """Manages WebSocket connection with automatic reconnection."""

    def __init__(self, url: str, on_data, on_status):
        self.url = url
        self.on_data = on_data
        self.on_status = on_status
        self._ws = None
        self._running = False
        self._thread = None
        self._reconnect_delay = 1.0
        self._max_delay = 30.0

    def start(self):
        self._running = True
        self._connect()

    def _connect(self):
        if not self._running:
            return

        self.on_status("connecting")

        self._ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        self._thread = threading.Thread(
            target=self._ws.run_forever,
            kwargs={"ping_interval": 30, "ping_timeout": 10},
            daemon=True,
        )
        self._thread.start()

    def _on_open(self, ws):
        self._reconnect_delay = 1.0
        self.on_status("connected")
        logger.info("WebSocket connected to %s", self.url)

    def _on_message(self, ws, msg):
        try:
            data = json.loads(msg)
            self.on_data(data)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON: %s", e)

    def _on_error(self, ws, err):
        logger.error("WebSocket error: %s", err)

    def _on_close(self, ws, code, msg):
        logger.info("WebSocket closed (code=%s, msg=%s)", code, msg)
        if self._running:
            self.on_status("reconnecting")
            time.sleep(self._reconnect_delay)
            self._reconnect_delay = min(
                self._reconnect_delay * 2, self._max_delay
            )
            self._connect()

    def stop(self):
        self._running = False
        if self._ws:
            self._ws.close()
        if self._thread:
            self._thread.join(timeout=3)


# ── Main Application ─────────────────────────────────────────────────────────


def run(symbol: str, compact: bool = False):
    """Main entry point: connect to Binance and display live ticker."""
    symbol_upper = symbol
    symbol_lower = symbol.lower()
    base = symbol_upper.replace("USDT", "").replace("BUSD", "")

    url = f"wss://fstream.binance.com/ws/{symbol_lower}@ticker"

    display = TickerDisplay(symbol_upper, base, compact=compact)

    # Status messages for connection state
    status = {"state": "connecting"}
    status_lock = threading.Lock()

    def on_data(raw_data):
        td = TickerData.from_binance(raw_data)
        with status_lock:
            status["state"] = "live"
        display.draw(td)

    def on_status(state):
        with status_lock:
            status["state"] = state
        if state == "reconnecting":
            sys.stdout.write(f"\033[H\n  {YEL}Reconnecting...{RST}\n\033[J")
            sys.stdout.flush()

    conn = ConnectionManager(url, on_data, on_status)

    # Graceful shutdown
    def shutdown():
        conn.stop()
        show_cursor()
        # Clear screen and show farewell
        sys.stdout.write("\033[H\033[2J")
        sys.stdout.flush()
        print(f"\n  {CYN}{BLD}Stopped tracking {symbol_upper}{RST}")
        print(f"  {DIM}Thanks for using CryptoTicker!{RST}\n")

    def signal_handler(sig, frame):
        shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(show_cursor)

    # Launch
    enable_windows_ansi()
    hide_cursor()
    # Clear screen once at start
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

    print(f"\n  {CYN}{BLD}>> CryptoTicker v{__version__}{RST}")
    print(f"  {GRN}*{RST} Symbol  : {BLD}{YEL}{symbol_upper}{RST}")
    print(f"  {GRN}*{RST} Stream  : {DIM}{url}{RST}")
    print(f"\n  {CYN}Connecting...{RST}\n")

    conn.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        shutdown()


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        prog="cryptoticker",
        description="Real-time cryptocurrency futures price tracker with live terminal UI.",
        epilog="Examples:\n"
        "  cryptoticker btc          Track Bitcoin\n"
        "  cryptoticker eth          Track Ethereum\n"
        "  cryptoticker solusdt      Track Solana\n"
        "  cryptoticker doge --compact  Compact mode\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "symbol",
        nargs="?",
        help="Crypto symbol (e.g., btc, eth, SOLUSDT, btcusdt.p, bitcoin)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Use compact single-line price display",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--log-file",
        metavar="PATH",
        help="Write debug logs to file",
    )

    args = parser.parse_args()

    # Setup logging
    if args.log_file:
        logging.basicConfig(
            filename=args.log_file,
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )
    else:
        logging.basicConfig(level=logging.WARNING)

    # Color handling
    if args.no_color or os.environ.get("NO_COLOR"):
        set_no_color()

    # Get symbol
    if args.symbol:
        raw_input = args.symbol
    else:
        # Interactive prompt
        print(f"\n  {CYN}{BLD}>> CryptoTicker v{__version__}{RST}\n")
        print(
            f"  {YEL}Enter coin symbol{RST} {DIM}(e.g. btc / eth / SOLUSDT / bitcoin):{RST}"
        )
        try:
            raw_input = input(f"  {BLD}> {RST}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  {DIM}Bye!{RST}\n")
            sys.exit(0)

    if not raw_input:
        print(f"\n  {RED}No symbol provided. Exiting.{RST}\n")
        sys.exit(1)

    symbol = normalize_symbol(raw_input)
    run(symbol, compact=args.compact)


if __name__ == "__main__":
    main()
