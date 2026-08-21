"""
TDFIF web bridge.

By the time this runs, the boot script has already written every
tdfif/*.py file into Pyodide's virtual filesystem and put its parent
directory on sys.path, so `import tdfif` here is a completely ordinary
package import - relative imports inside tdfif/*.py (from . import
constants, etc.) work exactly as they do under the real interpreter.
'curses' in sys.modules is the web_curses shim, registered before that
import happened.

TDFIF is a menu-driven turn-based game, not a real-time one, but the
overworld phase still runs on a tick loop (guard patrol/alert AI), so
this bridge is shaped the same way TDF's is: push a keystroke, advance
exactly one App.step(), read back the rendered screen. There's no
curses.wrapper() call here - the web build owns the tick loop itself
(see web_tick()), so it drives App.step() directly instead of going
through App/run.py's blocking run_blocking().
"""
import json
import sys

curses = sys.modules["curses"]

from tdfif import overworld as tdfif_overworld
from tdfif import ui as tdfif_ui
from tdfif.app import App

_screen = curses.Screen(cols=120, rows=40)
tdfif_ui.init_colors()
_app = App(_screen)

# The web build runs at 2.5x TDFIF's own overworld tick rate. This only
# changes how often the JS timer calls web_tick() (see web_tick_ms()
# below) - the standalone curses build still paces itself off
# overworld.TICK_MS directly and is untouched by this.
WEB_TICK_SPEEDUP = 2.5


def web_min_size():
    return json.dumps({"cols": tdfif_overworld.MIN_TERM_W, "rows": tdfif_overworld.MIN_TERM_H})


def web_tick_ms():
    return tdfif_overworld.TICK_MS / WEB_TICK_SPEEDUP


def web_resize(cols, rows):
    _screen.resize(cols, rows)


def web_key(code):
    _screen.push_key(code)


def web_tick():
    _app.step()
    return json.dumps(_screen.render_rows())
