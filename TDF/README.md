# Tour De Force

*a DISA infiltration op, by Float64*

2115. You're Gene Carpenter, a field operative for DISA - the Department
of Integrated Security Activities. Your body died years ago; what walks
around now is a nanomachine matrix sculpted man-shaped, wearing a vapor
suit that costs more than most nations. Kinetic rounds bounce off it and
feed you unlimited ammo. Bio-coated necrotising-fasciitis rounds don't -
keep moving while infected and it eats you alive; hold still and the
swarm burns it off in seconds. Iona and Selma Shepard run your control
room. Get to extraction, or leave nobody standing to report you didn't.

Three sites, three looks: a sand-and-grass ruin, a concrete-and-steel
DUMB (deep underground military base) full of blast doors, and a
blood-red/blood-orange black site. Playable in a browser or a real
terminal.

## Run locally

    python3 tdf.py

No dependencies beyond the Python standard library.

## Controls

`WASD` / arrows move (standing still purges necrotic infection fast) ·
numpad `7` `8` `9` fire up-left / up / up-right · numpad `4` `6` fire
left / right · numpad `1` `2` `3` fire down-left / down / down-right ·
numpad `5` fires in your current facing · `Q` ends the infiltration /
backs out of menus. Ammo is unlimited - only bio-coated rounds are a
threat, and only while you're moving.

## Rebuild the browser build

    python3 build_web.py

Inlines `tdf.py`, `web_curses.py` (an in-browser curses shim), and
`web_bridge.py` into `template.html` → `index.html`, the whole game as
one self-contained, ship-anywhere file. Open `index.html` in a browser
to play the result.
