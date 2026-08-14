"""
Terminal web bridge.

Unlike Solvent's web build (a sibling project's turn-based JSON command
API), terminal.py is a real-time curses grid game, so this bridge doesn't
model "views" or "commands" - it just wires together the pieces the JS
side already loaded into sys.modules (see the boot sequence in
template.html: 'curses' is the web_curses shim, 'terminal' is the
untouched game) and exposes a handful of functions JS calls directly:
push input, advance exactly one tick, read back the rendered screen.
"""
import json
import sys

curses = sys.modules["curses"]
terminal = sys.modules["terminal"]

_screen = curses.Screen(cols=120, rows=40)
_app = terminal.App(_screen)

# The web build runs at 2.5x terminal.py's own tick rate. This only changes
# how often the JS timer calls web_tick() (see web_tick_ms() below) - the
# standalone curses build still paces itself off terminal.TICK_MS directly
# and is untouched by this.
WEB_TICK_SPEEDUP = 2.5


def web_min_size():
    return json.dumps({"cols": terminal.MIN_TERM_W, "rows": terminal.MIN_TERM_H})


def web_tick_ms():
    return terminal.TICK_MS / WEB_TICK_SPEEDUP


def web_resize(cols, rows):
    _screen.resize(cols, rows)


def web_key(code):
    _screen.push_key(code)


def web_mouse_down(x, y):
    _screen.push_mouse(x, y, curses.BUTTON1_PRESSED)


def web_mouse_up(x, y):
    _screen.push_mouse(x, y, curses.BUTTON1_RELEASED)


def web_mouse_right(x, y):
    _screen.push_mouse(x, y, curses.BUTTON3_CLICKED)


def web_tick():
    _app.step()
    return json.dumps(_screen.render_rows())
