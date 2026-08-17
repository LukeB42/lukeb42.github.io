"""
Tour De Force web bridge.

Unlike Solvent's web build (a sibling project's turn-based JSON command
API), tdf.py is a real-time curses grid game, so this bridge doesn't
model "views" or "commands" - it just wires together the pieces the JS
side already loaded into sys.modules (see the boot sequence in
template.html: 'curses' is the web_curses shim, 'tdf' is the untouched
game) and exposes a handful of functions JS calls directly: push a
keystroke, advance exactly one tick, read back the rendered screen.

tdf.py is WASD-move / numpad-fire only - there's no mouse support to
wire up here, unlike the sibling RTS build this bridge was forked from.
"""
import json
import sys

curses = sys.modules["curses"]
game = sys.modules["tdf"]

_screen = curses.Screen(cols=120, rows=40)
_app = game.App(_screen)

# The web build runs at 2.5x tdf.py's own tick rate. This only changes how
# often the JS timer calls web_tick() (see web_tick_ms() below) - the
# standalone curses build still paces itself off tdf.TICK_MS directly and
# is untouched by this.
WEB_TICK_SPEEDUP = 2.5


def web_min_size():
    return json.dumps({"cols": game.MIN_TERM_W, "rows": game.MIN_TERM_H})


def web_tick_ms():
    return game.TICK_MS / WEB_TICK_SPEEDUP


def web_resize(cols, rows):
    _screen.resize(cols, rows)


def web_key(code):
    _screen.push_key(code)


def web_tick():
    _app.step()
    return json.dumps(_screen.render_rows())
