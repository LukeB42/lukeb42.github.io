# Tour De Force: Interdiction Force

*a squad RPG in the Tour De Force universe, by Float64*

2205. Ninety years after a nanomachine matrix answering to the name Gene
Carpenter walked out of a black site alone, DISA still officially doesn't
exist and still fields the one piece of hardware that makes any of this
survivable: the vapor suit. Eight billion pounds sterling of nanomachine
swarm per operative, four operatives this time - LOCKE SMITH, IAN
FORMANT, ROSE GARDNER, DAISY FIELDS - each suit soaking kinetic rounds
for feedstock and printing it back out as charge. Only bio-coated
necrotising-fasciitis rounds slip the weave: they build a load that eats
you alive for as long as you keep pushing, and burn off fast the moment
you hold position.

Walk a fogged, navigable map to find and avoid (or engage) hostile
squads, same as TDF - but contact hands off to a menu-driven, turn-based
squad battle instead of a real-time firefight. Manage suit charge
abilities, necrotic load, and front/back-row formation across seven
escalating sites, each unlocked by clearing the one before it.

## Play online

https://float64co.github.io/TDFIF/

Or open `index.html` yourself in a browser (a Pyodide-powered build -
first load fetches the Python runtime, ~12 MB, cached after).

## Run locally

    python3 run.py

No dependencies beyond the Python standard library. Needs a real
terminal (curses) - at least 92x27.

## Controls

**Overworld:** `WASD` / arrows move the fireteam · contact with an `S`
(hostile squad) or `H` (site boss) starts a battle · `Q` aborts the
mission.

**Battle:** `W`/`S` or arrows move the menu cursor · `Enter` / `Space`
confirms · `Q` / `Esc` / `Backspace` backs out of a submenu. Each turn: **Attack**
(free), **Ability** (costs Suit Charge - buffs, heals, purges necrotic
load, debuffs enemies), **Item** (Stims, Purge Canisters, Suit
Batteries), **Defend** (burns off your own necrotic load fast and
regens extra charge), **Formation** (swap front/back row), or **Flee**.

Kinetic fire from enemies can't hurt a suited operative - it just feeds
Suit Charge. Only necro rounds matter: they build a load on whoever's
hit, and any turn spent acting instead of defending drains HP off that
load. Front row draws more enemy fire; back row is safer but still
reachable by squad-wide effects.

## Structure

    tdfif/
        constants.py   cast, lore, mission tiers, briefings
        mapgen.py       tile-map generation + line of sight (from TDF)
        party.py        fireteam stats, suit abilities, inventory
        enemies.py      enemy templates per site + overworld encounter markers
        battle.py       turn-based battle engine (no curses - pure logic)
        battle_ui.py     battle menu navigation + rendering
        overworld.py     fogged map exploration + encounter contact
        ui.py            shared curses helpers, palettes, splash/mission/codec screens
        app.py           phase machine wiring it all together

## Rebuild the browser build

    python3 build_web.py

Writes every `tdfif/*.py` module, `web_curses.py` (an in-browser curses
shim), and `web_bridge.py` (glue) into `template.html` -> `index.html`,
the whole game as one self-contained, ship-anywhere file. TDFIF is a
real package with relative imports between its modules, so instead of
TDF's flat exec-into-a-module trick, the boot script writes each file
into Pyodide's virtual filesystem and does a genuine `import tdfif.app`
so the relative imports resolve normally. In-game colors are resolved
by `web_curses.py`'s own ANSI/xterm-256 hex table - faithful to a real
terminal's palette regardless of the page's green-and-gold chrome
around it.
