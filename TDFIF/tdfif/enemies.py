"""Enemy templates per site tier, and the squad rolls the overworld uses
to seed encounter markers."""

import random

from .constants import WEAPON_NECRO, WEAPON_VAPOR
from .party import Unit


class Enemy(Unit):
    def __init__(self, name, weapon, max_hp, atk, dfn, spd, elite=False,
                 on_hit_status=None, on_hit_turns=2):
        super().__init__(name, max_hp, atk, dfn, spd, row="front")
        self.weapon = weapon
        self.elite = elite
        self.on_hit_status = on_hit_status   # status this enemy applies when it lands a necro hit
        self.on_hit_turns = on_hit_turns


# name, weapon, hp, atk, dfn, spd
ENEMY_TEMPLATES = {
    "militia": [
        dict(name="Rustwater Gunman", weapon=WEAPON_VAPOR, hp=45, atk=12, dfn=4, spd=7),
        dict(name="Rustwater Marksman", weapon=WEAPON_NECRO, hp=35, atk=9, dfn=3, spd=8),
        dict(name="Militia Brute", weapon=WEAPON_VAPOR, hp=70, atk=16, dfn=6, spd=5),
    ],
    "dumb": [
        dict(name="DUMB Sentry", weapon=WEAPON_VAPOR, hp=55, atk=14, dfn=8, spd=7),
        dict(name="Bio-Trooper", weapon=WEAPON_NECRO, hp=48, atk=10, dfn=6, spd=8),
        dict(name="Combat Drone", weapon=WEAPON_VAPOR, hp=40, atk=18, dfn=4, spd=10),
    ],
    "blacksite": [
        dict(name="Reaper Trooper", weapon=WEAPON_NECRO, hp=60, atk=12, dfn=8, spd=9),
        dict(name="Blood Guard", weapon=WEAPON_VAPOR, hp=80, atk=20, dfn=10, spd=8),
    ],
}

ELITES = {
    "dumb": dict(name="Containment Officer", weapon=WEAPON_NECRO, hp=90, atk=11, dfn=10, spd=9,
                 on_hit_status="EMP-Locked", on_hit_turns=2),
    "blacksite": dict(name="Black Site Handler", weapon=WEAPON_NECRO, hp=150, atk=14, dfn=12, spd=10,
                       on_hit_status="Suppressed", on_hit_turns=2),
}


def _build(template, elite=False, on_hit_status=None, on_hit_turns=2, suffix=""):
    e = Enemy(template["name"] + suffix, template["weapon"], template["hp"],
              template["atk"], template["dfn"], template["spd"], elite=elite,
              on_hit_status=on_hit_status, on_hit_turns=on_hit_turns)
    return e


def roll_squad(tier, size_range, vapor_bias, include_elite=False):
    """Build one encounter's worth of enemies for the given site tier."""
    pool = ENEMY_TEMPLATES[tier]
    vapor_pool = [t for t in pool if t["weapon"] == WEAPON_VAPOR]
    necro_pool = [t for t in pool if t["weapon"] == WEAPON_NECRO]
    n = random.randint(*size_range)
    squad = []
    for i in range(n):
        pool_choice = vapor_pool if (vapor_pool and random.random() < vapor_bias) or not necro_pool else necro_pool
        tpl = random.choice(pool_choice)
        squad.append(_build(tpl, suffix=f" {i + 1}" if n > 1 else ""))
    if include_elite and tier in ELITES:
        squad.append(_build(ELITES[tier], elite=True,
                             on_hit_status=ELITES[tier]["on_hit_status"],
                             on_hit_turns=ELITES[tier]["on_hit_turns"]))
    return squad


class EncounterMarker:
    """An overworld map entity representing an unfought enemy squad."""

    def __init__(self, x, y, tier, size_range, vapor_bias, boss=False):
        self.x = x
        self.y = y
        self.spawn_x = x
        self.spawn_y = y
        self.tier = tier
        self.size_range = size_range
        self.vapor_bias = vapor_bias
        self.boss = boss
        self.alive = True
        self.alert = False
        self.alert_timer = 0
        self.patrol_target = None
        dominant_necro = vapor_bias < 0.5
        self.weapon = WEAPON_NECRO if dominant_necro else WEAPON_VAPOR
        # vision/patrol tuning scales gently with tier danger
        base = {"militia": 7, "dumb": 8, "blacksite": 9}.get(tier, 7)
        self.vision = base
        self.patrol_radius = 6

    def build_battle_squad(self):
        return roll_squad(self.tier, self.size_range, self.vapor_bias, include_elite=self.boss)
