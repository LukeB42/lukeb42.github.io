"""Phase machine: splash -> mission select -> codec briefing -> overworld
<-> battle -> end -> back to mission select. Mirrors TDF's App class."""

import random

import curses

from . import constants as C
from . import ui
from .battle import Battle
from .battle_ui import BattleUI
from .overworld import Overworld
from .party import Inventory, new_squad

# Mission-select easter egg: up down up down left right left right b a x x
# unlocks every site. Up/down accept WASD too, matching this screen's normal
# navigation keys; left/right/b/a/x are arrow/letter-only, since nothing
# else in this screen binds them.
CHEAT_SEQUENCE = ("up", "down", "up", "down", "left", "right", "left", "right",
                   "b", "a", "x", "x")


def _cheat_step_matches(step, key):
    if step == "up":
        return key in (curses.KEY_UP, ord('w'), ord('W'))
    if step == "down":
        return key in (curses.KEY_DOWN, ord('s'), ord('S'))
    if step == "left":
        return key == curses.KEY_LEFT
    if step == "right":
        return key == curses.KEY_RIGHT
    return key in (ord(step), ord(step.upper()))


class App:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.phase = "splash"
        self.mission_index = 0
        self.max_unlocked = 0        # highest site index the player may deploy to
        self.mission_status_msg = ""
        self.mission_status_ticks = 0
        self.cheat_progress = 0
        self.briefing_theme = None
        self.briefing_index = 0

        self.party = None
        self.inventory = None
        self.overworld = None
        self.battle = None
        self.battle_ui = None
        self.battle_marker = None
        self.end_headline = ""
        self.end_lines = []

        self.done = False
        stdscr.timeout(120)

    # ---------------------- transitions ----------------------

    def _begin_briefing(self):
        self.briefing_theme = random.choice(C.CODEC_THEMES)
        self.briefing_index = 0
        self.phase = "briefing"

    def _attempt_deploy(self, idx):
        self.mission_index = idx
        if idx <= self.max_unlocked:
            self._begin_briefing()
            return
        prev_name = C.LEVELS[idx - 1]["name"]
        self.mission_status_msg = f"LOCKED - complete {prev_name} first."
        self.mission_status_ticks = 30

    def _track_cheat(self, key):
        if _cheat_step_matches(CHEAT_SEQUENCE[self.cheat_progress], key):
            self.cheat_progress += 1
            if self.cheat_progress >= len(CHEAT_SEQUENCE):
                self.cheat_progress = 0
                self.max_unlocked = len(C.LEVELS) - 1
                self.mission_status_msg = "CHEAT ACCEPTED - every site unlocked."
                self.mission_status_ticks = 60
        else:
            self.cheat_progress = 1 if _cheat_step_matches(CHEAT_SEQUENCE[0], key) else 0

    def _start_mission(self):
        self.party = new_squad()
        self.inventory = Inventory()
        self.overworld = Overworld(self.stdscr, C.LEVELS[self.mission_index], self.party, self.inventory)
        self.phase = "overworld"

    def _start_battle(self, marker):
        self.battle_marker = marker
        enemies = marker.build_battle_squad()
        self.battle = Battle(self.party, enemies, inventory=self.inventory)
        self.battle_ui = BattleUI(self.battle)
        self.overworld.pending_encounter = None
        self.phase = "battle"

    def _resolve_battle(self):
        result = self.battle.result
        marker = self.battle_marker
        if result == "won":
            marker.alive = False
            tier_name = C.TIER_DISPLAY_NAMES.get(marker.tier, marker.tier.title())
            self.overworld.log(f"{tier_name} hostile squad down.")
        elif result == "fled":
            self.overworld.relocate_marker_away(marker)
            self.overworld.log("Fireteam breaks contact.")

        self.battle = None
        self.battle_ui = None
        self.battle_marker = None

        if result == "lost":
            self._end_mission("lost")
            return

        self.phase = "overworld"
        if self.overworld.markers and all(not m.alive for m in self.overworld.markers):
            self.overworld.result = "extracted"
            self.overworld.running = False

    def _end_mission(self, reason):
        if reason == "extracted" and self.mission_index == len(C.LEVELS) - 1:
            self.end_headline = "TOUR DE FORCE COMPLETE"
            self.end_lines = [
                f"{C.LEVELS[self.mission_index]['name']} is down. Every site on the list, cleared.",
                "Congratulations - four new bodies are already printing, flesh and blood",
                "this time, not swarm. The suits power down for good and go back in the crate.",
                f"{', '.join(C.SQUAD_NAMES[:-1])}, and {C.SQUAD_NAMES[-1]}: welcome back.",
                "Go live a life nobody at DISA will ever admit you were away from.",
                f"Map explored: {self.overworld.map_percent() if self.overworld else 0}%",
            ]
        elif reason == "extracted":
            self.end_headline = "MISSION COMPLETE"
            self.end_lines = ["Fireteam extracted clean.",
                               f"Map explored: {self.overworld.map_percent() if self.overworld else 0}%"]
            if self.mission_index >= self.max_unlocked and self.mission_index + 1 < len(C.LEVELS):
                self.max_unlocked = self.mission_index + 1
                self.end_lines.append(f"Site unlocked: {C.LEVELS[self.max_unlocked]['name']}.")
        elif reason == "aborted":
            self.end_headline = "MISSION ABORTED"
            self.end_lines = ["Fireteam pulled out early."]
        else:
            self.end_headline = "FIRETEAM DOWN"
            self.end_lines = ["Necrotic overload across the squad. Nobody left standing to extract."]
        self.overworld = None
        self.battle = None
        self.battle_ui = None
        self.battle_marker = None
        self.phase = "end"

    # ---------------------- per-frame step ----------------------

    def step(self):
        if self.phase == "splash":
            ui.draw_splash(self.stdscr)
            if self.stdscr.getch() != -1:
                self.phase = "mission"

        elif self.phase == "mission":
            status = self.mission_status_msg if self.mission_status_ticks > 0 else None
            ui.draw_mission_select(self.stdscr, self.mission_index, self.max_unlocked, status)
            if self.mission_status_ticks > 0:
                self.mission_status_ticks -= 1
            key = self.stdscr.getch()
            if key != -1:
                self._track_cheat(key)
            if key in (curses.KEY_UP, ord('w'), ord('W')):
                self.mission_index = (self.mission_index - 1) % len(C.LEVELS)
            elif key in (curses.KEY_DOWN, ord('s'), ord('S')):
                self.mission_index = (self.mission_index + 1) % len(C.LEVELS)
            elif key in (10, 13, curses.KEY_ENTER):
                self._attempt_deploy(self.mission_index)
            elif key in (ord('q'), ord('Q')):
                self.phase = "closed"
                self.done = True
            elif key != -1 and ord('1') <= key <= ord(str(len(C.LEVELS))):
                self._attempt_deploy(key - ord('1'))

        elif self.phase == "briefing":
            ui.draw_codec(self.stdscr, self.briefing_theme, self.briefing_index)
            key = self.stdscr.getch()
            if key != -1:
                self.briefing_index += 1
                if self.briefing_index >= len(self.briefing_theme["lines"]):
                    self._start_mission()

        elif self.phase == "overworld":
            self.overworld.tick_once()
            if self.overworld.pending_encounter is not None:
                self._start_battle(self.overworld.pending_encounter)
            elif not self.overworld.running:
                self._end_mission(self.overworld.result)

        elif self.phase == "battle":
            key = self.stdscr.getch()
            if key != -1 and key != curses.KEY_RESIZE:
                self.battle_ui.handle_key(key)
            self.battle_ui.draw(self.stdscr)
            if self.battle.phase == "done":
                self._resolve_battle()

        elif self.phase == "end":
            self._draw_end()
            if self.stdscr.getch() != -1:
                self.phase = "mission"

        elif self.phase == "closed":
            ui.draw_closed(self.stdscr)

    def _draw_end(self):
        self.stdscr.erase()
        lines = [self.end_headline, ""] + self.end_lines + ["", "Press any key to continue..."]
        for i, line in enumerate(lines):
            ui.safe_addstr(self.stdscr, i, 0, line, curses.color_pair(ui.PAIR_HUD) | curses.A_BOLD)
        self.stdscr.refresh()

    def run_blocking(self):
        while not self.done:
            self.step()


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    ui.init_colors()
    App(stdscr).run_blocking()


def run():
    """Zero-arg entry point for the `tdfif` console script / `python -m tdfif`."""
    curses.wrapper(main)
