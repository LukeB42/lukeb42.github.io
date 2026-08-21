"""
Minimal in-memory curses shim for running TDFIF inside Pyodide.

Pyodide's CPython build ships no ncurses, and there's no real terminal
under a browser tab anyway. This implements exactly the slice of the
curses API tdfif/*.py touches: a screen buffer with addch/addstr/
erase/refresh/getmaxyx, a color-pair table (basic 8 colors plus the
xterm-256 cube/grayscale indices ui.py's per-level palettes reach for
when curses.COLORS >= 256), the handful of key constants tdfif compares
against, and a non-blocking getch() fed by push_key() from the JS side.
There is no real device underneath - the browser renders whatever's in
the buffer (via Screen.render_rows()) and forwards DOM key events into
the input queue. Unlike TDF, none of TDFIF's menus use the mouse, so
there's no mouse plumbing here at all.

TDFIF never imports this module by name. The web bridge script
registers an instance of it into sys.modules['curses'] before the
tdfif package is loaded, so every `import curses` inside tdfif/*.py
resolves here instead of to a real (absent) curses.
"""


class error(Exception):
    """Stand-in for curses.error."""


# ---- color constants (mirror real curses ordering; not load-bearing) ----
COLOR_BLACK = 0
COLOR_RED = 1
COLOR_GREEN = 2
COLOR_YELLOW = 3
COLOR_BLUE = 4
COLOR_MAGENTA = 5
COLOR_CYAN = 6
COLOR_WHITE = 7

# ui.py checks `curses.COLORS >= 256` (see apply_palette/init_colors) to
# decide whether to reach for the richer xterm-256 shades instead of the
# basic 8. This shim resolves those indices for real (see _xterm256_hex
# below), so it can honestly claim the same 256-color support a real
# xterm would.
COLORS = 256

# ---- attribute bits (style in the low byte; color pair packed above it) ----
A_NORMAL = 0
A_BOLD = 1 << 0
A_DIM = 1 << 1
A_REVERSE = 1 << 2
_PAIR_SHIFT = 8

# ---- key constants: arbitrary but distinct. tdfif only ever compares
# them against values this same module hands back from getch() ----
KEY_UP = 1001
KEY_DOWN = 1002
KEY_LEFT = 1003
KEY_RIGHT = 1004
KEY_ENTER = 1005
KEY_RESIZE = 1007
KEY_BACKSPACE = 1008

_PAIRS = {0: (-1, -1)}


def start_color():
    pass


def use_default_colors():
    pass


def init_pair(n, fg, bg):
    _PAIRS[n] = (fg, bg)


def color_pair(n):
    return n << _PAIR_SHIFT


def curs_set(n):
    pass


class Screen:
    """Stands in for stdscr: a (char, attr) grid plus an input queue."""

    def __init__(self, cols=120, rows=40):
        self.cols = cols
        self.rows = rows
        self._buf = self._blank(cols, rows)
        self._input = []  # [code, ...]

    @staticmethod
    def _blank(cols, rows):
        return [[(' ', 0) for _ in range(cols)] for _ in range(rows)]

    # -------- curses-alike surface used by tdfif/*.py --------

    def getmaxyx(self):
        return self.rows, self.cols

    def erase(self):
        self._buf = self._blank(self.cols, self.rows)

    def addch(self, y, x, ch, attr=0):
        if 0 <= y < self.rows and 0 <= x < self.cols:
            self._buf[y][x] = (ch, attr)

    def addstr(self, y, x, text, attr=0):
        if not (0 <= y < self.rows):
            return
        row = self._buf[y]
        for i, ch in enumerate(text):
            xi = x + i
            if xi >= self.cols:
                break
            if xi >= 0:
                row[xi] = (ch, attr)

    def refresh(self):
        pass

    def keypad(self, flag):
        pass

    def timeout(self, ms):
        pass

    def getch(self):
        if not self._input:
            return -1
        return self._input.pop(0)

    # -------- driven by the JS bridge, not by tdfif --------

    def resize(self, cols, rows):
        cols, rows = max(1, int(cols)), max(1, int(rows))
        if (cols, rows) != (self.cols, self.rows):
            self.cols, self.rows = cols, rows
            self._buf = self._blank(cols, rows)

    def push_key(self, code):
        self._input.append(code)

    # -------- rendering for the browser: run-length-encoded rows --------

    def render_rows(self):
        rows_out = []
        for row in self._buf:
            runs = []
            cur_text, cur_style = "", None
            for ch, attr in row:
                style = _cell_style(attr)
                if style != cur_style:
                    if cur_text:
                        runs.append([cur_text, *cur_style])
                    cur_text, cur_style = ch, style
                else:
                    cur_text += ch
            if cur_text:
                runs.append([cur_text, *cur_style])
            rows_out.append(runs)
        return {"cols": self.cols, "rows": self.rows, "data": rows_out}


# ---- theme: 8 ANSI-ish colors resolved to hex for the browser renderer.
# Kept faithful to a plain terminal's ANSI palette - not skewed toward the
# page chrome's green-and-gold look, and not skewed toward any one site's
# in-game palette either, since the codec briefing (Olive/Locke/Ian/Rose/
# Daisy) and a few other fixed-pair reads always go through these 8
# regardless of which site's 256-color palette is currently applied. ----
_HEX = {
    COLOR_BLACK: "#0b0f0b", COLOR_RED: "#ff5a5a", COLOR_GREEN: "#9dff9d",
    COLOR_YELLOW: "#ffd24d", COLOR_BLUE: "#6a8caf", COLOR_MAGENTA: "#ff7ad1",
    COLOR_CYAN: "#7fe6ff", COLOR_WHITE: "#eafcea",
}
_DEFAULT_FG = "#9dff9d"
_DEFAULT_BG = "#060a06"


def _xterm256_hex(n):
    """xterm 256-color palette for indices 16-255 (the 6x6x6 color cube
    plus the grayscale ramp) - covers the extended concrete/steel/hazard-
    amber/blood-red shades ui.py's per-site palettes use once
    curses.COLORS >= 256. Indices 8-15 (bright basics) aren't used by
    this game and aren't handled - callers fall back to the defaults."""
    if 16 <= n <= 231:
        n -= 16
        r, n = divmod(n, 36)
        g, b = divmod(n, 6)
        steps = (0, 95, 135, 175, 215, 255)
        return "#%02x%02x%02x" % (steps[r], steps[g], steps[b])
    if 232 <= n <= 255:
        v = 8 + 10 * (n - 232)
        return "#%02x%02x%02x" % (v, v, v)
    return None


def _resolve_hex(color_idx):
    return _HEX.get(color_idx) or _xterm256_hex(color_idx)


def _cell_style(attr):
    pair = attr >> _PAIR_SHIFT
    style = attr & 0xFF
    fg, bg = _PAIRS.get(pair, (-1, -1))
    fg_hex = (_resolve_hex(fg) or _DEFAULT_FG) if fg != -1 else _DEFAULT_FG
    bg_hex = _resolve_hex(bg) if bg != -1 else None
    if style & A_REVERSE:
        fg_hex, bg_hex = (bg_hex or _DEFAULT_BG), fg_hex
    return (fg_hex, bg_hex, bool(style & A_BOLD), bool(style & A_DIM))
