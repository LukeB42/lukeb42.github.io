# SOLVENT — browser build
*a Chrome Dogs operation, by Float64*

## Files
- `index.html` — the whole game, self-contained. Ship this.
- `solvent.py` — game logic + terminal (curses) version. Single source of truth.
- `web_api.py` — JSON bridge between the logic and the browser UI.
- `template.html` + `build_web.py` — rebuild `index.html` after changing the game:
  `python3 solvent.py --selftest && python3 build_web.py`

## GitHub Pages / blog
Copy `index.html` anywhere in your published site, e.g. `blog/static/solvent/index.html`,
then link to `/solvent/` or embed in a post:

    <iframe src="/solvent/" width="100%" height="720"
            style="border:1px solid #123a12; background:#060a06"></iframe>

Keyboard needs focus — click inside the frame once. Everything also works by mouse/tap.

## Offline play
The page pulls the Python runtime (Pyodide, ~12 MB, cached) from jsDelivr on first
load. For fully offline / self-hosted:

1. Download `pyodide-0.26.4.tar.bz2` from https://github.com/pyodide/pyodide/releases
2. Unpack it next to `index.html` as `./pyodide/`
3. In `index.html`, change `PYODIDE_BASE` to `"./pyodide/"`

Then serve the folder with any static server (`python3 -m http.server`). Opening via
`file://` won't work — browsers block WASM loading from the filesystem.

## Saves
No cookies, no tracking, nothing stored in the browser: **Export save file** on the
HQ menu downloads your campaign as JSON; **Import save file** loads it back. Terminal
and web saves use the same format.

## Act II — The Production War

Beating Force Majeure no longer ends the campaign: it opens **Act II**, where
combat shifts from four-frame squads to a C&C-style numbers game.

- **Formations, not frames.** Your surviving Act I roster converts into
  formation units, plus six free Haunds and a 4,000cr signing bonus.
- **Turns.** Each turn: collect revenue (800cr base + held theaters), pay
  2% fleet upkeep (unpaid crews desert), build units up to factory capacity,
  then attack a theater or consolidate.
- **Five theaters**, taken in order, each with a garrison, per-turn revenue,
  and one-off spoils (the Foundry Cities add production capacity; the Orbital
  Downlink grants the orbital relay tech). The finale is Counterparty — every
  creditor you ever burned, incorporated.
- **Battles** resolve as aggregate exchanges with a role counter system
  (line shreds swarm, air hunts armor, armor anchors the line, orbital
  arrays strike first) and per-round doctrine choices: BALANCED, FOCUS
  ARMOR, SWEEP SWARMS, SCREEN, ENGINEERS, auto-doctrine, or break off.
- **Commit what you can afford to lose.** Only committed formations fight;
  a defeat writes off the entire committed force. Reserves are safe.
- Per-credit stat efficiency rises with unit size, so cheap-mass spam is a
  trap — swarm earns its keep by screening and countering line units.

Act I saves are forward-compatible: a version-1 save that has beaten Force
Majeure imports straight into Act II. In-progress Act I saves continue
unchanged.
