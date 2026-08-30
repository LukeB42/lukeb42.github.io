"""
L.E.E.T. web bridge.

Like Terminal's bridge, this just wires together the pieces the JS side
already loaded into sys.modules (see the boot sequence in template.html:
'curses' is the web_curses shim, 'leet' is the untouched game) and
exposes a handful of functions JS calls directly: push input, advance
exactly one tick, read back the rendered screen. There's no
curses.wrapper() call here - the web build owns the tick loop itself
(see web_tick()), so it drives App.step() directly instead of going
through App/main()'s blocking run_blocking(). Because that means
leet.main()'s own curses setup (color pairs, curs_set, mousemask, ...)
never runs either, this bridge repeats exactly that sequence itself
before constructing the App.

Two things this bridge carries that Terminal's doesn't, because leet.py
needs them and the RTS never did:

- Continuous mouse position. Terminal's box-select only needs the two
  corners of a drag (mousedown/mouseup), so its bridge has no "current
  position" concept at all. leet.py's flight controls need the cursor's
  *current* position every tick while dragging, and - in its default
  "Auto Seek Cursor" mode - even with no button held. web_mouse_move()
  below feeds that (see web_curses.py's push_mouse() for how the queue
  avoids building a backlog under fast mouse movement).

- Save persistence. Terminal and TDFIF have no save system at all, so
  their bridges never touch a filesystem. leet.py does (Game.save() /
  App._load_save() read and write leet.SAVE_PATH with plain open()
  calls, completely unmodified here) - but Pyodide's virtual filesystem
  is in-memory only and vanishes on reload, so nothing written there
  would survive a page refresh on its own. web_read_save() lets the JS
  side mirror the save file out to localStorage after every write, and
  a SEED_SAVE_TEXT global - set by JS *before* this script runs, only
  when localStorage actually has something saved - lets it write that
  content back into the virtual filesystem before the App (and its
  splash-screen "does a save exist" check) is ever constructed.
"""
import json
import os
import sys

curses = sys.modules["curses"]
leet = sys.modules["leet"]

_screen = curses.Screen(cols=120, rows=40)

_seed = globals().get("SEED_SAVE_TEXT")
if _seed:
    try:
        os.makedirs(os.path.dirname(leet.SAVE_PATH), exist_ok=True)
        with open(leet.SAVE_PATH, "w") as f:
            f.write(_seed)
    except OSError:
        pass

# Mirrors leet.main()'s own curses setup, minus the final blocking
# App(stdscr).run_blocking() call - this bridge drives App.step() itself.
curses.curs_set(0)
_screen.keypad(True)
curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
curses.mouseinterval(0)
curses.start_color()
curses.use_default_colors()
curses.init_pair(leet.CP_PLAYER, curses.COLOR_CYAN, -1)
curses.init_pair(leet.CP_HOSTILE, curses.COLOR_RED, -1)
curses.init_pair(leet.CP_NEUTRAL, curses.COLOR_WHITE, -1)
curses.init_pair(leet.CP_HUD, curses.COLOR_GREEN, -1)
curses.init_pair(leet.CP_DANGER, curses.COLOR_RED, -1)
curses.init_pair(leet.CP_WARN, curses.COLOR_YELLOW, -1)
curses.init_pair(leet.CP_POLICE, curses.COLOR_BLUE, -1)
curses.init_pair(leet.CP_REVERSE, curses.COLOR_BLACK, curses.COLOR_WHITE)

_app = leet.App(_screen)

# Unlike Terminal/TDFIF, the web build does NOT speed up leet.py's own
# tick rate: its flight physics (throttle easing, mouse-turn momentum
# spin-up/coast, laser tracer duration, missile speed...) are all tuned
# in real-world time against TICK_MS, not just an animation-smoothness
# knob, so scaling the tick rate would scale gameplay speed and balance
# right along with it. 1:1 keeps the browser build feeling identical to
# the standalone curses build.
WEB_TICK_SPEEDUP = 1.0


def web_min_size():
    return json.dumps({"cols": leet.MIN_TERM_W, "rows": leet.MIN_TERM_H})


def web_tick_ms():
    return leet.TICK_MS / WEB_TICK_SPEEDUP


def web_resize(cols, rows):
    _screen.resize(cols, rows)


def web_key(code):
    _screen.push_key(code)


def web_mouse_down(x, y):
    _screen.push_mouse(x, y, curses.BUTTON1_PRESSED)


def web_mouse_up(x, y):
    _screen.push_mouse(x, y, curses.BUTTON1_RELEASED)


def web_mouse_move(x, y):
    _screen.push_mouse(x, y, curses.REPORT_MOUSE_POSITION)


def web_read_save():
    """Current contents of the save file, for JS to mirror into
    localStorage, or "" if nothing has been saved yet this session."""
    try:
        with open(leet.SAVE_PATH) as f:
            return f.read()
    except OSError:
        return ""


def web_tick():
    _app.step()
    return json.dumps(_screen.render_rows())
