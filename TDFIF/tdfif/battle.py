"""Menu-driven turn-based battle engine.

Pure game logic - no curses in here. A UI layer drives it by reading
`battle.phase` / `battle.current` and calling the `do_*` methods; each
`do_*` call resolves one unit's turn and auto-advances through any enemy
turns until either the next party member needs input or the battle ends
(`battle.phase == "done"`, `battle.result` in {"won", "lost", "fled"}).

Threat model mirrors TDF exactly: kinetic (vapor) rounds cannot hurt a
suited operative at all - they just feed Suit Charge. Only necro rounds
matter, and only as an accumulating load that drains HP on any turn the
carrier keeps acting; Defend burns the load off fast instead.
"""

import random

from . import constants as C
from .party import Inventory, PartyMember, new_squad

LOG_CAP = 6


class Battle:
    def __init__(self, party, enemies, inventory=None):
        self.party = party
        self.enemies = enemies
        self.inventory = inventory or Inventory()
        self.log_lines = []
        self.round_no = 0
        self.queue = []
        self.current = None
        self.phase = "action"     # action | done
        self.result = None        # None | "won" | "lost" | "fled"
        self._start_round()

    # ---------------------- logging ----------------------

    def log(self, text):
        self.log_lines.append(text)
        self.log_lines = self.log_lines[-LOG_CAP:]

    # ---------------------- stat helpers ----------------------

    @staticmethod
    def eff_atk(u):
        a = u.atk
        if u.has_status("Overdriven"):
            a = int(a * 1.25)
        return a

    @staticmethod
    def eff_dfn(u):
        d = u.dfn
        if u.has_status("Overdriven"):
            d = int(d * 1.25)
        if u.has_status("Bulwark"):
            d = int(d * 1.5)
        return d

    def _damage(self, attacker, target, power_mult):
        dmg = self.eff_atk(attacker) * power_mult - self.eff_dfn(target) / 2
        dmg += random.randint(-2, 2)
        dmg = max(1, int(dmg))
        if getattr(target, "defending", False):
            dmg = max(1, int(dmg * C.DEFEND_DMG_REDUCTION))
        if target.has_status("Marked") or target.has_status("Exposed"):
            dmg = int(dmg * 1.3)
        return dmg

    # ---------------------- turn order ----------------------

    def _alive_units(self):
        return [u for u in self.party + self.enemies if u.alive]

    def _start_round(self):
        self.round_no += 1
        for u in self._alive_units():
            u.tick_statuses()
        self.queue = sorted(self._alive_units(), key=lambda u: u.spd + random.uniform(-1, 1),
                             reverse=True)
        self._advance()

    def _advance(self):
        if self.phase == "done":
            return
        while True:
            if not self.queue:
                if self._check_end():
                    return
                self._start_round()
                return
            nxt = self.queue.pop(0)
            if not nxt.alive:
                continue
            if isinstance(nxt, PartyMember):
                nxt.defending = False
                self.current = nxt
                self.phase = "action"
                return
            self._enemy_act(nxt)
            if self._check_end():
                return

    def _check_end(self):
        if all(not e.alive for e in self.enemies):
            self.phase = "done"
            self.result = "won"
            return True
        if all(not p.alive for p in self.party):
            self.phase = "done"
            self.result = "lost"
            return True
        return False

    # ---------------------- enemy AI ----------------------

    def _enemy_act(self, enemy):
        alive_party = [p for p in self.party if p.alive]
        if not alive_party:
            return
        if enemy.has_status("Suppressed") and random.random() < 0.4:
            self.log(f"{enemy.name}'s shot goes wide - suppressed.")
            return

        taunting = [p for p in alive_party if p.has_status("Bulwark")]
        if taunting:
            target = random.choice(taunting)
        else:
            front = [p for p in alive_party if p.row == "front"]
            back = [p for p in alive_party if p.row == "back"]
            pool = (front * 7 + back * 3) if (front or back) else alive_party
            target = random.choice(pool)

        if enemy.weapon == C.WEAPON_VAPOR:
            gained = min(target.max_sc - target.sc, C.SC_FEEDSTOCK_PER_VAPOR_HIT)
            target.sc = min(target.max_sc, target.sc + C.SC_FEEDSTOCK_PER_VAPOR_HIT)
            self.log(f"{enemy.name} fires on {target.name} - harmless, +{gained} charge.")
        else:
            target.necro_load = min(C.NECRO_LOAD_CAP, target.necro_load + C.NECRO_LOAD_PER_HIT)
            msg = f"{enemy.name} lands a bio round on {target.name} - necrotic load rising."
            if enemy.on_hit_status and not enemy.has_status("EMP-Locked"):
                target.apply_status(enemy.on_hit_status, enemy.on_hit_turns)
                msg += f" ({target.name} is {enemy.on_hit_status})"
            self.log(msg)

    # ---------------------- ability resolution ----------------------

    def _targets_for(self, ability, unit, chosen):
        if ability.target == "single_enemy":
            return [chosen] if chosen and chosen.alive else []
        if ability.target == "all_enemies":
            return [e for e in self.enemies if e.alive]
        if ability.target == "single_ally":
            return [chosen] if chosen and chosen.alive else []
        if ability.target == "all_allies":
            return [p for p in self.party if p.alive]
        if ability.target == "self":
            return [unit]
        return []

    def _resolve_ability(self, unit, ability, chosen):
        targets = self._targets_for(ability, unit, chosen)
        if not targets:
            return False
        for t in targets:
            if ability.kind == "attack":
                dmg = self._damage(unit, t, ability.power)
                t.hp = max(0, t.hp - dmg)
                self.log(f"{unit.name} uses {ability.name} on {t.name} - {dmg} dmg.")
                if t.hp <= 0:
                    t.alive = False
                    self.log(f"{t.name} is down.")
                if ability.status:
                    t.apply_status(ability.status, ability.status_turns)
            elif ability.kind == "heal":
                healed = min(t.max_hp - t.hp, ability.power)
                t.hp = min(t.max_hp, t.hp + ability.power)
                self.log(f"{unit.name} uses {ability.name} on {t.name} - +{healed} hp.")
            elif ability.kind == "purge":
                t.necro_load = 0
                self.log(f"{unit.name} uses {ability.name} - {t.name}'s necrotic load is clear.")
            elif ability.kind in ("buff", "debuff", "shield"):
                if ability.status:
                    t.apply_status(ability.status, ability.status_turns)
                self.log(f"{unit.name} uses {ability.name} on {t.name}.")
        return True

    # ---------------------- party turn upkeep ----------------------

    def _end_party_turn(self, unit):
        if unit.defending:
            unit.necro_load = max(0, unit.necro_load - C.NECRO_DEFEND_DECAY)
            unit.sc = min(unit.max_sc, unit.sc + C.SC_REGEN_DEFENDING)
        else:
            if unit.necro_load > 0:
                drain = unit.necro_load // C.NECRO_DRAIN_DIVISOR
                if unit.necro_load >= C.NECRO_LOAD_CAP:
                    drain += C.NECRO_CRITICAL_DRAIN
                unit.hp = max(0, unit.hp - drain)
                self.log(f"{unit.name} pushes through the infection - {drain} dmg.")
                if unit.hp <= 0:
                    unit.alive = False
                    self.log(f"{unit.name} goes down.")
            unit.sc = min(unit.max_sc, unit.sc + C.SC_REGEN_PER_TURN)
        self._check_end()

    # ---------------------- player-facing actions ----------------------
    # each returns True/False (whether the action was legal); on success it
    # resolves the turn and advances the battle automatically.

    def do_attack(self, target):
        unit = self.current
        if self.phase != "action" or not target or not target.alive:
            return False
        dmg = self._damage(unit, target, 1.0)
        target.hp = max(0, target.hp - dmg)
        self.log(f"{unit.name} fires - {dmg} dmg to {target.name}.")
        if target.hp <= 0:
            target.alive = False
            self.log(f"{target.name} is down.")
        self._end_party_turn(unit)
        self._advance()
        return True

    def do_ability(self, ability, target=None):
        unit = self.current
        if self.phase != "action" or unit.sc < ability.sc_cost:
            return False
        ok = self._resolve_ability(unit, ability, target)
        if not ok:
            return False
        unit.sc -= ability.sc_cost
        self._end_party_turn(unit)
        self._advance()
        return True

    def do_defend(self):
        unit = self.current
        if self.phase != "action":
            return False
        unit.defending = True
        self.log(f"{unit.name} holds position - the swarm gets to work.")
        self._end_party_turn(unit)
        self._advance()
        return True

    def do_item(self, item_name, target):
        unit = self.current
        if self.phase != "action" or not self.inventory.has(item_name) or not target or not target.alive:
            return False
        if item_name == "Stim":
            healed = min(target.max_hp - target.hp, 50)
            target.hp = min(target.max_hp, target.hp + 50)
            self.log(f"{unit.name} uses a Stim on {target.name} - +{healed} hp.")
        elif item_name == "Purge Canister":
            target.necro_load = 0
            self.log(f"{unit.name} uses a Purge Canister on {target.name} - load cleared.")
        elif item_name == "Suit Battery":
            target.sc = min(target.max_sc, target.sc + 20)
            self.log(f"{unit.name} uses a Suit Battery on {target.name} - +20 charge.")
        else:
            return False
        self.inventory.use(item_name)
        self._end_party_turn(unit)
        self._advance()
        return True

    def do_formation_swap(self):
        unit = self.current
        if self.phase != "action":
            return False
        unit.row = "back" if unit.row == "front" else "front"
        self.log(f"{unit.name} shifts to {unit.row} line.")
        self._end_party_turn(unit)
        self._advance()
        return True

    def do_flee(self):
        unit = self.current
        if self.phase != "action":
            return False
        party_spd = sum(p.spd for p in self.party if p.alive) / max(1, len([p for p in self.party if p.alive]))
        enemy_spd = sum(e.spd for e in self.enemies if e.alive) / max(1, len([e for e in self.enemies if e.alive]))
        chance = max(0.1, min(0.9, 0.3 + (party_spd - enemy_spd) * 0.05))
        if random.random() < chance:
            self.log("Squad breaks contact.")
            self.phase = "done"
            self.result = "fled"
            return True
        self.log(f"{unit.name} can't shake them.")
        self._end_party_turn(unit)
        self._advance()
        return True
