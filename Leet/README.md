# L.E.E.T.

*a terminal-based tribute to Elite, by Float64*

You are an independent commander with a leased freighter, a handful of
credits, and a procedurally generated galaxy to make a living in. Dock
at stations to trade commodities, refit your ship, take on delivery and
bounty contracts, and build a combat reputation - or fly out into the
black and get yourself killed by pirates. Full 3D flight, first-person:
no yaw, roll then pitch to turn, throttle sets a cruising speed (and
holds past zero into a slower reverse) rather than free thrust, and
wireframe ships and a rotating station to fly into, just like the
original.

## Play

Open `index.html` in a browser (a Pyodide-powered build - first load
fetches the Python runtime, ~12 MB, cached after). Not hosted anywhere
yet; see `Terminal`'s and `TDFIF`'s READMEs in this project for how
those got a `float64co.github.io` link, if you want to set one up the
same way. Progress saves to that browser via localStorage (`Save
Commander Log` at a station) - it isn't synced anywhere else, and
clearing the browser's site data for this page will lose it.

## Run locally

    python3 leet.py

No dependencies beyond the Python standard library. Needs a real
terminal (curses) - at least 92x30.

## Controls

**Flight:** mouse aim - hold the left button and drag (`Seek Cursor`),
or hands-free with no button held (`Auto Seek Cursor`, the default);
`C` toggles between the two. Left/Right roll, Up/Down pitch, `,`/`.`
throttle down/up (holds past zero into a slower reverse), Space fires
the laser, `M` fires a missile at the locked target, Tab cycles the
target lock, `E` fires an ECM burst, `D` requests docking, `G` opens
the galaxy map, `Q`/Esc/Backspace backs out of a menu or opens the
pause menu, `?` shows the full in-game help overlay.

**Docked at a station:** Up/Down and Enter navigate the menus (Market,
Shipyard, Outfitting, Bulletin Board contracts, Commander Status, Refuel
& Repair); `Q`/Esc/Backspace backs out.

## Rebuild the browser build

    python3 build_web.py

Inlines `web_curses.py` (an in-browser curses shim), `leet.py` itself
(untouched), and `web_bridge.py` (glue) into `template.html` ->
`index.html`, the whole game as one self-contained, ship-anywhere file.
Re-run after changing any of those three files:

    python3 -m py_compile leet.py web_curses.py web_bridge.py
    python3 build_web.py

`leet.py` here is a plain copy of the standalone game (same file this
project's terminal build uses) - if you change the canonical copy
elsewhere, copy it back in here before rebuilding.

Two things this build carries that this project's other Pyodide ports
(`Terminal`, `TDFIF`) don't need, because they're single-file games with
mouse-drag-select and no save system, while L.E.E.T. is a single-file
game with continuous mouse-driven flight *and* a save/continue system:

- **Continuous mouse position.** `web_curses.py`'s `Screen.push_mouse()`
  coalesces consecutive, still-unconsumed pure-motion reports into the
  latest one instead of queueing every single browser `mousemove` event,
  so fast mouse movement can't outrun the game's own tick rate and build
  up an input backlog. A press or release is never coalesced away.
- **Save persistence.** `Game.save()` / `App._load_save()` in `leet.py`
  are completely unmodified - they still just call `open()` on
  `leet.SAVE_PATH` - but Pyodide's virtual filesystem is in-memory only
  and doesn't survive a page reload. `web_bridge.py` exposes
  `web_read_save()` for the JS side to mirror that file out to
  `localStorage` after every write, and template.html seeds it back into
  the virtual filesystem (via a `SEED_SAVE_TEXT` global, set before the
  bridge script runs) at the next boot, before the splash screen's "does
  a save exist" check ever runs.

Also unlike those two, this build does **not** speed up the tick rate
(`WEB_TICK_SPEEDUP = 1.0` in `web_bridge.py`): L.E.E.T.'s flight physics
- throttle easing, mouse-turn momentum spin-up/coast, laser tracer
duration, missile speed - are all tuned in real-world time against
`TICK_MS`, not just an animation-smoothness knob, so scaling the tick
rate would scale gameplay speed and balance right along with it. 1:1
keeps the browser build feeling identical to the standalone one.
