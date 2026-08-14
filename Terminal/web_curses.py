"""
Minimal in-memory curses shim for running terminal.py inside Pyodide.

Pyodide's CPython build ships no ncurses, and there's no real terminal
under a browser tab anyway. This implements exactly the slice of the
curses API terminal.py touches: a screen buffer with addch/addstr/
erase/refresh/getmaxyx, a tiny color-pair table, the handful of key
and mouse-button constants terminal.py compares against, and a
non-blocking getch()/getmouse() pair fed by push_key()/push_mouse()
from the JS side. There is no real device underneath - the browser
renders whatever's in the buffer (via Screen.render_rows()) and
forwards DOM events into the input queue.

terminal.py never imports this module by name. The web bridge script
registers an instance of it into sys.modules['curses'] before
terminal.py is loaded, so terminal.py's own `import curses` resolves
here instead of to a real (absent) curses.
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

# ---- attribute bits (style in the low byte; color pair packed above it) ----
A_NORMAL = 0
A_BOLD = 1 << 0
A_DIM = 1 << 1
A_REVERSE = 1 << 2
A_UNDERLINE = 1 << 3
_PAIR_SHIFT = 8

# ---- key constants: arbitrary but distinct. terminal.py only ever
# compares them against values this same module hands back from getch() ----
KEY_UP = 1001
KEY_DOWN = 1002
KEY_LEFT = 1003
KEY_RIGHT = 1004
KEY_ENTER = 1005
KEY_MOUSE = 1006
KEY_RESIZE = 1007

# ---- mouse button bits ----
BUTTON1_PRESSED = 1 << 0
BUTTON1_RELEASED = 1 << 1
BUTTON1_CLICKED = 1 << 2
BUTTON3_PRESSED = 1 << 3
BUTTON3_RELEASED = 1 << 4
BUTTON3_CLICKED = 1 << 5
ALL_MOUSE_EVENTS = (BUTTON1_PRESSED | BUTTON1_RELEASED | BUTTON1_CLICKED |
                     BUTTON3_PRESSED | BUTTON3_RELEASED | BUTTON3_CLICKED)
REPORT_MOUSE_POSITION = 1 << 6

_PAIRS = {0: (-1, -1)}
_current_screen = None


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


def mousemask(mask):
    return mask, mask


def mouseinterval(n):
    pass


def getmouse():
    """Real curses.getmouse() is a module-level call, not a stdscr method -
    it returns the event queued behind the KEY_MOUSE that getch() just
    returned. Mirror that here instead of hanging it off Screen."""
    if _current_screen is None:
        raise error("getmouse() called before any screen existed")
    return _current_screen.getmouse()


def wrapper(fn):
    """Real curses.wrapper() sets up/tears down a terminal. There's
    nothing to set up here; this exists only so `if __name__ ==
    "__main__": curses.wrapper(main)` doesn't blow up if this module
    ever gets exec'd directly instead of imported as 'terminal'."""
    return fn(Screen())


class Screen:
    """Stands in for stdscr: a (char, attr) grid plus input queues."""

    def __init__(self, cols=120, rows=40):
        self.cols = cols
        self.rows = rows
        self._buf = self._blank(cols, rows)
        self._input = []  # [('key', code), ...] / [('mouse', (id,x,y,z,bstate)), ...]
        self._pending_mouse = None
        global _current_screen
        _current_screen = self

    @staticmethod
    def _blank(cols, rows):
        return [[(' ', 0) for _ in range(cols)] for _ in range(rows)]

    # -------- curses-alike surface used by terminal.py --------

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

    def nodelay(self, flag):
        pass

    def timeout(self, ms):
        pass

    def getch(self):
        if not self._input:
            return -1
        kind, val = self._input.pop(0)
        if kind == "mouse":
            self._pending_mouse = val
            return KEY_MOUSE
        return val

    def getmouse(self):
        if self._pending_mouse is None:
            raise error("getmouse() called without a pending mouse event")
        m = self._pending_mouse
        self._pending_mouse = None
        return m

    # -------- driven by the JS bridge, not by terminal.py --------

    def resize(self, cols, rows):
        cols, rows = max(1, int(cols)), max(1, int(rows))
        if (cols, rows) != (self.cols, self.rows):
            self.cols, self.rows = cols, rows
            self._buf = self._blank(cols, rows)

    def push_key(self, code):
        self._input.append(("key", code))

    def push_mouse(self, x, y, bstate):
        self._input.append(("mouse", (0, x, y, 0, bstate)))

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


# ---- theme: 8 ANSI-ish colors resolved to hex for the browser renderer ----
_HEX = {
    COLOR_BLACK: "#0b0f0b", COLOR_RED: "#ff5a5a", COLOR_GREEN: "#9dff9d",
    COLOR_YELLOW: "#ffd24d", COLOR_BLUE: "#6a8caf", COLOR_MAGENTA: "#ff7ad1",
    COLOR_CYAN: "#7fe6ff", COLOR_WHITE: "#eafcea",
}
_DEFAULT_FG = "#9dff9d"
_DEFAULT_BG = "#060a06"


def _cell_style(attr):
    pair = attr >> _PAIR_SHIFT
    style = attr & 0xFF
    fg, bg = _PAIRS.get(pair, (-1, -1))
    fg_hex = _HEX.get(fg, _DEFAULT_FG) if fg != -1 else _DEFAULT_FG
    bg_hex = _HEX.get(bg) if bg != -1 else None
    if style & A_REVERSE:
        fg_hex, bg_hex = (bg_hex or _DEFAULT_BG), fg_hex
    return (fg_hex, bg_hex, bool(style & A_BOLD), bool(style & A_DIM), bool(style & A_UNDERLINE))
