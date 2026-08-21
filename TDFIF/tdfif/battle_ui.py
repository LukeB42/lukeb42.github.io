"""Curses front end for battle.py's turn engine: menu navigation and
rendering only - every actual rule lives in Battle's do_* methods."""

import curses

from . import ui
from .constants import NECRO_LOAD_CAP

TOP_MENU = ["Attack", "Ability", "Item", "Defend", "Formation", "Flee"]


class BattleUI:
    def __init__(self, battle):
        self.battle = battle
        self.menu_state = "top"     # top | ability | item | target_enemy | target_ally
        self.cursor = 0
        self.action = None          # "attack" | "ability" | "item", pending a target
        self.pending_ability = None
        self.pending_item = None

    def _reset_to_top(self):
        self.menu_state = "top"
        self.cursor = 0
        self.action = None
        self.pending_ability = None
        self.pending_item = None

    # ---------------------- input ----------------------

    def handle_key(self, key):
        b = self.battle
        if b.phase != "action":
            return

        up = key in (curses.KEY_UP, ord('w'), ord('W'))
        down = key in (curses.KEY_DOWN, ord('s'), ord('S'))
        confirm = key in (10, 13, curses.KEY_ENTER, ord(' '))
        back = key in (ord('q'), ord('Q'), 27, curses.KEY_BACKSPACE, 127, 8)

        if self.menu_state == "top":
            if up:
                self.cursor = (self.cursor - 1) % len(TOP_MENU)
            elif down:
                self.cursor = (self.cursor + 1) % len(TOP_MENU)
            elif confirm:
                self._confirm_top()
            return

        if self.menu_state == "ability":
            n = len(b.current.abilities)
            if n == 0:
                if back:
                    self._reset_to_top()
                return
            if up:
                self.cursor = (self.cursor - 1) % n
            elif down:
                self.cursor = (self.cursor + 1) % n
            elif confirm:
                self._confirm_ability()
            elif back:
                self._reset_to_top()
            return

        if self.menu_state == "item":
            items = self._available_items()
            if not items:
                if back:
                    self._reset_to_top()
                return
            if up:
                self.cursor = (self.cursor - 1) % len(items)
            elif down:
                self.cursor = (self.cursor + 1) % len(items)
            elif confirm:
                self.pending_item = items[self.cursor]
                self.menu_state = "target_ally"
                self.cursor = 0
            elif back:
                self._reset_to_top()
            return

        if self.menu_state == "target_enemy":
            targets = [e for e in b.enemies if e.alive]
            if not targets:
                self._reset_to_top()
                return
            if up:
                self.cursor = (self.cursor - 1) % len(targets)
            elif down:
                self.cursor = (self.cursor + 1) % len(targets)
            elif confirm:
                target = targets[self.cursor]
                if self.action == "attack":
                    b.do_attack(target)
                elif self.action == "ability":
                    b.do_ability(self.pending_ability, target)
                self._reset_to_top()
            elif back:
                self._reset_to_top()
            return

        if self.menu_state == "target_ally":
            targets = [p for p in b.party if p.alive]
            if not targets:
                self._reset_to_top()
                return
            if up:
                self.cursor = (self.cursor - 1) % len(targets)
            elif down:
                self.cursor = (self.cursor + 1) % len(targets)
            elif confirm:
                target = targets[self.cursor]
                if self.action == "ability":
                    b.do_ability(self.pending_ability, target)
                elif self.action == "item":
                    b.do_item(self.pending_item, target)
                self._reset_to_top()
            elif back:
                self._reset_to_top()
            return

    def _available_items(self):
        return [name for name, count in self.battle.inventory.items.items() if count > 0]

    def _confirm_top(self):
        b = self.battle
        choice = TOP_MENU[self.cursor]
        if choice == "Attack":
            self.action = "attack"
            self.menu_state = "target_enemy"
            self.cursor = 0
        elif choice == "Ability":
            self.menu_state = "ability"
            self.cursor = 0
        elif choice == "Item":
            self.menu_state = "item"
            self.cursor = 0
        elif choice == "Defend":
            b.do_defend()
            self._reset_to_top()
        elif choice == "Formation":
            b.do_formation_swap()
            self._reset_to_top()
        elif choice == "Flee":
            b.do_flee()
            self._reset_to_top()

    def _confirm_ability(self):
        b = self.battle
        ability = b.current.abilities[self.cursor]
        if b.current.sc < ability.sc_cost or b.current.has_status("EMP-Locked"):
            return
        if ability.target in ("single_enemy", "single_ally"):
            self.pending_ability = ability
            self.action = "ability"
            self.menu_state = "target_enemy" if ability.target == "single_enemy" else "target_ally"
            self.cursor = 0
        else:
            b.do_ability(ability)
            self._reset_to_top()

    # ---------------------- rendering ----------------------

    def draw(self, stdscr):
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()
        b = self.battle

        ui.safe_addstr(stdscr, 0, 0, f"ROUND {b.round_no}", curses.color_pair(ui.PAIR_HUD) | curses.A_BOLD)

        row = 2
        ui.safe_addstr(stdscr, row, 2, "-- HOSTILES --", curses.color_pair(ui.PAIR_DANGER))
        row += 1
        for e in b.enemies:
            if not e.alive:
                continue
            hb, pair = ui.bar(e.hp / e.max_hp if e.max_hp else 0, 20)
            tag = " [ELITE]" if e.elite else ""
            statuses = ",".join(e.statuses.keys())
            ui.safe_addstr(stdscr, row, 2, f" {e.name}{tag}", curses.color_pair(ui.PAIR_DANGER))
            row += 1
            ui.safe_addstr(stdscr, row, 4, f"[{hb}] {e.hp:3d}/{e.max_hp}" + (f"  ({statuses})" if statuses else ""),
                            curses.color_pair(pair))
            row += 1
        row += 1

        ui.safe_addstr(stdscr, row, 2, "-- FIRETEAM --", curses.color_pair(ui.PAIR_HUD))
        row += 1
        for p in b.party:
            is_current = (p is b.current and b.phase == "action")
            name_attr = curses.color_pair(ui.PAIR_GOOD) | curses.A_BOLD if is_current else curses.color_pair(ui.PAIR_HUD)
            tag = " [DOWN]" if not p.alive else (" [DEF]" if p.defending else "")
            row_label = "front" if p.row == "front" else "back"
            marker = ">" if is_current else " "
            statuses = ",".join(p.statuses.keys())
            ui.safe_addstr(stdscr, row, 2, f"{marker}{p.name} ({row_label}){tag}", name_attr)
            row += 1
            hb, hp_pair = ui.bar(p.hp / p.max_hp if p.max_hp else 0, 18)
            sb, _ = ui.bar(p.sc / p.max_sc if p.max_sc else 0, 18)
            nb, n_pair = ui.bar(p.necro_load / NECRO_LOAD_CAP, 18, invert=True)
            ui.safe_addstr(stdscr, row, 4, f"HP [{hb}] {p.hp:3d}/{p.max_hp}", curses.color_pair(hp_pair))
            row += 1
            ui.safe_addstr(stdscr, row, 4, f"SC [{sb}] {p.sc:3d}/{p.max_sc}", curses.color_pair(ui.PAIR_ACCENT))
            row += 1
            ui.safe_addstr(stdscr, row, 4, f"NL [{nb}] {p.necro_load:3d}" + (f"  ({statuses})" if statuses else ""),
                            curses.color_pair(n_pair))
            row += 2

        self._draw_menu(stdscr, row, max_x)

        log_row = max_y - min(len(b.log_lines), 6) - 1
        for i, line in enumerate(b.log_lines):
            ui.safe_addstr(stdscr, log_row + i, 2, line[:max_x - 4], curses.A_DIM)

        stdscr.refresh()

    def _draw_menu(self, stdscr, row, max_x):
        b = self.battle
        if b.phase != "action":
            return
        col = max_x // 2

        if self.menu_state == "top":
            ui.safe_addstr(stdscr, row, col, f"{b.current.name}'s turn:", curses.color_pair(ui.PAIR_HUD) | curses.A_BOLD)
            for i, choice in enumerate(TOP_MENU):
                attr = curses.A_REVERSE if i == self.cursor else 0
                ui.safe_addstr(stdscr, row + 1 + i, col + 2, choice, attr)

        elif self.menu_state == "ability":
            locked = b.current.has_status("EMP-Locked")
            title = "Choose an ability:" if not locked else "EMP-Locked - abilities disabled:"
            ui.safe_addstr(stdscr, row, col, title, curses.color_pair(ui.PAIR_HUD) | curses.A_BOLD)
            for i, ab in enumerate(b.current.abilities):
                affordable = b.current.sc >= ab.sc_cost and not locked
                text = f"{ab.name} (SC {ab.sc_cost})"
                attr = curses.A_REVERSE if i == self.cursor else 0
                if not affordable:
                    attr |= curses.A_DIM
                ui.safe_addstr(stdscr, row + 1 + i, col + 2, text, attr)
            desc_row = row + 1 + len(b.current.abilities) + 1
            if b.current.abilities:
                ui.safe_addstr(stdscr, desc_row, col + 2, b.current.abilities[self.cursor].desc, curses.A_DIM)

        elif self.menu_state == "item":
            items = self._available_items()
            ui.safe_addstr(stdscr, row, col, "Choose an item:", curses.color_pair(ui.PAIR_HUD) | curses.A_BOLD)
            if not items:
                ui.safe_addstr(stdscr, row + 1, col + 2, "(none left)", curses.A_DIM)
            for i, name in enumerate(items):
                count = b.inventory.items[name]
                attr = curses.A_REVERSE if i == self.cursor else 0
                ui.safe_addstr(stdscr, row + 1 + i, col + 2, f"{name} x{count}", attr)

        elif self.menu_state == "target_enemy":
            targets = [e for e in b.enemies if e.alive]
            ui.safe_addstr(stdscr, row, col, "Choose a target:", curses.color_pair(ui.PAIR_HUD) | curses.A_BOLD)
            for i, t in enumerate(targets):
                attr = curses.A_REVERSE if i == self.cursor else 0
                ui.safe_addstr(stdscr, row + 1 + i, col + 2, f"{t.name} ({t.hp}/{t.max_hp} hp)", attr)

        elif self.menu_state == "target_ally":
            targets = [p for p in b.party if p.alive]
            ui.safe_addstr(stdscr, row, col, "Choose an ally:", curses.color_pair(ui.PAIR_HUD) | curses.A_BOLD)
            for i, t in enumerate(targets):
                attr = curses.A_REVERSE if i == self.cursor else 0
                ui.safe_addstr(stdscr, row + 1 + i, col + 2, f"{t.name} ({t.hp}/{t.max_hp} hp)", attr)

        hint = "Up/Down: choose   Enter: confirm   Q/Backspace: back"
        ui.safe_addstr(stdscr, row - 1, col, hint, curses.A_DIM)
