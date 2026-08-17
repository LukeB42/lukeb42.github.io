#!/usr/bin/env python3
"""
TOUR DE FORCE - a terminal infiltration game.

2115. You are GENE CARPENTER, a field operative for DISA - the Department
of Integrated Security Activities. Your body died years ago. What walks
around now is a directed nanomachine matrix sculpted into your old shape,
wearing the one piece of hardware that makes any of this survivable: a
vapor suit, 8-billion-pounds-sterling-worth of nanomachine swarm woven
into a kinetic-abatement layer that catches incoming slugs, strips them
for feedstock, and prints you fresh
ammunition out of your enemies' own gunfire. Regular bullets literally
cannot hurt you. You get paid in them.

The one thing the suit doesn't stop is bioweaponized ordnance: rounds
coated in a cultured necrotising fasciitis payload that ride straight
through the weave and force your nanoswarm to fight an infection instead
of holding your legs together. Keep moving with that infection active and
it eats you alive, slowly. Stand dead still and the swarm burns it off in
a couple of seconds. It takes a lot of that stuff, from a lot of guns, to
actually put you down.

Iona Shepard and Selma Shepard run your control room. DISA denies you
exist. Get to extraction, or leave nobody standing to report you didn't.

Controls:
    W A S D / Arrows   - move (also clears necrotic infection when you
                          stop: standing still purges it fast)
    Numpad 7 8 9        - fire diagonal-up-left / up / diagonal-up-right
    Numpad 4 6          - fire left / right
    Numpad 1 2 3        - fire diagonal-down-left / down / diagonal-down-right
    Numpad 5            - fire in whatever direction you're already facing
                          (most terminals can't tell numpad digits from the
                          top-row number keys anyway - either works)
    Q                   - end the infiltration / back out of menus
"""

import curses
import random
import textwrap

# --------------------------------------------------------------------------
# Layout / timing
# --------------------------------------------------------------------------

SIDEBAR_W = 30
TOP_H = 1
BOTTOM_H = 4
MIN_TERM_W = 76
MIN_TERM_H = 24

TICK_MS = 120

FOG_UNSEEN = 0
FOG_EXPLORED = 1
FOG_VISIBLE = 2

FLOOR = "."
GRASS = "\""
WALL = "#"
RUBBLE = ","
DOOR = "="       # big metal blast door - bunker levels only. Walkable, but
                 # blocks line of sight and gunfire like a wall does.
EXFIL_SYMBOL = "X"

ENV_RUIN = "ruin"      # open sand/grass compound, generate_world()
ENV_BUNKER = "bunker"  # underground concrete-and-steel base, generate_bunker_world()

VAPOR_SUIT_COST = "£8,000,000,000"

# --------------------------------------------------------------------------
# Player tuning
# --------------------------------------------------------------------------

PLAYER_MAX_HP = 220
ROUNDS_PER_ABSORBED_HIT = (2, 4)        # cosmetic tally, not a resource - firing is unlimited
PLAYER_DMG = 18
PLAYER_FIRE_COOLDOWN_TICKS = 1
PLAYER_VISION = 9

# Necrotic infection: builds only from bio-coated rounds. While the player
# moves it drains HP off the accumulated load every tick (slow, sustained
# bleed - needs many hits from many guns to actually be lethal). While the
# player holds perfectly still, the swarm burns the load off in a couple of
# ticks flat and no HP is lost. This is the entire threat model - regular
# rounds never touch HP at all, by design (see the suit).
NECRO_LOAD_PER_HIT = 9
NECRO_LOAD_CAP = 160
NECRO_DRAIN_DIVISOR = 9                 # hp lost/tick while moving = load // this
NECRO_IMMOBILE_DECAY = 45               # load burned off per tick while still

HIT_FLASH_TICKS = 3
AMMO_FLASH_TICKS = 3

BULLET_STEPS_PER_TICK = 2

WEAPON_VAPOR = "vapor"
WEAPON_NECRO = "necro"

WEAPON_META = {
    WEAPON_VAPOR: dict(glyph="g", pair_normal=8, pair_alert=8,
                        desc="Standard AP - the vapor suit eats it and prints you ammo."),
    WEAPON_NECRO: dict(glyph="b", pair_normal=9, pair_alert=9,
                        desc="Bio-coated round - necrotising fasciitis. Slips the suit."),
}

GUARD_ALERT_PERSIST_TICKS = 25
GUARD_PATROL_RADIUS = 6

# Radius of the fog-of-war circle lifted around the player's spawn point the
# instant a mission starts (see Game.__init__). Extraction is rolled to
# always land outside this circle, with a little headroom, so it can never
# spawn already-visible right on top of you.
START_REVEAL_RADIUS = 9
EXFIL_MARGIN = 6

# --------------------------------------------------------------------------
# Cast
# --------------------------------------------------------------------------

PLAYER_NAME = "Gene Carpenter"
HANDLER_IONA = "Iona Shepard"
HANDLER_SELMA = "Selma Shepard"
ORG_NAME = "DISA"
ORG_FULL_NAME = "Department of Integrated Security Activities"
MISSION_YEAR = 2115

# --------------------------------------------------------------------------
# Mission tiers
# --------------------------------------------------------------------------

LEVELS = [
    dict(name="Rustwater Compound", world_w=440, world_h=200,
         env=ENV_RUIN, palette="sand",
         n_vapor_guards=8, n_necro_guards=16,
         guard_hp=40, guard_range=9, guard_vision=8, guard_fire_cd=7,
         blurb="A scrap-fed militia outpost, sand and dead grass. Good place to learn the suit."),
    dict(name="Deniable Assets Site", world_w=600, world_h=256,
         env=ENV_BUNKER, palette="bunker",
         n_vapor_guards=10, n_necro_guards=48,
         guard_hp=55, guard_range=10, guard_vision=9, guard_fire_cd=6,
         blurb="A DUMB - deep underground military base. Poured concrete, blast doors, no sky."),
    dict(name="Force Majeure Black Site", world_w=760, world_h=320,
         env=ENV_RUIN, palette="blood",
         n_vapor_guards=13, n_necro_guards=88,
         guard_hp=70, guard_range=11, guard_vision=10, guard_fire_cd=5,
         blurb="The event no contract survives. Bio rounds everywhere you look."),
]

GAME_TITLE = "TOUR DE FORCE"

# --------------------------------------------------------------------------
# Codec briefings - Iona and Selma Shepard run mission control for DISA.
# One of these is picked at random for every deployment, independent of
# which site you're going to, so the same map never opens the same way
# twice. GENE lines are Gene Carpenter's (rare, clipped) side of the call.
# --------------------------------------------------------------------------

CODEC_THEMES = [
    dict(title="SNATCH AND GRAB", lines=[
        ("IONA", f"Gene, come in. DISA's tracking a stolen prototype weapons cache on site."),
        ("SELMA", "Whoever's sitting on it hasn't posted it anywhere. Yet. That's the whole rush."),
        ("IONA", "Get in, confirm it's real, get out. Nothing with your name on it if it goes loud."),
        ("SELMA", "Which, given the suit, is doing a lot of heavy lifting in that sentence."),
        ("GENE", "Copy. Moving in."),
    ]),
    dict(title="GHOST DEBT", lines=[
        ("SELMA", "So the good news is our asset wants out. The bad news is everyone there knows it."),
        ("IONA", "An engineer on-site built half the necrotic rounds you're about to eat. They want to defect."),
        ("SELMA", "DISA wants their notes more than we want them alive, for what it's worth."),
        ("IONA", "Don't repeat that. Get to extraction, Gene, we'll sort the paperwork after."),
        ("GENE", "Understood."),
    ]),
    dict(title="OFF THE BOOKS", lines=[
        ("IONA", "There's an auction running on-site. Nanotech blueprints, no export license, no questions."),
        ("SELMA", "Guest list reads like everyone DISA's not allowed to admit exists. Including you, technically."),
        ("IONA", "Shut it down. Buyers don't need to be breathing when you leave, but it's your call."),
        ("SELMA", "Iona means that. She really does mean that."),
        ("GENE", "Copy that."),
    ]),
    dict(title="STATIC ON THE LINE", lines=[
        ("SELMA", "Gene, this is a welfare check. DISA outstation on site went dark six hours ago."),
        ("IONA", "Last transmission wasn't words. Just channel noise. We don't like that."),
        ("SELMA", "Could be jamming. Could be everyone in there is already dead. Go find out which."),
        ("IONA", "Watch your integrity out there. If it's the second one, find out why before you're next."),
        ("GENE", "On my way in."),
    ]),
    dict(title="PAPER TRAIL", lines=[
        ("IONA", "There's a ledger on-site that ties this outfit's funding straight back to a DISA line item."),
        ("SELMA", "Which is awkward, because officially we've never heard of them."),
        ("IONA", "Pull the ledger, Gene. Whatever else happens on-site is secondary to that drive."),
        ("SELMA", "Don't lose the drive. We will absolutely lose you before we lose that drive."),
        ("GENE", "Noted."),
    ]),
    dict(title="CLEAN SWEEP", lines=[
        ("SELMA", "No subtlety on this one. DISA wants the site gone and nobody able to say why."),
        ("IONA", "Extraction opens the second there's nobody left standing to file a report."),
        ("SELMA", "Or you just walk to the marker and we call it a draw. Your funeral either way."),
        ("IONA", "Selma. -- Gene, use your judgment. Just don't leave a trail back to us."),
        ("GENE", "Copy. Starting the sweep."),
    ]),
    dict(title="SECOND OPINION", lines=[
        ("IONA", "We've got an operative in there, captured three days ago. Still alive, as of an hour ago."),
        ("SELMA", "Their interrogators aren't known for patience. That clock is not on your side, Gene."),
        ("IONA", "Get to extraction with them breathing and this whole thing was worth it."),
        ("SELMA", "Get there without them, and it very much was not. No pressure."),
        ("GENE", "Moving."),
    ]),
    dict(title="VAPOR TRAIL", lines=[
        ("SELMA", "Somebody on-site has a full schematic set for a suit just like yours."),
        ("IONA", "Eight billion pounds of R&D, reverse-engineered off a corpse we didn't recover cleanly enough."),
        ("SELMA", "DISA would very much like to not have a second one of you walking around. No offense."),
        ("IONA", "None taken, I assume. Recover or destroy the schematics. Your call which."),
        ("GENE", "Copy. Moving to confirm."),
    ]),
    dict(title="QUIET WORD", lines=[
        ("IONA", "This one's political. A DISA liaison is meeting someone on-site we can't be seen meeting."),
        ("SELMA", "You're not there. This conversation isn't happening. You know the drill by now, Gene."),
        ("IONA", "Confirm the meet went how it was supposed to, and get out without being seen doing it."),
        ("SELMA", "Try not to shoot anyone important. Or anyone at all, ideally, but we know how that goes."),
        ("GENE", "Understood. Going dark."),
    ]),
]

SPLASH_TEXT = """Your body died years ago. What answers to your name now is a directed
nanomachine matrix, sculpted man-shaped out of habit, wearing the one
piece of hardware standing between you and a very short career: a vapor
suit, 8-billion-pounds-sterling-worth of nanomachine swarm woven into a
kinetic-abatement layer. Regular gunfire cannot hurt you - the suit
strips it for feedstock and prints you fresh
ammunition out of whatever they just shot you with.
They know that. So some of them load bioweapon rounds instead - cultured
necrotising fasciitis, riding straight through the weave. Keep moving
while that's in you and it eats you alive. Stand still and the swarm
burns it off in seconds. It'll take a lot of guns, a lot of hits, to
actually finish the job.
Get to extraction. Or don't leave anyone who can say you didn't."""

# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

_next_id = [1]


def _new_id():
    n = _next_id[0]
    _next_id[0] += 1
    return n


def _sign(n):
    return (n > 0) - (n < 0)


def line_of_sight(grid, x0, y0, x1, y1):
    """Bresenham walk from (x0,y0) to (x1,y1); False if a WALL or a closed
    blast DOOR sits strictly between the two endpoints."""
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while (x, y) != (x1, y1):
        if (x, y) != (x0, y0) and grid[y][x] in (WALL, DOOR):
            return False
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return True


DIR_GLYPH = {
    (0, -1): "|", (0, 1): "|", (-1, 0): "-", (1, 0): "-",
    (1, -1): "/", (-1, 1): "/", (1, 1): "\\", (-1, -1): "\\",
}

# numpad-style direction keys; movement is WASD/arrows exclusively, this is
# fire-only. Most terminals can't distinguish a physical numpad from the
# top-row digits when NumLock is on, so plain 1-9 works either way.
NUMPAD_DIRS = {
    ord('8'): (0, -1), ord('2'): (0, 1), ord('4'): (-1, 0), ord('6'): (1, 0),
    ord('7'): (-1, -1), ord('9'): (1, -1), ord('1'): (-1, 1), ord('3'): (1, 1),
}

# --------------------------------------------------------------------------
# Map generation
# --------------------------------------------------------------------------

def generate_world(width, height):
    grid = [[FLOOR for _ in range(width)] for _ in range(height)]

    for x in range(width):
        grid[0][x] = WALL
        grid[height - 1][x] = WALL
    for y in range(height):
        grid[y][0] = WALL
        grid[y][width - 1] = WALL

    n_blocks = (width * height) // 200
    for _ in range(n_blocks):
        bw = random.randint(2, 6)
        bh = random.randint(2, 5)
        bx = random.randint(2, width - bw - 2)
        by = random.randint(2, height - bh - 2)
        for y in range(by, by + bh):
            for x in range(bx, bx + bw):
                grid[y][x] = WALL

    n_patches = max(8, (width * height) // 550)
    for _ in range(n_patches):
        cx = random.randint(2, width - 3)
        cy = random.randint(2, height - 3)
        r = random.randint(5, 13)
        core2 = (r * 0.6) ** 2
        r2 = r * r
        for yy in range(max(1, cy - r), min(height - 1, cy + r + 1)):
            for xx in range(max(1, cx - r), min(width - 1, cx + r + 1)):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                if d2 > r2 or grid[yy][xx] != FLOOR:
                    continue
                if d2 <= core2 or random.random() < 0.75:
                    grid[yy][xx] = GRASS

    for _ in range(width * height // 70):
        x = random.randint(1, width - 2)
        y = random.randint(1, height - 2)
        if grid[y][x] == FLOOR:
            grid[y][x] = RUBBLE

    return grid


def clear_area(grid, cx, cy, radius):
    for y in range(max(1, cy - radius), min(len(grid) - 1, cy + radius + 1)):
        for x in range(max(1, cx - radius), min(len(grid[0]) - 1, cx + radius + 1)):
            grid[y][x] = FLOOR


def _carve_room(grid, x0, y0, w, h):
    """Carve a concrete-floored room, clamped to stay inside the perimeter
    wall. Returns its (x0, y0, x1, y1) bounds, inclusive."""
    width, height = len(grid[0]), len(grid)
    x0 = max(1, min(width - 3, x0))
    y0 = max(1, min(height - 3, y0))
    x1 = max(x0 + 1, min(width - 2, x0 + w))
    y1 = max(y0 + 1, min(height - 2, y0 + h))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            grid[y][x] = FLOOR
    return (x0, y0, x1, y1)


def _carve_corridor(grid, x0, y0, x1, y1, door_chance=0.55):
    """L-shaped single-width corridor between two points, with a chance of
    a blast DOOR planted at each end - the compartmentalized-bunker feel."""
    width, height = len(grid[0]), len(grid)
    pts = []
    if random.random() < 0.5:
        for x in range(min(x0, x1), max(x0, x1) + 1):
            pts.append((x, y0))
        for y in range(min(y0, y1), max(y0, y1) + 1):
            pts.append((x1, y))
    else:
        for y in range(min(y0, y1), max(y0, y1) + 1):
            pts.append((x0, y))
        for x in range(min(x0, x1), max(x0, x1) + 1):
            pts.append((x, y1))
    for x, y in pts:
        if 1 <= x < width - 1 and 1 <= y < height - 1 and grid[y][x] == WALL:
            grid[y][x] = FLOOR
    for x, y in (pts[0], pts[-1]) if pts else ():
        if 1 <= x < width - 1 and 1 <= y < height - 1 and random.random() < door_chance:
            grid[y][x] = DOOR


def generate_bunker_world(width, height, anchor):
    """A DUMB - deep underground military base. Solid poured concrete
    (WALL) by default, hollowed into a chain of rooms linked by single-
    width corridors gated with big metal blast doors. `anchor` is the
    player's spawn point; the first room is carved around it so spawn is
    always inside the connected network, not walled off in a pocket."""
    grid = [[WALL for _ in range(width)] for _ in range(height)]
    ax, ay = anchor

    rw, rh = random.randint(8, 12), random.randint(6, 9)
    rooms = [_carve_room(grid, ax - rw // 2, ay - rh // 2, rw, rh)]

    n_rooms = max(14, (width * height) // 1600)
    for _ in range(n_rooms):
        rw, rh = random.randint(6, 14), random.randint(5, 10)
        rx = random.randint(2, max(3, width - rw - 3))
        ry = random.randint(2, max(3, height - rh - 3))
        room = _carve_room(grid, rx, ry, rw, rh)
        prev = rooms[-1]
        cx0, cy0 = (prev[0] + prev[2]) // 2, (prev[1] + prev[3]) // 2
        cx1, cy1 = (room[0] + room[2]) // 2, (room[1] + room[3]) // 2
        _carve_corridor(grid, cx0, cy0, cx1, cy1)
        rooms.append(room)

    # sparse debris/rubble for texture - no grass, this is all poured concrete
    for _ in range(width * height // 140):
        x = random.randint(1, width - 2)
        y = random.randint(1, height - 2)
        if grid[y][x] == FLOOR and random.random() < 0.5:
            grid[y][x] = RUBBLE

    for x in range(width):
        grid[0][x] = WALL
        grid[height - 1][x] = WALL
    for y in range(height):
        grid[y][0] = WALL
        grid[y][width - 1] = WALL

    return grid


# --------------------------------------------------------------------------
# Entities
# --------------------------------------------------------------------------

class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.hp = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP
        self.rounds_absorbed = 0  # cosmetic - the suit's synth hopper never runs dry
        self.necro_load = 0
        self.facing = (0, 1)
        self.fire_cooldown = 0
        self.moved_this_tick = False
        self.hit_flash = 0
        self.ammo_flash = 0
        self.low_hp_warned = False
        self.alive = True


class Guard:
    def __init__(self, x, y, weapon, hp, rng, vision, fire_cd):
        self.id = _new_id()
        self.x = x
        self.y = y
        self.spawn_x = x
        self.spawn_y = y
        self.weapon = weapon
        self.hp = hp
        self.max_hp = hp
        self.rng = rng
        self.vision = vision
        self.fire_cd_max = fire_cd
        self.fire_cooldown = 0
        self.alert = False
        self.alert_timer = 0
        self.patrol_target = None
        self.alive = True


class Bullet:
    def __init__(self, x, y, dx, dy, owner, weapon=None, dmg=0):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.owner = owner  # "player" or "enemy"
        self.weapon = weapon
        self.dmg = dmg
        self.alive = True


# --------------------------------------------------------------------------
# Game
# --------------------------------------------------------------------------

class Game:
    def __init__(self, stdscr, level=None):
        self.stdscr = stdscr
        self.level = level or LEVELS[0]
        self.world_w = self.level["world_w"]
        self.world_h = self.level["world_h"]

        apply_palette(self.level.get("palette", "sand"))

        self.start_pos = (5, 5)
        if self.level.get("env", ENV_RUIN) == ENV_BUNKER:
            self.grid = generate_bunker_world(self.world_w, self.world_h, self.start_pos)
        else:
            self.grid = generate_world(self.world_w, self.world_h)
        self.fog = [[FOG_UNSEEN] * self.world_w for _ in range(self.world_h)]

        clear_area(self.grid, *self.start_pos, 4)

        # Every non-wall cell, built once - used to place extraction and
        # guards so both always land somewhere actually reachable, which
        # matters once the bunker's sparse room-and-corridor floor makes
        # blind random-coordinate sampling unreliable.
        self._open_cells = [(x, y) for y in range(self.world_h) for x in range(self.world_w)
                             if self.grid[y][x] != WALL]

        self.exfil_pos = self._pick_exfil_pos()
        clear_area(self.grid, *self.exfil_pos, 4)

        self.player = Player(*self.start_pos)
        self.guards = []
        self.bullets = []
        self._spawn_guards()

        self.messages = []
        self.tick = 0
        self.running = True
        self.win = None
        self.win_reason = None

        self.camera_x, self.camera_y = 0, 0
        self._recenter_camera(force=True)
        self.reveal(*self.start_pos, START_REVEAL_RADIUS)

        self.log(f"VAPOR SUIT ONLINE - {VAPOR_SUIT_COST} of hardware, powered up.")

    # ---------------------- setup ----------------------

    def _pick_exfil_pos(self):
        """Roll an open tile for the extraction marker that's guaranteed to
        sit outside the fog circle __init__ lifts around the spawn point
        (START_REVEAL_RADIUS + EXFIL_MARGIN of headroom), so it can never
        spawn already visible. Sampled from the actual reachable floor
        (self._open_cells) rather than blind coordinates, since the
        bunker's floor is sparse enough that blind rejection sampling
        would miss it far too often."""
        min_d2 = (START_REVEAL_RADIUS + EXFIL_MARGIN) ** 2
        sx, sy = self.start_pos
        candidates = [(x, y) for (x, y) in self._open_cells
                      if (x - sx) ** 2 + (y - sy) ** 2 >= min_d2]
        if candidates:
            return random.choice(candidates)
        # Fallback for oddly cramped maps: the single open tile farthest
        # from spawn, whatever that distance turns out to be.
        return max(self._open_cells, key=lambda p: (p[0] - sx) ** 2 + (p[1] - sy) ** 2)

    def _open_tile_near(self, cx, cy, occupied, max_radius=12):
        for r in range(1, max_radius + 1):
            candidates = []
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    x, y = cx + dx, cy + dy
                    if 1 <= x < self.world_w - 1 and 1 <= y < self.world_h - 1:
                        if self.grid[y][x] != WALL and (x, y) not in occupied:
                            candidates.append((x, y))
            if candidates:
                return random.choice(candidates)
        return cx, cy

    def _spawn_guards(self):
        occupied = {self.start_pos, self.exfil_pos}
        counts = [(WEAPON_VAPOR, self.level["n_vapor_guards"]),
                  (WEAPON_NECRO, self.level["n_necro_guards"])]
        for weapon, count in counts:
            for _ in range(count):
                cx, cy = random.choice(self._open_cells)
                x, y = self._open_tile_near(cx, cy, occupied)
                occupied.add((x, y))
                g = Guard(x, y, weapon, self.level["guard_hp"], self.level["guard_range"],
                           self.level["guard_vision"], self.level["guard_fire_cd"])
                self.guards.append(g)

    def log(self, text):
        self.messages.append(text)
        self.messages = self.messages[-3:]

    # ---------------------- fog of war ----------------------

    def reveal(self, cx, cy, radius):
        r2 = radius * radius
        for dy in range(-radius, radius + 1):
            y = cy + dy
            if y < 0 or y >= self.world_h:
                continue
            for dx in range(-radius, radius + 1):
                x = cx + dx
                if x < 0 or x >= self.world_w:
                    continue
                if dx * dx + dy * dy <= r2:
                    self.fog[y][x] = FOG_VISIBLE

    def map_percent(self):
        seen = sum(1 for row in self.fog for v in row if v != FOG_UNSEEN)
        return int(seen * 100 / (self.world_w * self.world_h))

    # ---------------------- occupancy ----------------------

    def guard_at(self, x, y, exclude=None):
        for g in self.guards:
            if g.alive and g.x == x and g.y == y and g is not exclude:
                return g
        return None

    def tile_free(self, x, y, exclude=None):
        if not (0 <= x < self.world_w and 0 <= y < self.world_h):
            return False
        if self.grid[y][x] == WALL:
            return False
        if self.guard_at(x, y, exclude=exclude):
            return False
        if self.player.alive and (x, y) == (self.player.x, self.player.y) and exclude is not self.player:
            return False
        return True

    def move_towards(self, entity, tx, ty):
        dx, dy = _sign(tx - entity.x), _sign(ty - entity.y)
        candidates = []
        if dx and dy:
            candidates.append((entity.x + dx, entity.y + dy))
        if dx:
            candidates.append((entity.x + dx, entity.y))
        if dy:
            candidates.append((entity.x, entity.y + dy))
        for nx, ny in candidates:
            if self.tile_free(nx, ny, exclude=entity):
                entity.x, entity.y = nx, ny
                return True
        return False

    # ---------------------- player actions ----------------------

    def try_move_player(self, dx, dy):
        p = self.player
        nx, ny = p.x + dx, p.y + dy
        p.facing = (dx, dy)
        if self.tile_free(nx, ny, exclude=p):
            p.x, p.y = nx, ny
            p.moved_this_tick = True
            self.reveal(p.x, p.y, PLAYER_VISION)

    def try_fire_player(self, direction):
        # The suit's printer keeps up indefinitely - firing is never
        # ammo-gated, only paced by the fire cooldown below.
        p = self.player
        if not p.alive or p.fire_cooldown > 0:
            return
        if direction != (0, 0):
            p.facing = direction
        p.fire_cooldown = PLAYER_FIRE_COOLDOWN_TICKS
        dx, dy = p.facing
        self.bullets.append(Bullet(p.x, p.y, dx, dy, "player", dmg=PLAYER_DMG))

    # ---------------------- guard AI ----------------------

    def _guard_patrol(self, g):
        if g.patrol_target is None or (g.x, g.y) == g.patrol_target or random.random() < 0.03:
            rx = g.spawn_x + random.randint(-GUARD_PATROL_RADIUS, GUARD_PATROL_RADIUS)
            ry = g.spawn_y + random.randint(-GUARD_PATROL_RADIUS, GUARD_PATROL_RADIUS)
            rx = max(1, min(self.world_w - 2, rx))
            ry = max(1, min(self.world_h - 2, ry))
            g.patrol_target = (rx, ry)
        if random.random() < 0.5:
            self.move_towards(g, *g.patrol_target)

    def _guard_ai(self):
        p = self.player
        for g in self.guards:
            if not g.alive:
                continue
            if g.fire_cooldown > 0:
                g.fire_cooldown -= 1

            dx, dy = p.x - g.x, p.y - g.y
            dist2 = dx * dx + dy * dy
            sees = (p.alive and dist2 <= g.vision * g.vision and
                    line_of_sight(self.grid, g.x, g.y, p.x, p.y))

            if sees:
                if not g.alert:
                    self.log("! A guard spots you.")
                g.alert = True
                g.alert_timer = GUARD_ALERT_PERSIST_TICKS
            elif g.alert:
                g.alert_timer -= 1
                if g.alert_timer <= 0:
                    g.alert = False

            if not g.alert:
                self._guard_patrol(g)
                continue

            aligned = dx == 0 or dy == 0 or abs(dx) == abs(dy)
            in_range = dist2 <= g.rng * g.rng
            if sees and aligned and in_range and g.fire_cooldown <= 0:
                bx, by = _sign(dx), _sign(dy)
                self.bullets.append(Bullet(g.x, g.y, bx, by, "enemy",
                                            weapon=g.weapon, dmg=0))
                g.fire_cooldown = g.fire_cd_max
            else:
                self.move_towards(g, p.x, p.y)

    # ---------------------- bullets / hits ----------------------

    def _damage_guard(self, g, dmg):
        g.hp -= dmg
        if g.hp <= 0:
            g.alive = False
            self.log(f"Guard down ({g.hp + dmg} hp).")

    def _hit_player(self, weapon):
        p = self.player
        if weapon == WEAPON_VAPOR:
            p.rounds_absorbed += random.randint(*ROUNDS_PER_ABSORBED_HIT)
            p.ammo_flash = AMMO_FLASH_TICKS
        elif weapon == WEAPON_NECRO:
            p.necro_load = min(NECRO_LOAD_CAP, p.necro_load + NECRO_LOAD_PER_HIT)
            p.hit_flash = HIT_FLASH_TICKS
            self.log("Bio round through the weave. Necrotic load rising.")

    def _update_bullets(self):
        survivors = []
        for b in self.bullets:
            for _ in range(BULLET_STEPS_PER_TICK):
                if not b.alive:
                    break
                b.x += b.dx
                b.y += b.dy
                if not (0 <= b.x < self.world_w and 0 <= b.y < self.world_h):
                    b.alive = False
                    break
                if self.grid[b.y][b.x] in (WALL, DOOR):
                    b.alive = False
                    break
                if b.owner == "player":
                    g = self.guard_at(b.x, b.y)
                    if g:
                        self._damage_guard(g, b.dmg)
                        b.alive = False
                        break
                else:
                    if self.player.alive and (b.x, b.y) == (self.player.x, self.player.y):
                        self._hit_player(b.weapon)
                        b.alive = False
                        break
            if b.alive:
                survivors.append(b)
        self.bullets = survivors

    def _apply_necrotic_load(self):
        p = self.player
        if p.necro_load <= 0:
            return
        if p.moved_this_tick:
            drain = p.necro_load // NECRO_DRAIN_DIVISOR
            if drain > 0:
                p.hp -= drain
        else:
            p.necro_load = max(0, p.necro_load - NECRO_IMMOBILE_DECAY)

    # ---------------------- tick update ----------------------

    def update(self):
        self.tick += 1
        p = self.player

        if p.fire_cooldown > 0:
            p.fire_cooldown -= 1
        if p.hit_flash > 0:
            p.hit_flash -= 1
        if p.ammo_flash > 0:
            p.ammo_flash -= 1

        self._guard_ai()
        self._update_bullets()
        self._apply_necrotic_load()

        if p.alive and not p.low_hp_warned and p.hp <= p.max_hp * 0.25:
            p.low_hp_warned = True
            self.log("IONA: Gene, integrity's critical - hold still and let the swarm work!")

        if p.hp <= 0 and p.alive:
            p.alive = False
            self.win = False
            self.win_reason = "Necrotic overload. The swarm couldn't keep up."
            self.running = False
            return

        if p.alive and (p.x, p.y) == self.exfil_pos:
            self.win = True
            self.win_reason = "Extracted clean."
            self.running = False
            return

        if p.alive and self.guards and all(not g.alive for g in self.guards):
            self.win = True
            self.win_reason = "Nobody left to file a report."
            self.running = False
            return

    # ---------------------- camera ----------------------

    def viewport_size(self):
        max_y, max_x = self.stdscr.getmaxyx()
        view_w = max(10, max_x - SIDEBAR_W - 1)
        view_h = max(5, max_y - TOP_H - BOTTOM_H)
        return view_w, view_h

    def _recenter_camera(self, force=False):
        view_w, view_h = self.viewport_size()
        margin = 5
        if force:
            self.camera_x = max(0, min(max(0, self.world_w - view_w), self.player.x - view_w // 2))
            self.camera_y = max(0, min(max(0, self.world_h - view_h), self.player.y - view_h // 2))
            return
        if self.player.x < self.camera_x + margin:
            self.camera_x = max(0, self.player.x - margin)
        elif self.player.x > self.camera_x + view_w - margin:
            self.camera_x = self.player.x - view_w + margin
        if self.player.y < self.camera_y + margin:
            self.camera_y = max(0, self.player.y - margin)
        elif self.player.y > self.camera_y + view_h - margin:
            self.camera_y = self.player.y - view_h + margin
        self.camera_x = max(0, min(max(0, self.world_w - view_w), self.camera_x))
        self.camera_y = max(0, min(max(0, self.world_h - view_h), self.camera_y))

    # ---------------------- rendering ----------------------

    def _safe_addstr(self, y, x, text, attr=0):
        max_y, max_x = self.stdscr.getmaxyx()
        if y < 0 or y >= max_y or x >= max_x:
            return
        text = text[:max(0, max_x - x)]
        if not text:
            return
        try:
            self.stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass

    def _safe_addch(self, y, x, ch, attr=0):
        max_y, max_x = self.stdscr.getmaxyx()
        if 0 <= y < max_y and 0 <= x < max_x - 1:
            try:
                self.stdscr.addch(y, x, ch, attr)
            except curses.error:
                pass

    def draw(self):
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        if max_y < MIN_TERM_H or max_x < MIN_TERM_W:
            msg = f"Terminal too small ({max_x}x{max_y}). Need at least {MIN_TERM_W}x{MIN_TERM_H}."
            self._safe_addstr(0, 0, msg, curses.color_pair(5))
            self.stdscr.refresh()
            return

        self._recenter_camera()
        view_w, view_h = self.viewport_size()

        self._draw_topbar(max_x)
        self._draw_map(view_w, view_h)
        self._draw_sidebar(view_w, view_h)
        self._draw_bottombar(view_h, max_x)

        self.stdscr.refresh()

    def _draw_topbar(self, max_x):
        elapsed = self.tick * TICK_MS // 1000
        alive_guards = sum(1 for g in self.guards if g.alive)
        left = (f"{GAME_TITLE} // HP:{self.player.hp}/{self.player.max_hp}  "
                f"AMMO:∞  GUARDS:{alive_guards}  "
                f"T+{elapsed // 60:02d}:{elapsed % 60:02d}")
        self._safe_addstr(0, 0, left, curses.color_pair(4))
        right = f"Map: {self.map_percent()}%"
        self._safe_addstr(0, max(0, max_x - len(right)), right, curses.color_pair(4) | curses.A_BOLD)

    def _draw_map(self, view_w, view_h):
        for sy in range(view_h):
            wy = self.camera_y + sy
            if wy >= self.world_h:
                break
            for sx in range(view_w):
                wx = self.camera_x + sx
                if wx >= self.world_w:
                    break
                fog = self.fog[wy][wx]
                if fog == FOG_UNSEEN:
                    continue
                tile = self.grid[wy][wx]
                dim = curses.A_DIM if fog == FOG_EXPLORED else 0
                if tile == WALL:
                    self._safe_addch(sy + TOP_H, sx, WALL, curses.color_pair(3) | dim)
                elif tile == DOOR:
                    self._safe_addch(sy + TOP_H, sx, DOOR, curses.color_pair(15) | curses.A_BOLD | dim)
                elif tile == RUBBLE:
                    self._safe_addch(sy + TOP_H, sx, RUBBLE, curses.color_pair(3) | dim)
                elif tile == GRASS:
                    self._safe_addch(sy + TOP_H, sx, GRASS, curses.color_pair(12) | dim)
                else:
                    self._safe_addch(sy + TOP_H, sx, FLOOR, curses.color_pair(11) | dim)

        ex, ey = self.exfil_pos
        if self.fog[ey][ex] != FOG_UNSEEN:
            sx, sy = ex - self.camera_x, ey - self.camera_y
            if 0 <= sx < view_w and 0 <= sy < view_h:
                self._safe_addch(sy + TOP_H, sx, EXFIL_SYMBOL, curses.color_pair(13) | curses.A_BOLD)

        for g in self.guards:
            if not g.alive:
                continue
            if self.fog[g.y][g.x] != FOG_VISIBLE:
                continue
            sx, sy = g.x - self.camera_x, g.y - self.camera_y
            if 0 <= sx < view_w and 0 <= sy < view_h:
                meta = WEAPON_META[g.weapon]
                attr = curses.color_pair(meta["pair_normal"]) | curses.A_BOLD
                if g.alert:
                    attr |= curses.A_REVERSE
                self._safe_addch(sy + TOP_H, sx, meta["glyph"], attr)

        for b in self.bullets:
            sx, sy = b.x - self.camera_x, b.y - self.camera_y
            if 0 <= sx < view_w and 0 <= sy < view_h:
                glyph = DIR_GLYPH.get((b.dx, b.dy), "*")
                if b.owner == "player":
                    pair = 14
                elif b.weapon == WEAPON_NECRO:
                    pair = 9
                else:
                    pair = 8
                self._safe_addch(sy + TOP_H, sx, glyph, curses.color_pair(pair))

        p = self.player
        if p.alive:
            sx, sy = p.x - self.camera_x, p.y - self.camera_y
            if 0 <= sx < view_w and 0 <= sy < view_h:
                if p.hit_flash > 0:
                    attr = curses.color_pair(9) | curses.A_BOLD | curses.A_REVERSE
                elif p.ammo_flash > 0:
                    attr = curses.color_pair(8) | curses.A_BOLD | curses.A_REVERSE
                else:
                    attr = curses.color_pair(1) | curses.A_BOLD
                self._safe_addch(sy + TOP_H, sx, "@", attr)

    def _bar(self, ratio, width, invert=False):
        ratio = max(0.0, min(1.0, ratio))
        filled = int(round(ratio * width))
        bar = "#" * filled + "-" * (width - filled)
        good, mid, bad = (5, 6, 4) if invert else (4, 6, 5)
        if ratio > 0.66:
            pair = bad if invert else good
        elif ratio > 0.33:
            pair = mid
        else:
            pair = good if invert else bad
        return bar, pair

    def _draw_sidebar(self, view_w, view_h):
        col = view_w + 1
        row = TOP_H
        p = self.player

        self._safe_addstr(row, col, "-- OPERATIVE STATUS --", curses.color_pair(4))
        row += 2

        self._safe_addstr(row, col, "INTEGRITY", curses.color_pair(4))
        row += 1
        bar, pair = self._bar(p.hp / p.max_hp if p.max_hp else 0, SIDEBAR_W - 8)
        self._safe_addstr(row, col, f"[{bar}]", curses.color_pair(pair))
        row += 2

        self._safe_addstr(row, col, "NECROTIC LOAD", curses.color_pair(4))
        row += 1
        bar, pair = self._bar(p.necro_load / NECRO_LOAD_CAP, SIDEBAR_W - 8, invert=True)
        self._safe_addstr(row, col, f"[{bar}]", curses.color_pair(pair))
        row += 1
        if p.necro_load == 0:
            state = "clean"
        elif p.moved_this_tick:
            state = "MOVING - draining"
        else:
            state = "still - purging"
        self._safe_addstr(row, col, f"  ({state})"[:SIDEBAR_W - 1], curses.A_DIM)
        row += 2

        self._safe_addstr(row, col, "AMMO: UNLIMITED", curses.color_pair(1) | curses.A_BOLD)
        row += 1
        self._safe_addstr(row, col, f"  rounds absorbed: {p.rounds_absorbed}", curses.A_DIM)
        row += 2

        self._safe_addstr(row, col, "VAPOR SUIT", curses.color_pair(6) | curses.A_BOLD)
        row += 1
        self._safe_addstr(row, col, VAPOR_SUIT_COST, curses.color_pair(6) | curses.A_BOLD)
        row += 2

        alive_guards = [g for g in self.guards if g.alive]
        alert_n = sum(1 for g in alive_guards if g.alert)
        self._safe_addstr(row, col, f"GUARDS: {len(alive_guards)} ({alert_n} alert)", curses.color_pair(4))
        row += 2

        self._safe_addstr(row, col, "-- WEAPON KEY --", curses.color_pair(4))
        row += 1
        self._safe_addstr(row, col, "g kinetic - harmless, tops up the tally", curses.color_pair(8))
        row += 1
        self._safe_addstr(row, col, "b bio-round - drains you moving", curses.color_pair(9))
        row += 1
        self._safe_addstr(row, col, "X extraction point", curses.color_pair(13))

    def _draw_bottombar(self, view_h, max_x):
        y = TOP_H + view_h
        controls = "Move:WASD/Arrows  Numpad 1-9:Fire 8 dirs (5=facing)  Q:End"
        self._safe_addstr(y, 0, controls[:max_x], curses.color_pair(4))
        for i, msg in enumerate(self.messages):
            self._safe_addstr(y + 1 + i, 0, msg[:max_x], curses.color_pair(6))

    # ---------------------- input ----------------------

    def handle_key(self, key):
        moves = {
            ord('w'): (0, -1), curses.KEY_UP: (0, -1),
            ord('s'): (0, 1), curses.KEY_DOWN: (0, 1),
            ord('a'): (-1, 0), curses.KEY_LEFT: (-1, 0),
            ord('d'): (1, 0), curses.KEY_RIGHT: (1, 0),
        }
        if key in moves:
            self.try_move_player(*moves[key])
            return

        if key in NUMPAD_DIRS:
            self.try_fire_player(NUMPAD_DIRS[key])
            return

        if key == ord('5'):
            self.try_fire_player((0, 0))
            return

        if key in (ord('q'), ord('Q')):
            self.running = False
            self.win = None
            self.win_reason = "Infiltration aborted."
            return

    # ---------------------- main loop ----------------------

    def tick_once(self):
        self.draw()
        # moved_this_tick reflects the *previous* tick's input while draw()
        # (just above) reads it for the HUD label; clear it only now, right
        # before this tick's own input can set it again.
        self.player.moved_this_tick = False
        key = self.stdscr.getch()
        if key == curses.KEY_RESIZE:
            pass
        elif key != -1:
            self.handle_key(key)
        self.update()

    def render_end_screen(self):
        self.stdscr.erase()
        if self.win is True:
            headline = "EXTRACTED. CONTRACT COMPLETE."
        elif self.win is False:
            headline = "OPERATIVE DOWN."
        else:
            headline = "INFILTRATION ABORTED."
        lines = [
            headline,
            self.win_reason or "",
            f"Time on site: {self.tick * TICK_MS // 1000}s",
            f"Map explored: {self.map_percent()}%",
            f"Rounds absorbed by the suit: {self.player.rounds_absorbed}",
            "",
            "Press any key to continue...",
        ]
        for i, line in enumerate(lines):
            self._safe_addstr(i, 0, line, curses.color_pair(4) | curses.A_BOLD)
        self.stdscr.refresh()


# --------------------------------------------------------------------------
# Splash / mission select / app phase machine
# --------------------------------------------------------------------------

def draw_splash(stdscr):
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    lines = [GAME_TITLE, ""] + SPLASH_TEXT.split("\n") + ["", "Press any key to deploy..."]
    start_y = max(0, (max_y - len(lines)) // 2)
    for i, line in enumerate(lines):
        y = start_y + i
        if y >= max_y:
            break
        x = max(0, (max_x - len(line)) // 2)
        attr = curses.A_BOLD if i == 0 else 0
        try:
            stdscr.addstr(y, x, line[:max_x - 1], curses.color_pair(MENU_PAIR_CHROME) | attr)
        except curses.error:
            pass
    stdscr.refresh()


def draw_mission_select(stdscr, index):
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    title = "CHOOSE YOUR SITE"
    try:
        stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title, curses.color_pair(MENU_PAIR_CHROME) | curses.A_BOLD)
    except curses.error:
        pass
    row = 3
    for i, lvl in enumerate(LEVELS):
        marker = ">" if i == index else " "
        total_guards = lvl['n_vapor_guards'] + lvl['n_necro_guards']
        line = (f"{marker} {i + 1}) {lvl['name']}  ({lvl['world_w']}x{lvl['world_h']}, "
                f"{total_guards} guards: {lvl['n_vapor_guards']} kinetic / {lvl['n_necro_guards']} bio)")
        attr = curses.A_REVERSE if i == index else curses.color_pair(MENU_PAIR_CHROME)
        try:
            stdscr.addstr(row, 4, line[:max_x - 5], attr)
        except curses.error:
            pass
        row += 1
        if i == index:
            try:
                stdscr.addstr(row, 8, lvl["blurb"][:max_x - 9], curses.A_DIM)
            except curses.error:
                pass
            row += 1
        row += 1
    hint = f"Up/Down: choose   Enter/1-{len(LEVELS)}: deploy   Q: quit"
    try:
        stdscr.addstr(row + 1, 4, hint, curses.color_pair(MENU_PAIR_CHROME))
    except curses.error:
        pass
    stdscr.refresh()


# The codec briefing is explicitly exempt from the in-mission blood-red /
# blood-orange palette (see init_colors) - it gets its own dedicated pair
# block (20-23) so Iona, Selma and Gene stay visually distinct on the call.
CODEC_PAIR_CHROME = 20
CODEC_SPEAKER_PAIRS = {"IONA": 21, "SELMA": 22, "GENE": 23}


def draw_codec(stdscr, theme, index):
    """One frame of the pre-mission codec call: every line up through
    `index` is shown, oldest dimmed out, the newest one lit up - like
    scrollback on an MGS-style codec screen. `index` is the count of lines
    revealed so far, minus one (i.e. lines[:index + 1] is on screen)."""
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    header = f"INCOMING TRANSMISSION :: {theme['title']}"
    sub = f"{ORG_NAME} SECURE CHANNEL // {HANDLER_IONA} & {HANDLER_SELMA} TO {PLAYER_NAME.upper()}"
    try:
        stdscr.addstr(1, max(0, (max_x - len(header)) // 2), header, curses.color_pair(CODEC_PAIR_CHROME) | curses.A_BOLD)
        stdscr.addstr(2, max(0, (max_x - len(sub)) // 2), sub[:max_x - 1], curses.A_DIM)
    except curses.error:
        pass

    lines = theme["lines"]
    shown = lines[:index + 1]
    row = 4
    for i, (speaker, text) in enumerate(shown):
        is_current = (i == len(shown) - 1)
        pair = CODEC_SPEAKER_PAIRS.get(speaker, CODEC_PAIR_CHROME)
        label_attr = curses.color_pair(pair) | curses.A_BOLD
        body_attr = 0
        if not is_current:
            label_attr |= curses.A_DIM
            body_attr = curses.A_DIM
        try:
            stdscr.addstr(row, 4, f"[{speaker}]", label_attr)
        except curses.error:
            pass
        for wline in textwrap.wrap(text, max(20, max_x - 12)):
            row += 1
            try:
                stdscr.addstr(row, 6, wline, body_attr)
            except curses.error:
                pass
        row += 2
        if row >= max_y - 3:
            break

    hint = "Press any key to continue..." if index < len(lines) - 1 else "Press any key to deploy..."
    try:
        stdscr.addstr(max_y - 2, 4, hint, curses.color_pair(CODEC_PAIR_CHROME))
    except curses.error:
        pass
    stdscr.refresh()


def draw_closed(stdscr):
    stdscr.erase()
    try:
        stdscr.addstr(0, 0, "Session closed.", curses.color_pair(CLOSED_PAIR_PHOSPHOR) | curses.A_BOLD)
    except curses.error:
        pass
    stdscr.refresh()


class App:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.phase = "splash"
        self.mission_index = 0
        self.briefing_theme = None
        self.briefing_index = 0
        self.game = None
        self.done = False
        stdscr.timeout(TICK_MS)

    def _begin_briefing(self):
        """A random codec theme, independent of the site picked, so the
        same map never opens with the same call twice."""
        self.briefing_theme = random.choice(CODEC_THEMES)
        self.briefing_index = 0
        self.phase = "briefing"

    def _start_game(self):
        self.game = Game(self.stdscr, LEVELS[self.mission_index])
        self.phase = "game"

    def step(self):
        if self.phase == "splash":
            draw_splash(self.stdscr)
            if self.stdscr.getch() != -1:
                self.phase = "mission"

        elif self.phase == "mission":
            draw_mission_select(self.stdscr, self.mission_index)
            key = self.stdscr.getch()
            if key in (curses.KEY_UP, ord('w'), ord('W')):
                self.mission_index = (self.mission_index - 1) % len(LEVELS)
            elif key in (curses.KEY_DOWN, ord('s'), ord('S')):
                self.mission_index = (self.mission_index + 1) % len(LEVELS)
            elif key in (10, 13, curses.KEY_ENTER):
                self._begin_briefing()
            elif key in (ord('q'), ord('Q')):
                self.phase = "closed"
                self.done = True
            elif key != -1 and ord('1') <= key <= ord(str(len(LEVELS))):
                self.mission_index = key - ord('1')
                self._begin_briefing()

        elif self.phase == "briefing":
            draw_codec(self.stdscr, self.briefing_theme, self.briefing_index)
            key = self.stdscr.getch()
            if key != -1:
                self.briefing_index += 1
                if self.briefing_index >= len(self.briefing_theme["lines"]):
                    self._start_game()

        elif self.phase == "game":
            self.game.tick_once()
            if not self.game.running:
                self.phase = "end"

        elif self.phase == "end":
            self.game.render_end_screen()
            if self.stdscr.getch() != -1:
                self.phase = "mission"

        elif self.phase == "closed":
            draw_closed(self.stdscr)

    def run_blocking(self):
        while not self.done:
            self.step()


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

MENU_PAIR_CHROME = 24   # splash / mission-select screens - fixed, independent
                         # of whichever level's palette last ran
CLOSED_PAIR_PHOSPHOR = 25  # "Session closed." - classic phosphor green, on its own

# Pair numbers shared by every per-level palette below:
#   1 player   3 walls        4 HUD text   5 danger        6 warnings/log
#   8 vapor(g) 9 necro/bio(b) 11 floor     12 grass/debris 13 exfil  14 player bullets
#   15 blast door (bunker only, but every palette defines it for safety)
def _palette_sand(has_256):
    """Rustwater Compound - the original sand-and-dead-grass ruin."""
    return {1: curses.COLOR_CYAN, 3: curses.COLOR_WHITE, 4: curses.COLOR_GREEN,
            5: curses.COLOR_RED, 6: curses.COLOR_YELLOW, 8: curses.COLOR_MAGENTA,
            9: curses.COLOR_RED, 11: curses.COLOR_YELLOW, 12: curses.COLOR_GREEN,
            13: curses.COLOR_GREEN, 14: curses.COLOR_WHITE, 15: curses.COLOR_WHITE}


def _palette_bunker(has_256):
    """Deniable Assets Site - a DUMB: poured concrete, steel, hazard-amber
    blast doors, no sky, no grass."""
    if has_256:
        concrete, concrete_lt, steel, hazard = 240, 250, 111, 178
    else:
        concrete, concrete_lt, steel, hazard = curses.COLOR_WHITE, curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_YELLOW
    return {1: curses.COLOR_CYAN, 3: concrete, 4: steel, 5: curses.COLOR_RED,
            6: hazard, 8: steel, 9: curses.COLOR_RED, 11: concrete_lt,
            12: concrete, 13: hazard, 14: curses.COLOR_WHITE, 15: hazard}


def _palette_blood(has_256):
    """Force Majeure Black Site - strict two-tone blood-red / blood-orange."""
    if has_256:
        blood_red, blood_orange = 88, 166  # #870000 / #d75f00
    else:
        blood_red, blood_orange = curses.COLOR_RED, curses.COLOR_YELLOW
    return {1: blood_orange, 3: blood_red, 4: blood_orange, 5: blood_red,
            6: blood_red, 8: blood_orange, 9: blood_red, 11: blood_orange,
            12: blood_red, 13: blood_orange, 14: blood_orange, 15: blood_red}


PALETTES = {"sand": _palette_sand, "bunker": _palette_bunker, "blood": _palette_blood}


def apply_palette(name):
    """Re-point the shared map/HUD pair numbers at a given level's palette.
    Called once per mission start (Game.__init__), so the whole in-game
    look - map tiles, HUD, sidebar - reskins per level. The codec call and
    the splash/menu screens use their own dedicated pairs and are never
    touched by this."""
    has_256 = curses.COLORS >= 256
    for pair_num, color in PALETTES[name](has_256).items():
        curses.init_pair(pair_num, color, -1)


def init_colors():
    """Sets up the pairs that stay fixed for the whole app session: the
    codec-call speaker colors and the menu chrome. Per-level in-mission
    colors are applied later, per mission, via apply_palette()."""
    curses.start_color()
    curses.use_default_colors()

    menu_color = 166 if curses.COLORS >= 256 else curses.COLOR_YELLOW
    curses.init_pair(MENU_PAIR_CHROME, menu_color, -1)
    curses.init_pair(CLOSED_PAIR_PHOSPHOR, curses.COLOR_GREEN, -1)

    curses.init_pair(CODEC_PAIR_CHROME, curses.COLOR_YELLOW, -1)
    curses.init_pair(CODEC_SPEAKER_PAIRS["IONA"], curses.COLOR_CYAN, -1)
    curses.init_pair(CODEC_SPEAKER_PAIRS["SELMA"], curses.COLOR_MAGENTA, -1)
    curses.init_pair(CODEC_SPEAKER_PAIRS["GENE"], curses.COLOR_GREEN, -1)

    apply_palette(LEVELS[0]["palette"])  # sane default before any mission starts


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    init_colors()
    App(stdscr).run_blocking()


if __name__ == "__main__":
    curses.wrapper(main)
