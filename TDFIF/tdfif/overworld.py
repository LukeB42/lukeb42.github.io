"""Real-time exploration screen: walk the squad around a fogged map,
avoid or make contact with hostile-squad markers, reach extraction.
Structurally the same loop as TDF's Game class, minus bullets - contact
with a marker hands off to battle.py instead of exchanging fire in place."""

import random

import curses

from . import mapgen, ui
from .constants import (DOOR, ENV_BUNKER, EXFIL_SYMBOL, FLOOR, FOG_UNSEEN,
                         FOG_VISIBLE, FOG_EXPLORED, GRASS, NECRO_LOAD_CAP,
                         NECRO_OVERWORLD_DECAY_PER_TICK, RUBBLE, TIER_DISPLAY_NAMES,
                         WALL, WEAPON_NECRO)
from .enemies import EncounterMarker

SIDEBAR_W = 36
TOP_H = 1
BOTTOM_H = 5
MIN_TERM_W = 92
MIN_TERM_H = 27

TICK_MS = 110
PLAYER_VISION = 9
START_REVEAL_RADIUS = 8
EXFIL_MARGIN = 6
ALERT_PERSIST_TICKS = 25


class Overworld:
    def __init__(self, stdscr, level, party, inventory):
        self.stdscr = stdscr
        self.level = level
        self.party = party
        self.inventory = inventory

        self.world_w = level["world_w"]
        self.world_h = level["world_h"]
        ui.apply_palette(level["palette"])

        self.start_pos = (5, 5)
        if level["env"] == ENV_BUNKER:
            self.grid = mapgen.generate_bunker_world(self.world_w, self.world_h, self.start_pos)
        else:
            self.grid = mapgen.generate_world(self.world_w, self.world_h)
        self.fog = [[FOG_UNSEEN] * self.world_w for _ in range(self.world_h)]
        mapgen.clear_area(self.grid, *self.start_pos, 4)

        self._open_cells = [(x, y) for y in range(self.world_h) for x in range(self.world_w)
                             if self.grid[y][x] != WALL]

        self.exfil_pos = self._pick_exfil_pos()
        mapgen.clear_area(self.grid, *self.exfil_pos, 4)

        self.px, self.py = self.start_pos
        self.markers = []
        self._spawn_markers()

        self.messages = []
        self.tick = 0
        self.running = True
        self.result = None          # None | "extracted" | "aborted"
        self.pending_encounter = None

        self.camera_x, self.camera_y = 0, 0
        self._recenter_camera(force=True)
        self.reveal(*self.start_pos, START_REVEAL_RADIUS)

        self.log(f"{len(self.party)} vapor suits online - {level['name']}.")

    # ---------------------- setup ----------------------

    def _pick_exfil_pos(self):
        min_d2 = (START_REVEAL_RADIUS + EXFIL_MARGIN) ** 2
        sx, sy = self.start_pos
        candidates = [(x, y) for (x, y) in self._open_cells
                      if (x - sx) ** 2 + (y - sy) ** 2 >= min_d2]
        if candidates:
            return random.choice(candidates)
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

    def _spawn_markers(self):
        occupied = {self.start_pos, self.exfil_pos}
        n = self.level["n_squads"]
        boss = self.level.get("boss_squad", False)
        for i in range(n):
            is_boss = boss and i == n - 1
            if is_boss:
                cx, cy = self.exfil_pos
            else:
                cx, cy = random.choice(self._open_cells)
            x, y = self._open_tile_near(cx, cy, occupied)
            occupied.add((x, y))
            m = EncounterMarker(x, y, self.level["tier"], self.level["squad_size"],
                                 self.level["vapor_bias"], boss=is_boss)
            self.markers.append(m)

    def log(self, text):
        self.messages.append(text)
        self.messages = self.messages[-4:]

    def relocate_marker_away(self, marker, min_dist=10):
        min_d2 = min_dist * min_dist
        candidates = [(x, y) for (x, y) in self._open_cells
                      if (x - self.px) ** 2 + (y - self.py) ** 2 >= min_d2]
        if candidates:
            marker.x, marker.y = random.choice(candidates)
        marker.alert = False
        marker.alert_timer = 0
        marker.patrol_target = None

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

    # ---------------------- movement ----------------------

    def tile_free(self, x, y):
        if not (0 <= x < self.world_w and 0 <= y < self.world_h):
            return False
        return self.grid[y][x] != WALL

    def try_move_player(self, dx, dy):
        nx, ny = self.px + dx, self.py + dy
        if self.tile_free(nx, ny):
            self.px, self.py = nx, ny
            self.reveal(self.px, self.py, PLAYER_VISION)

    # ---------------------- marker AI ----------------------

    def _marker_patrol(self, m):
        if m.patrol_target is None or (m.x, m.y) == m.patrol_target or random.random() < 0.03:
            rx = m.spawn_x + random.randint(-m.patrol_radius, m.patrol_radius)
            ry = m.spawn_y + random.randint(-m.patrol_radius, m.patrol_radius)
            rx = max(1, min(self.world_w - 2, rx))
            ry = max(1, min(self.world_h - 2, ry))
            m.patrol_target = (rx, ry)
        if random.random() < 0.5:
            m.x, m.y = mapgen.move_towards(self.grid, self.world_w, self.world_h,
                                            m.x, m.y, *m.patrol_target, self.tile_free)

    def _tick_markers(self):
        for m in self.markers:
            if not m.alive:
                continue
            dx, dy = self.px - m.x, self.py - m.y
            dist2 = dx * dx + dy * dy
            sees = dist2 <= m.vision * m.vision and mapgen.line_of_sight(self.grid, m.x, m.y, self.px, self.py)

            if sees:
                if not m.alert:
                    tier_name = TIER_DISPLAY_NAMES.get(m.tier, m.tier.title())
                    self.log(f"! A hostile squad ({tier_name}) spots the fireteam.")
                m.alert = True
                m.alert_timer = ALERT_PERSIST_TICKS
            elif m.alert:
                m.alert_timer -= 1
                if m.alert_timer <= 0:
                    m.alert = False

            if m.alert:
                m.x, m.y = mapgen.move_towards(self.grid, self.world_w, self.world_h,
                                                m.x, m.y, self.px, self.py, self.tile_free)
            else:
                self._marker_patrol(m)

            if max(abs(self.px - m.x), abs(self.py - m.y)) <= 1:
                self.pending_encounter = m
                return

    # ---------------------- tick update ----------------------

    def _regen_party(self):
        for p in self.party:
            if p.alive and p.necro_load > 0:
                p.necro_load = max(0, p.necro_load - NECRO_OVERWORLD_DECAY_PER_TICK)

    def update(self):
        self.tick += 1
        self._regen_party()
        if self.pending_encounter is not None:
            return
        self._tick_markers()
        if self.pending_encounter is not None:
            return
        if (self.px, self.py) == self.exfil_pos:
            self.result = "extracted"
            self.running = False
            return
        if self.markers and all(not m.alive for m in self.markers):
            self.result = "extracted"
            self.running = False

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
            self.camera_x = max(0, min(max(0, self.world_w - view_w), self.px - view_w // 2))
            self.camera_y = max(0, min(max(0, self.world_h - view_h), self.py - view_h // 2))
            return
        if self.px < self.camera_x + margin:
            self.camera_x = max(0, self.px - margin)
        elif self.px > self.camera_x + view_w - margin:
            self.camera_x = self.px - view_w + margin
        if self.py < self.camera_y + margin:
            self.camera_y = max(0, self.py - margin)
        elif self.py > self.camera_y + view_h - margin:
            self.camera_y = self.py - view_h + margin
        self.camera_x = max(0, min(max(0, self.world_w - view_w), self.camera_x))
        self.camera_y = max(0, min(max(0, self.world_h - view_h), self.camera_y))

    # ---------------------- rendering ----------------------

    def draw(self):
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        if max_y < MIN_TERM_H or max_x < MIN_TERM_W:
            msg = f"Terminal too small ({max_x}x{max_y}). Need at least {MIN_TERM_W}x{MIN_TERM_H}."
            ui.safe_addstr(self.stdscr, 0, 0, msg, curses.color_pair(ui.PAIR_DANGER))
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
        alive_squads = sum(1 for m in self.markers if m.alive)
        left = (f"{self.level['name'].upper()} // SQUADS:{alive_squads}  "
                f"T+{elapsed // 60:02d}:{elapsed % 60:02d}")
        ui.safe_addstr(self.stdscr, 0, 0, left, curses.color_pair(ui.PAIR_HUD))
        right = f"Map: {self.map_percent()}%"
        ui.safe_addstr(self.stdscr, 0, max(0, max_x - len(right)), right,
                        curses.color_pair(ui.PAIR_HUD) | curses.A_BOLD)

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
                    ui.safe_addch(self.stdscr, sy + TOP_H, sx, WALL, curses.color_pair(ui.PAIR_WALL) | dim)
                elif tile == DOOR:
                    ui.safe_addch(self.stdscr, sy + TOP_H, sx, DOOR, curses.color_pair(ui.PAIR_DOOR) | curses.A_BOLD | dim)
                elif tile == RUBBLE:
                    ui.safe_addch(self.stdscr, sy + TOP_H, sx, RUBBLE, curses.color_pair(ui.PAIR_WALL) | dim)
                elif tile == GRASS:
                    ui.safe_addch(self.stdscr, sy + TOP_H, sx, GRASS, curses.color_pair(ui.PAIR_GRASS) | dim)
                else:
                    ui.safe_addch(self.stdscr, sy + TOP_H, sx, FLOOR, curses.color_pair(ui.PAIR_FLOOR) | dim)

        ex, ey = self.exfil_pos
        if self.fog[ey][ex] != FOG_UNSEEN:
            sx, sy = ex - self.camera_x, ey - self.camera_y
            if 0 <= sx < view_w and 0 <= sy < view_h:
                ui.safe_addch(self.stdscr, sy + TOP_H, sx, EXFIL_SYMBOL, curses.color_pair(ui.PAIR_EXFIL) | curses.A_BOLD)

        for m in self.markers:
            if not m.alive or self.fog[m.y][m.x] != FOG_VISIBLE:
                continue
            sx, sy = m.x - self.camera_x, m.y - self.camera_y
            if 0 <= sx < view_w and 0 <= sy < view_h:
                pair = ui.PAIR_ELITE if m.boss else (ui.PAIR_NECRO if m.weapon == WEAPON_NECRO else ui.PAIR_VAPOR)
                attr = curses.color_pair(pair) | curses.A_BOLD
                if m.alert:
                    attr |= curses.A_REVERSE
                glyph = "H" if m.boss else "S"
                ui.safe_addch(self.stdscr, sy + TOP_H, sx, glyph, attr)

        sx, sy = self.px - self.camera_x, self.py - self.camera_y
        if 0 <= sx < view_w and 0 <= sy < view_h:
            ui.safe_addch(self.stdscr, sy + TOP_H, sx, "@", curses.color_pair(ui.PAIR_PLAYER) | curses.A_BOLD)

    def _draw_sidebar(self, view_w, view_h):
        col = view_w + 1
        row = TOP_H
        ui.safe_addstr(self.stdscr, row, col, "-- FIRETEAM --", curses.color_pair(ui.PAIR_HUD))
        row += 2
        for p in self.party:
            tag = "" if p.alive else " [DOWN]"
            ui.safe_addstr(self.stdscr, row, col, f"{p.name}{tag}"[:SIDEBAR_W - 1],
                            curses.color_pair(ui.PAIR_HUD) | curses.A_BOLD)
            row += 1
            hb, hp_pair = ui.bar(p.hp / p.max_hp if p.max_hp else 0, 16)
            ui.safe_addstr(self.stdscr, row, col, f"HP [{hb}] {p.hp:3d}/{p.max_hp}", curses.color_pair(hp_pair))
            row += 1
            sb, _ = ui.bar(p.sc / p.max_sc if p.max_sc else 0, 16)
            ui.safe_addstr(self.stdscr, row, col, f"SC [{sb}] {p.sc:3d}/{p.max_sc}", curses.color_pair(ui.PAIR_ACCENT))
            row += 1
            nb, n_pair = ui.bar(p.necro_load / NECRO_LOAD_CAP, 16, invert=True)
            ui.safe_addstr(self.stdscr, row, col, f"NL [{nb}] {p.necro_load:3d}", curses.color_pair(n_pair))
            row += 2

        ui.safe_addstr(self.stdscr, row, col, "-- INVENTORY --", curses.color_pair(ui.PAIR_HUD))
        row += 1
        for name, count in self.inventory.items.items():
            ui.safe_addstr(self.stdscr, row, col, f"{name}: {count}", curses.A_DIM)
            row += 1
        row += 1
        ui.safe_addstr(self.stdscr, row, col, "-- KEY --", curses.color_pair(ui.PAIR_HUD))
        row += 1
        ui.safe_addstr(self.stdscr, row, col, "S hostile squad  H site boss", curses.A_DIM)
        row += 1
        ui.safe_addstr(self.stdscr, row, col, "X extraction point", curses.color_pair(ui.PAIR_EXFIL))

    def _draw_bottombar(self, view_h, max_x):
        y = TOP_H + view_h
        controls = "Move: WASD/Arrows   Contact with S/H starts a fight   Q: abort"
        ui.safe_addstr(self.stdscr, y, 0, controls[:max_x], curses.color_pair(ui.PAIR_HUD))
        for i, msg in enumerate(self.messages):
            ui.safe_addstr(self.stdscr, y + 1 + i, 0, msg[:max_x], curses.color_pair(ui.PAIR_WARN))

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
        if key in (ord('q'), ord('Q')):
            self.running = False
            self.result = "aborted"

    # ---------------------- main loop ----------------------

    def tick_once(self):
        self.draw()
        key = self.stdscr.getch()
        if key == curses.KEY_RESIZE:
            pass
        elif key != -1:
            self.handle_key(key)
        self.update()
