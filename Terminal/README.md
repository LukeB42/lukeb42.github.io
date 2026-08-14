# Terminal

*a cyberpunk Command & Conquer-alike, by Float64*

**Play online: https://float64co.github.io/Terminal/**

Command a mercenary workshop, spawn mech "frames," and grind a rival
outfit's base to scrap across six escalating contracts — Rustwater
Irregulars up through Force Majeure. Real-time combat, fog of war, and
multi-unit selection, playable with mouse or keyboard, in a browser or
a real terminal.

## Run locally

    python3 terminal.py

No dependencies beyond the Python standard library.

## Controls

Arrows/WASD move the cursor · Enter/Space select or order · mouse
click/drag/right-click work too · `A` select everything · `1`-`9` recall
a control group, `G` then a digit assigns one · `[`/`]` cycle frames ·
`P` autoplay · `B` build (also where extra workshops are commissioned,
at the cursor) · `{`/`}` cycle the active workshop (missions 4-6 only,
where workshops are also selectable and groupable) · `S` stop · `Q` end
mission, then back to menu. Frames slowly self-repair over time.

## Rebuild the browser build

    python3 build_web.py

Inlines `terminal.py`, `web_curses.py` (an in-browser curses shim), and
`web_bridge.py` into `template.html` → `index.html`, the whole game as
one self-contained, ship-anywhere file.
