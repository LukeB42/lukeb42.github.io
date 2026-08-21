"""Party members, their suit-charge abilities, and the shared Unit base
that battle.py's enemies also build on."""

from . import constants as C


class Ability:
    def __init__(self, name, sc_cost, kind, target, power=0, status=None,
                 status_turns=3, desc=""):
        self.name = name
        self.sc_cost = sc_cost
        self.kind = kind            # attack | heal | purge | buff | debuff | shield
        self.target = target        # single_enemy | all_enemies | single_ally | all_allies | self
        self.power = power
        self.status = status        # status name applied by this ability, if any
        self.status_turns = status_turns
        self.desc = desc


class Unit:
    """Shared base for party members and enemies."""

    def __init__(self, name, max_hp, atk, dfn, spd, row="front"):
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.atk = atk
        self.dfn = dfn
        self.spd = spd
        self.row = row              # "front" or "back"
        self.necro_load = 0
        self.statuses = {}          # name -> turns remaining
        self.alive = True
        self.defending = False      # true from a Defend action until this unit's next turn

    @property
    def side(self):
        return "party" if isinstance(self, PartyMember) else "enemy"

    def has_status(self, name):
        return name in self.statuses

    def apply_status(self, name, turns):
        self.statuses[name] = max(self.statuses.get(name, 0), turns)

    def tick_statuses(self):
        expired = []
        for name in list(self.statuses):
            self.statuses[name] -= 1
            if self.statuses[name] <= 0:
                expired.append(name)
                del self.statuses[name]
        return expired


ABILITIES = {
    "Locke Smith": [
        Ability("Overdrive Sync", sc_cost=6, kind="buff", target="all_allies",
                status="Overdriven", status_turns=3,
                desc="Squad-wide ATK/DEF buff for 3 turns."),
        Ability("Rally Fire", sc_cost=4, kind="attack", target="single_enemy",
                power=1.6, status="Marked", status_turns=2,
                desc="Heavy shot; marks the target for extra necro damage."),
    ],
    "Ian Formant": [
        Ability("Bulwark Stance", sc_cost=3, kind="shield", target="self",
                status="Bulwark", status_turns=2,
                desc="Draws enemy fire to Ian and raises his DEF for 2 turns."),
        Ability("Suppression Volley", sc_cost=5, kind="attack", target="all_enemies",
                power=0.5, status="Suppressed", status_turns=2,
                desc="Kinetic burst - low damage, suppresses all enemies' accuracy."),
    ],
    "Rose Gardner": [
        Ability("Nanite Purge", sc_cost=4, kind="purge", target="single_ally",
                desc="Instantly clears an ally's necrotic load."),
        Ability("EMP Burst", sc_cost=6, kind="debuff", target="all_enemies",
                status="EMP-Locked", status_turns=2,
                desc="Locks out enemy special attacks for 2 turns."),
        Ability("Field Patch", sc_cost=3, kind="heal", target="single_ally",
                power=45, desc="Restores HP to one ally."),
    ],
    "Daisy Fields": [
        Ability("Bio-Counter Rounds", sc_cost=5, kind="attack", target="single_enemy",
                power=1.3, status="Exposed", status_turns=2,
                desc="Armour-piercing shot; leaves the target Exposed."),
        Ability("Twin Strike", sc_cost=4, kind="attack", target="single_enemy",
                power=1.0, desc="Two quick shots on one target."),
    ],
}


class PartyMember(Unit):
    def __init__(self, name):
        stats = C.SQUAD_BASE_STATS[name]
        super().__init__(name, stats["max_hp"], stats["atk"], stats["dfn"],
                          stats["spd"], row=stats["row"])
        self.role = stats["role"]
        self.max_sc = stats["max_sc"]
        self.sc = self.max_sc // 2
        self.abilities = ABILITIES[name]


def new_squad():
    return [PartyMember(name) for name in C.SQUAD_NAMES]


class Inventory:
    """Shared party inventory, persists for the length of a mission."""

    def __init__(self):
        self.items = {"Stim": 3, "Purge Canister": 2, "Suit Battery": 2}

    def has(self, name):
        return self.items.get(name, 0) > 0

    def use(self, name):
        if self.has(name):
            self.items[name] -= 1
            return True
        return False
