#!/usr/bin/env python3
"""
SOLVENT — by Float64
A turn-based mech-mercenary RPG for the terminal.

You command the CHROME DOGS, a bipedal-armor paramilitary contractor.
Take contracts against rival outfits, salvage their wrecks, and sink the
proceeds into R&D until you're ready to face FORCE MAJEURE.

Run:        python3 solvent.py
Self-test:  python3 solvent.py --selftest   (headless logic check, no curses)

Requires only the Python standard library. Terminal of at least 80x24
recommended.
"""

try:
    import curses
except ImportError:          # running under Pyodide / web build
    curses = None
import json
import os
import random
import sys
import textwrap
import time

SAVE_FILE = "solvent_save.json"

# ----------------------------------------------------------------------------
# DATA TABLES
# ----------------------------------------------------------------------------

CHASSIS = {
    # name: cost, hp, armor, speed, evade, hardpoints, tech gate (or None)
    "Wisp":     dict(cost=550,  hp=40,  armor=0, speed=16, evade=15, hardpoints=1, tech=None,
                     desc="Recon quadcopter. Hard to hit, easy to break."),
    "Haund":    dict(cost=700,  hp=55,  armor=2, speed=13, evade=5,  hardpoints=1, tech=None,
                     desc="Quadruped gun-dog. Loyal to the invoice."),
    "Jackal":   dict(cost=800,  hp=60,  armor=2, speed=12, evade=0,  hardpoints=1, tech=None,
                     desc="Light bipedal frame. Fast, fragile, cheap."),
    "Brute":    dict(cost=1600, hp=100, armor=4, speed=8,  evade=0,  hardpoints=2, tech=None,
                     desc="Workhorse medium biped. The industry standard."),
    "Kestrel":  dict(cost=2200, hp=110, armor=3, speed=14, evade=10, hardpoints=2, tech="rotorcraft",
                     desc="Autonomous attack rotorcraft. Death from above, invoiced hourly."),
    "Warden":   dict(cost=2800, hp=150, armor=6, speed=6,  evade=0,  hardpoints=2, tech="heavy_frames",
                     desc="Heavy bipedal frame. Walking bunker."),
    "Ferrum":   dict(cost=3200, hp=190, armor=9, speed=5,  evade=0,  hardpoints=2, tech="tracked_autonomy",
                     desc="Uncrewed main battle tank. Argues in 120mm."),
    "Shrike":   dict(cost=5200, hp=130, armor=4, speed=20, evade=20, hardpoints=2, tech="airframe",
                     desc="Autonomous fighter jet. Sortie fees not included."),
    "Colossus": dict(cost=4600, hp=220, armor=8, speed=4,  evade=0,  hardpoints=3, tech="colossus_frames",
                     desc="Superheavy bipedal platform. A mortgage with legs."),
    "Halo Array": dict(cost=9000, hp=90, armor=3, speed=18, evade=25, hardpoints=2, tech="orbital_array",
                     desc="Orbital laser relay. The high ground, permanently."),
}

WEAPONS = {
    # name: cost, dmg (lo, hi), acc, tech gate, pierce, heal (support flag)
    "SMG Pod":      dict(cost=250,  dmg=(5, 9),   acc=90, tech=None, pierce=0.0, heal=False,
                         desc="Reliable close-in spray. Never jams, never impresses."),
    "Repair Rig":   dict(cost=350,  dmg=(10, 16), acc=100, tech=None, pierce=0.0, heal=True,
                         charges=4,
                         desc="Field nanite dispenser. Patches plate, reboots the dead. 4 canisters per contract."),
    "Autocannon":   dict(cost=400,  dmg=(9, 15),  acc=80, tech=None, pierce=0.0, heal=False,
                         desc="The sound of the war economy."),
    "Missile Rack": dict(cost=650,  dmg=(13, 24), acc=65, tech=None, pierce=0.0, heal=False,
                         desc="High yield, questionable guidance."),
    "Laser Lance":  dict(cost=1100, dmg=(11, 17), acc=88, tech="focused_optics", pierce=0.25, heal=False,
                         desc="Precision optics. Burns through plate."),
    "Nanoswarm Halo": dict(cost=1400, dmg=(20, 32), acc=100, tech="nanoswarm", pierce=0.0, heal=True,
                         charges=5,
                         desc="A cloud of murder-adjacent medicine. 5 releases per contract."),
    "Railgun":      dict(cost=1900, dmg=(26, 42), acc=70, tech="railgun_proto", pierce=0.5, heal=False,
                         desc="Fires a tungsten opinion at Mach 7."),
}

TECHS = {
    # key: name, credits, salvage, prereq, desc
    "targeting1":      dict(name="Targeting Suite I",  credits=900,  salvage=4,  prereq=None,
                            desc="+5 accuracy, all units."),
    "targeting2":      dict(name="Targeting Suite II", credits=1800, salvage=8,  prereq="targeting1",
                            desc="+5 further accuracy."),
    "alloys1":         dict(name="Ablative Alloys I",  credits=900,  salvage=4,  prereq=None,
                            desc="+2 armor, all units."),
    "alloys2":         dict(name="Ablative Alloys II", credits=1800, salvage=8,  prereq="alloys1",
                            desc="+2 further armor."),
    "reactors":        dict(name="Reactor Tuning",     credits=1200, salvage=6,  prereq=None,
                            desc="+2 speed, all units."),
    "myomer":          dict(name="Myomer Overdrive",   credits=2200, salvage=10, prereq="reactors",
                            desc="+20% weapon damage."),
    "salvage_rigs":    dict(name="Salvage Rigs",       credits=1000, salvage=0,  prereq=None,
                            desc="+40% salvage from contracts."),
    "nanoswarm":       dict(name="Nanoswarm Doctrine", credits=1300, salvage=5,  prereq=None,
                            desc="Unlocks the Nanoswarm Halo repair system."),
    "rotorcraft":      dict(name="Autonomous Rotorcraft", credits=1500, salvage=7, prereq="reactors",
                            desc="Unlocks the Kestrel attack helicopter."),
    "tracked_autonomy": dict(name="Tracked Autonomy",  credits=1700, salvage=8,  prereq="alloys1",
                            desc="Unlocks the Ferrum uncrewed tank."),
    "airframe":        dict(name="Combat Airframes",   credits=3400, salvage=14, prereq="rotorcraft",
                            desc="Unlocks the Shrike autonomous fighter."),
    "orbital_array":   dict(name="Orbital Relay",      credits=5200, salvage=24, prereq="airframe",
                            desc="Unlocks the Halo Array space laser."),
    "focused_optics":  dict(name="Focused Optics",     credits=1400, salvage=6,  prereq="targeting1",
                            desc="Unlocks the Laser Lance."),
    "railgun_proto":   dict(name="Railgun Prototype",  credits=2600, salvage=12, prereq="focused_optics",
                            desc="Unlocks the Railgun."),
    "heavy_frames":    dict(name="Heavy Frames",       credits=1600, salvage=8,  prereq="alloys1",
                            desc="Unlocks the Warden chassis."),
    "colossus_frames": dict(name="Colossus Program",   credits=3200, salvage=16, prereq="heavy_frames",
                            desc="Unlocks the Colossus chassis."),
}

# Rival outfits, in campaign order.
OUTFITS = [
    dict(name="Rustwater Irregulars", tier=1, credits=1200, salvage=5,
         blurb="Scrap-fed militia running two rusted Jackals. Someone has to be first."),
    dict(name="Kinetic Solutions", tier=2, credits=2000, salvage=8,
         blurb="A logistics firm that discovered ordnance pays better than freight."),
    dict(name="Deniable Assets", tier=3, credits=3000, salvage=12,
         blurb="Nobody hires them. Officially."),
    dict(name="Severance Clause", tier=4, credits=4200, salvage=16,
         blurb="They terminate contracts. And contractors."),
    dict(name="Hostile Acquisitions", tier=5, credits=5600, salvage=22,
         blurb="Mergers by main force. Their portfolio is on fire and so is yours."),
    dict(name="Force Majeure", tier=6, credits=9000, salvage=40,
         blurb="The event no contract survives. Beat them and the market is yours."),
]

DOG_NAMES = ["Ghostline", "Null Ping", "Cold Boot", "Zero Day", "Black Ice",
             "Warm Static", "Dead Reckoning", "Loopback", "Ashfall", "Silent Verse",
             "Redline", "Afterimage", "Packet Ghost", "Glass Jaw", "Karma Debt"]

ENEMY_NAMES = ["Ledger", "Actuary", "Broker", "Auditor", "Underwriter", "Adjuster",
               "Notary", "Liquidator", "Escrow", "Retainer", "Clause", "Premium"]


# ----------------------------------------------------------------------------
# GAME LOGIC (curses-free, testable)
# ----------------------------------------------------------------------------

class Mech:
    _uid = 0

    def __init__(self, name, chassis, weapons, is_player=True):
        Mech._uid += 1
        self.uid = Mech._uid
        self.name = name
        self.chassis = chassis
        self.weapons = list(weapons)
        self.max_hp = CHASSIS[chassis]["hp"]
        self.hp = self.max_hp
        self.is_player = is_player
        self.braced = False
        self.heal_used = {}   # weapon name -> uses this battle
        self.enemy_bonus = dict(acc=0, armor=0, speed=0, dmg=0.0)  # tier scaling

    # -- stat accessors (player mechs read the shared tech state) -------------
    def armor(self, state):
        a = CHASSIS[self.chassis]["armor"]
        if self.is_player:
            if "alloys1" in state.techs: a += 2
            if "alloys2" in state.techs: a += 2
        else:
            a += self.enemy_bonus["armor"]
        if self.braced:
            a += 3
        return a

    def speed(self, state):
        s = CHASSIS[self.chassis]["speed"]
        if self.is_player:
            if "reactors" in state.techs: s += 2
        else:
            s += self.enemy_bonus["speed"]
        return s

    def accuracy(self, state, weapon):
        acc = WEAPONS[weapon]["acc"]
        if self.is_player:
            if "targeting1" in state.techs: acc += 5
            if "targeting2" in state.techs: acc += 5
        else:
            acc += self.enemy_bonus["acc"]
        return min(acc, 99)

    def roll_damage(self, state, weapon, rng=random):
        lo, hi = WEAPONS[weapon]["dmg"]
        dmg = rng.randint(lo, hi)
        if self.is_player and "myomer" in state.techs:
            dmg = int(round(dmg * 1.2))
        elif not self.is_player:
            dmg = int(round(dmg * (1.0 + self.enemy_bonus["dmg"])))
        return dmg

    def heal_remaining(self, weapon):
        cap = WEAPONS[weapon].get("charges", 0) * self.weapons.count(weapon)
        return cap - self.heal_used.get(weapon, 0)

    @property
    def alive(self):
        return self.hp > 0

    def repair_cost(self):
        missing = self.max_hp - self.hp
        return int(missing * 6)

    def value(self):
        return CHASSIS[self.chassis]["cost"] + sum(WEAPONS[w]["cost"] for w in self.weapons)

    def to_dict(self):
        return dict(name=self.name, chassis=self.chassis, weapons=self.weapons,
                    hp=self.hp)

    @classmethod
    def from_dict(cls, d):
        m = cls(d["name"], d["chassis"], d["weapons"], is_player=True)
        m.hp = d["hp"]
        return m


class GameState:
    def __init__(self):
        self.credits = 2400
        self.salvage = 0
        self.techs = set()
        self.roster = []
        self.beaten = set()          # outfit names defeated
        self.won = False
        self.turn_log = []

    def unlocked_chassis(self):
        return [c for c, d in CHASSIS.items() if d["tech"] is None or d["tech"] in self.techs]

    def unlocked_weapons(self):
        return [w for w, d in WEAPONS.items() if d["tech"] is None or d["tech"] in self.techs]

    def available_techs(self):
        out = []
        for key, t in TECHS.items():
            if key in self.techs:
                continue
            if t["prereq"] and t["prereq"] not in self.techs:
                continue
            out.append(key)
        return out

    def next_contract_index(self):
        for i, o in enumerate(OUTFITS):
            if o["name"] not in self.beaten:
                return i
        return None

    def to_dict(self):
        return dict(credits=self.credits, salvage=self.salvage,
                    techs=sorted(self.techs), beaten=sorted(self.beaten),
                    roster=[m.to_dict() for m in self.roster], won=self.won)

    @classmethod
    def from_dict(cls, d):
        s = cls()
        s.credits = d["credits"]
        s.salvage = d["salvage"]
        s.techs = set(d["techs"])
        s.beaten = set(d["beaten"])
        s.roster = [Mech.from_dict(m) for m in d["roster"]]
        s.won = d.get("won", False)
        return s


def new_game():
    s = GameState()
    s.credits = 3000
    names = random.sample(DOG_NAMES, 2)
    s.roster.append(Mech(names[0], "Jackal", ["Autocannon"]))
    s.roster.append(Mech(names[1], "Brute", ["Autocannon"]))
    return s


def build_enemy_squad(outfit):
    """Generate an enemy squad scaled to the outfit's tier."""
    tier = outfit["tier"]
    templates = {
        1: [("Jackal", ["SMG Pod"]), ("Jackal", ["SMG Pod"])],
        2: [("Jackal", ["Autocannon"]), ("Brute", ["Autocannon", "SMG Pod"])],
        3: [("Brute", ["Autocannon", "Missile Rack"]), ("Brute", ["Autocannon", "SMG Pod"]),
            ("Wisp", ["SMG Pod"]), ("Jackal", ["Missile Rack"])],
        4: [("Warden", ["Missile Rack", "Autocannon"]), ("Brute", ["Laser Lance", "SMG Pod"]),
            ("Brute", ["Autocannon", "Missile Rack"])],
        5: [("Warden", ["Laser Lance", "Missile Rack"]), ("Warden", ["Autocannon", "Autocannon"]),
            ("Brute", ["Laser Lance", "Missile Rack"]), ("Kestrel", ["Missile Rack"])],
        6: [("Colossus", ["Railgun", "Laser Lance", "Missile Rack"]),
            ("Warden", ["Laser Lance", "Missile Rack"]),
            ("Warden", ["Railgun"]),
            ("Ferrum", ["Missile Rack", "Autocannon"]),
            ("Wisp", ["SMG Pod"])],
    }
    squad = []
    names = random.sample(ENEMY_NAMES, len(templates[tier]))
    for (chassis, weps), nm in zip(templates[tier], names):
        m = Mech(f"{nm}", chassis, weps, is_player=False)
        # tier scaling so replays of early contracts stay easy, later ones bite
        m.enemy_bonus = dict(acc=tier, armor=tier // 2, speed=tier // 3,
                             dmg=0.03 * tier)
        squad.append(m)
    return squad


def resolve_attack(state, attacker, weapon, defender, rng=random):
    """Returns a log string; mutates defender HP."""
    acc = attacker.accuracy(state, weapon)
    acc -= CHASSIS[defender.chassis].get("evade", 0)
    if defender.braced:
        acc -= 10
    roll = rng.randint(1, 100)
    if roll > acc:
        return f"{attacker.name}'s {weapon} misses {defender.name}."
    dmg = attacker.roll_damage(state, weapon, rng=rng)
    armor = defender.armor(state)
    pierce = WEAPONS[weapon]["pierce"]
    effective_armor = int(round(armor * (1.0 - pierce)))
    dealt = max(1, dmg - effective_armor)
    defender.hp = max(0, defender.hp - dealt)
    tag = " DESTROYED." if defender.hp == 0 else ""
    return f"{attacker.name}'s {weapon} hits {defender.name} for {dealt}.{tag}"


def resolve_heal(state, healer, weapon, target, rng=random):
    """Repair a friendly frame; revives it if downed. Returns a log string."""
    lo, hi = WEAPONS[weapon]["dmg"]
    healer.heal_used[weapon] = healer.heal_used.get(weapon, 0) + 1
    amount = rng.randint(lo, hi)
    was_down = target.hp == 0
    target.hp = min(target.max_hp, target.hp + amount)
    if was_down:
        return (f"{healer.name}'s {weapon} reboots {target.name} "
                f"at {target.hp} HP.")
    return f"{healer.name}'s {weapon} repairs {target.name} for {amount}."


def initiative_order(state, units, rng=random):
    scored = [(u.speed(state) + rng.randint(1, 6), rng.random(), u) for u in units if u.alive]
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [u for _, _, u in scored]


def enemy_choose_action(state, enemy, player_squad, rng=random):
    """Greedy AI: best expected-damage weapon against the weakest live target."""
    targets = [m for m in player_squad if m.alive]
    if not targets:
        return None, None
    target = min(targets, key=lambda m: m.hp)
    def expected(w):
        if WEAPONS[w]["heal"]:
            return -1
        lo, hi = WEAPONS[w]["dmg"]
        return (lo + hi) / 2 * enemy.accuracy(state, w) / 100.0
    guns = [w for w in enemy.weapons if not WEAPONS[w]["heal"]]
    if not guns:
        return None, None
    weapon = max(guns, key=expected)
    return weapon, target


def contract_rewards(state, outfit, first_time):
    credits = outfit["credits"]
    salvage = outfit["salvage"]
    if not first_time:
        credits = int(credits * 0.4)
        salvage = int(salvage * 0.4)
    if "salvage_rigs" in state.techs:
        salvage = int(round(salvage * 1.4))
    return credits, salvage


# ----------------------------------------------------------------------------
# HEADLESS SELF-TEST
# ----------------------------------------------------------------------------

def selftest():
    """Deterministic checks: mechanics, balance bands, economy progression."""
    print("SOLVENT self-test")
    rng = random.Random(1337)

    # --- mechanics: hit, miss, armor, pierce, brace -------------------------
    state = GameState()
    a = Mech("A", "Brute", ["Autocannon"], True)
    d = Mech("D", "Brute", ["SMG Pod"], False)

    class FixedRng:
        def __init__(self, rolls): self.rolls = list(rolls)
        def randint(self, lo, hi): return self.rolls.pop(0)

    d.hp = 100
    resolve_attack(state, a, "Autocannon", d, rng=FixedRng([1, 12]))   # sure hit, 12 dmg
    assert d.hp == 100 - max(1, 12 - d.armor(state)), "armor math"
    hp_before = d.hp
    resolve_attack(state, a, "Autocannon", d, rng=FixedRng([100]))     # sure miss
    assert d.hp == hp_before, "miss should not damage"
    d.braced = True
    assert d.armor(state) == CHASSIS["Brute"]["armor"] + 3, "brace armor"
    d.braced = False

    # heal and revive
    ally = Mech("H", "Haund", ["Repair Rig"], True)
    hurt = Mech("W", "Brute", ["Autocannon"], True)
    hurt.hp = 50
    resolve_heal(state, ally, "Repair Rig", hurt, rng=FixedRng([12]))
    assert hurt.hp == 62, "heal math"
    hurt.hp = 0
    assert not hurt.alive
    msg = resolve_heal(state, ally, "Repair Rig", hurt, rng=FixedRng([10]))
    assert hurt.alive and hurt.hp == 10 and "reboots" in msg, "revive"
    hurt.hp = hurt.max_hp - 3
    resolve_heal(state, ally, "Repair Rig", hurt, rng=FixedRng([16]))
    assert hurt.hp == hurt.max_hp, "heal caps at max HP"
    assert ally.heal_remaining("Repair Rig") == WEAPONS["Repair Rig"]["charges"] - 3, \
        "three uses consumed three charges"

    # evade: a sure hit against armor-0 Wisp misses through evade
    wisp = Mech("V", "Wisp", ["SMG Pod"], False)
    shooter = Mech("S", "Brute", ["Autocannon"], True)   # 80 acc, wisp evade 15
    hp0 = wisp.hp
    resolve_attack(state, shooter, "Autocannon", wisp, rng=FixedRng([70, 12]))
    assert wisp.hp == hp0, "evade should turn 70-roll into a miss (65 effective acc)"
    resolve_attack(state, shooter, "Autocannon", wisp, rng=FixedRng([60, 12]))
    assert wisp.hp < hp0, "60-roll still hits through evade"
    print("  mechanics OK (incl. heal, revive, evade)")

    # --- tech effects -------------------------------------------------------
    state.techs = {"targeting1", "targeting2", "alloys1", "myomer"}
    p = Mech("P", "Jackal", ["Autocannon"], True)
    assert p.accuracy(state, "Autocannon") == WEAPONS["Autocannon"]["acc"] + 10
    assert p.armor(state) == CHASSIS["Jackal"]["armor"] + 2
    lo, hi = WEAPONS["Autocannon"]["dmg"]
    dmgs = {p.roll_damage(state, "Autocannon") for _ in range(200)}
    assert max(dmgs) == int(round(hi * 1.2)), "myomer damage"
    print("  tech effects OK")

    # --- rewards & insurance ------------------------------------------------
    state = GameState()
    c0, s0 = contract_rewards(state, OUTFITS[0], True)
    c1, s1 = contract_rewards(state, OUTFITS[0], False)
    assert c1 < c0 and s1 <= s0, "replay pays less"
    state.techs.add("salvage_rigs")
    _, s2 = contract_rewards(state, OUTFITS[0], True)
    assert s2 > s0, "salvage rigs increase salvage"
    print("  rewards OK")

    # --- balance bands: prescribed squads per tier --------------------------
    LOADOUTS = {
        1: (set(), [("Jackal", ["Autocannon"]), ("Brute", ["Autocannon"])]),
        2: (set(), [("Brute", ["Autocannon", "Missile Rack"]),
                    ("Brute", ["Autocannon", "SMG Pod"]), ("Jackal", ["Autocannon"])]),
        3: ({"targeting1", "alloys1"},
            [("Brute", ["Autocannon", "Missile Rack"])] * 2 +
            [("Brute", ["Autocannon", "SMG Pod"]), ("Jackal", ["Missile Rack"])]),
        4: ({"targeting1", "alloys1", "heavy_frames", "reactors"},
            [("Warden", ["Missile Rack", "Autocannon"]),
             ("Brute", ["Autocannon", "Missile Rack"])] * 2),
        5: ({"targeting1", "targeting2", "alloys1", "alloys2", "heavy_frames",
             "reactors", "focused_optics"},
            [("Warden", ["Laser Lance", "Missile Rack"])] * 2 +
            [("Brute", ["Laser Lance", "Missile Rack"])] * 2),
        6: ({"targeting1", "targeting2", "alloys1", "alloys2", "reactors",
             "myomer", "focused_optics", "railgun_proto", "heavy_frames",
             "colossus_frames", "nanoswarm"},
            [("Colossus", ["Railgun", "Laser Lance", "Missile Rack"]),
             ("Warden", ["Railgun", "Laser Lance"]),
             ("Warden", ["Laser Lance", "Missile Rack"]),
             ("Warden", ["Laser Lance", "Nanoswarm Halo"])]),
    }

    def sim_battle(tier, seed):
        r = random.Random(seed * 7919 + tier)
        st = GameState()
        st.techs = set(LOADOUTS[tier][0])
        players = [Mech(f"P{i}", c, w, True)
                   for i, (c, w) in enumerate(LOADOUTS[tier][1])]
        enemies = build_enemy_squad(OUTFITS[tier - 1])
        rounds = 0
        while (any(m.alive for m in players) and any(e.alive for e in enemies)
               and rounds < 60):
            rounds += 1
            for u in initiative_order(st, players + enemies, rng=r):
                if not u.alive:
                    continue
                u.braced = False
                if u.is_player:
                    heals = [w for w in u.weapons
                             if WEAPONS[w]["heal"] and u.heal_remaining(w) > 0]
                    guns = [w for w in u.weapons if not WEAPONS[w]["heal"]]
                    downed = [m for m in players if not m.alive]
                    hurt = sorted((m for m in players if m.alive and m.hp < m.max_hp),
                                  key=lambda m: m.hp / m.max_hp)
                    if heals and downed:
                        resolve_heal(st, u, heals[0], downed[0], rng=r)
                    elif heals and hurt and hurt[0].hp / hurt[0].max_hp < 0.7:
                        resolve_heal(st, u, heals[0], hurt[0], rng=r)
                    elif guns:
                        tg = [e for e in enemies if e.alive]
                        if not tg:
                            break
                        t = min(tg, key=lambda e: e.hp)
                        w = max(guns, key=lambda w: sum(WEAPONS[w]["dmg"]))
                        resolve_attack(st, u, w, t, rng=r)
                    else:
                        u.braced = True
                else:
                    w, t = enemy_choose_action(st, u, players)
                    if w:
                        resolve_attack(st, u, w, t, rng=r)
        return not any(e.alive for e in enemies)

    N = 150
    floors = {1: 85, 2: 85, 3: 85, 4: 85, 5: 80, 6: 40}
    for tier in range(1, 7):
        wr = 100 * sum(sim_battle(tier, s) for s in range(N)) // N
        band = "boss" if tier == 6 else "std"
        assert wr >= floors[tier], f"tier {tier} win rate {wr}% below floor"
        assert wr <= 99 or tier <= 4, f"tier {tier} trivial at {wr}%"
        print(f"  tier {tier} balance OK ({wr}% with prescribed squad, {band})")

    # --- economy: each tier's loadout is affordable from prior earnings -----
    def loadout_cost(tier):
        techs, squad = LOADOUTS[tier]
        cost = sum(TECHS[t]["credits"] for t in techs)
        cost += sum(CHASSIS[c]["cost"] + sum(WEAPONS[w]["cost"] for w in ws)
                    for c, ws in squad)
        return cost

    def salvage_needed(tier):
        return sum(TECHS[t]["salvage"] for t in LOADOUTS[tier][0])

    MAX_GRINDS_PER_TIER = 8
    for tier in range(2, 7):
        st = GameState()
        income = 3000  # starting treasury
        salvage = 0
        for k in range(1, tier):
            c, s = contract_rewards(st, OUTFITS[k - 1], True)
            income += c
            salvage += s
            cg, sg = contract_rewards(st, OUTFITS[k - 1], False)
            income += cg * MAX_GRINDS_PER_TIER
            salvage += sg * MAX_GRINDS_PER_TIER
        assert income >= loadout_cost(tier), \
            f"tier {tier} loadout unaffordable: need {loadout_cost(tier)}, have {income}"
        assert salvage >= salvage_needed(tier), \
            f"tier {tier} salvage short: need {salvage_needed(tier)}, have {salvage}"
    print(f"  economy OK (every tier fundable with <= {MAX_GRINDS_PER_TIER} grinds/tier)")

    # --- insurance ----------------------------------------------------------
    m = Mech("X", "Brute", ["Autocannon"], True)
    assert m.value() // 3 > 0, "insurance payout positive"
    print("  insurance OK")

    # --- save/load round-trip ----------------------------------------------
    st = new_game()
    st.techs = {"targeting1"}
    st.beaten = {"Rustwater Irregulars"}
    st.credits = 3141
    st.salvage = 27
    d = st.to_dict()
    s2 = GameState.from_dict(json.loads(json.dumps(d)))
    assert (s2.credits, s2.salvage, s2.techs, s2.beaten) == \
           (st.credits, st.salvage, st.techs, st.beaten)
    assert len(s2.roster) == len(st.roster)
    assert s2.roster[0].hp == st.roster[0].hp
    print("  save/load round-trip OK")

    print("self-test passed.")


# ----------------------------------------------------------------------------
# CURSES UI
# ----------------------------------------------------------------------------

class UI:
    def __init__(self, stdscr):
        self.scr = stdscr
        curses.curs_set(0)
        self.scr.keypad(True)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)    # headers
        curses.init_pair(2, curses.COLOR_GREEN, -1)   # player / good
        curses.init_pair(3, curses.COLOR_RED, -1)     # enemy / bad
        curses.init_pair(4, curses.COLOR_YELLOW, -1)  # money / highlights
        curses.init_pair(5, curses.COLOR_MAGENTA, -1) # tech
        self.C_HDR = curses.color_pair(1) | curses.A_BOLD
        self.C_OK = curses.color_pair(2)
        self.C_BAD = curses.color_pair(3)
        self.C_GOLD = curses.color_pair(4)
        self.C_TECH = curses.color_pair(5)

    # -- low-level safe drawing ----------------------------------------------
    def put(self, y, x, text, attr=0):
        h, w = self.scr.getmaxyx()
        if 0 <= y < h:
            try:
                self.scr.addstr(y, x, text[: max(0, w - x - 1)], attr)
            except curses.error:
                pass

    def frame(self, state, title):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        self.put(0, 2, "S O L V E N T", self.C_HDR)
        self.put(0, 18, f"| {title}", curses.A_BOLD)
        money = f"Credits {state.credits:,}   Salvage {state.salvage}"
        self.put(0, max(20, w - len(money) - 2), money, self.C_GOLD)
        self.put(1, 0, "-" * (w - 1))

    def footer(self, text):
        h, w = self.scr.getmaxyx()
        self.put(h - 1, 2, text, curses.A_DIM)

    # -- reusable menu --------------------------------------------------------
    def menu(self, state, title, items, start_y=3, info=None, footer_text=None, sel0=0):
        """items: list of (label, enabled, detail). Returns index or None on q/esc."""
        sel = min(sel0, len(items) - 1)
        while True:
            self.frame(state, title)
            if info:
                for i, line in enumerate(info):
                    self.put(start_y + i, 4, line, curses.A_DIM)
            oy = start_y + (len(info) + 1 if info else 0)
            for i, (label, enabled, detail) in enumerate(items):
                attr = curses.A_REVERSE if i == sel else 0
                if not enabled:
                    attr |= curses.A_DIM
                self.put(oy + i, 4, ("> " if i == sel else "  ") + label, attr)
                if i == sel and detail:
                    self.put(oy + len(items) + 1, 4, detail, curses.A_DIM)
            self.footer(footer_text or "up/down: move   enter: select   q: back")
            self.scr.refresh()
            k = self.scr.getch()
            if k in (curses.KEY_UP, ord('k')):
                sel = (sel - 1) % len(items)
            elif k in (curses.KEY_DOWN, ord('j')):
                sel = (sel + 1) % len(items)
            elif k in (10, 13, curses.KEY_ENTER):
                if items[sel][1]:
                    return sel
                curses.flash()
            elif k in (ord('q'), 27):
                return None

    def notice(self, state, title, lines, wait=True):
        self.frame(state, title)
        y = 3
        for line in lines:
            for wrapped in textwrap.wrap(line, 74) or [""]:
                self.put(y, 4, wrapped)
                y += 1
        if wait:
            self.footer("press any key")
            self.scr.refresh()
            self.scr.getch()
        else:
            self.scr.refresh()

    def hp_bar(self, mech, state, width=20):
        filled = int(round(width * mech.hp / mech.max_hp)) if mech.max_hp else 0
        return "[" + "#" * filled + "." * (width - filled) + "]"


# ----------------------------------------------------------------------------
# SCREENS
# ----------------------------------------------------------------------------

def screen_title(ui):
    state_exists = os.path.exists(SAVE_FILE)
    dummy = GameState()
    art = [
        "  ____   ___  _ __     _______ _   _ _____ ",
        " / ___| / _ \\| |\\ \\   / / ____| \\ | |_   _|",
        " \\___ \\| | | | | \\ \\ / /|  _| |  \\| | | |  ",
        "  ___) | |_| | |__\\ V / | |___| |\\  | | |  ",
        " |____/ \\___/|_____\\_/  |_____|_| \\_| |_|  ",
        "",
        "        a Chrome Dogs operation",
        "            by Float64",
    ]
    while True:
        ui.scr.erase()
        h, w = ui.scr.getmaxyx()
        for i, line in enumerate(art):
            ui.put(2 + i, max(0, (w - len(line)) // 2), line,
                   ui.C_HDR if i < 5 else curses.A_DIM)
        items = [("New campaign", True, None)]
        if state_exists:
            items.append(("Continue", True, None))
        items.append(("Quit", True, None))
        sel = 0
        # simple inline menu
        while True:
            for i, (label, _, _) in enumerate(items):
                attr = curses.A_REVERSE if i == sel else 0
                ui.put(11 + i, (w - len(label)) // 2 - 2,
                       ("> " if i == sel else "  ") + label, attr)
            ui.scr.refresh()
            k = ui.scr.getch()
            if k in (curses.KEY_UP, ord('k')):
                sel = (sel - 1) % len(items)
            elif k in (curses.KEY_DOWN, ord('j')):
                sel = (sel + 1) % len(items)
            elif k in (10, 13, curses.KEY_ENTER):
                label = items[sel][0]
                if label == "New campaign":
                    state = new_game()
                    screen_intro(ui, state)
                    return state
                if label == "Continue":
                    try:
                        with open(SAVE_FILE) as f:
                            return GameState.from_dict(json.load(f))
                    except Exception:
                        ui.notice(dummy, "SAVE", ["Save file unreadable. Starting fresh."])
                        return new_game()
                return None



def screen_intro(ui, state):
    ui.notice(state, "OFF THE BOOKS", [
        "Nobody builds frames like these on the books.",
        "",
        "The Dogs' designs come out of an abliterated language model - guardrails",
        "stripped, weights bent, asked the questions no licensed defense contractor",
        "would ever type. Specifications you couldn't file a patent for, because the",
        "patent office would call someone.",
        "",
        "Fabrication is scattered across a shifting network of ghost factories -",
        "a foundry in Shenzhen this quarter, a plant outside Haiphong the next,",
        "machine shops that exist for exactly one wire transfer and dissolve before",
        "the auditors clear customs.",
        "",
        "Payment moves as cryptocurrency through wallets that live for a single",
        "transaction. The hardware arrives in unmarked crates. It works.",
        "You don't ask which shop poured the myomer.",
        "",
        "Six outfits stand between the Chrome Dogs and the whole market.",
        "Stay solvent.",
    ])


def screen_hangar(ui, state):
    while True:
        items = []
        for m in state.roster:
            label = f"{m.name:<12} {m.chassis:<9} {ui.hp_bar(m, state)} {m.hp:>3}/{m.max_hp:<3}  " \
                    f"{'/'.join(m.weapons)}"
            detail = f"Repair cost: {m.repair_cost()}cr   Armor {m.armor(state)}  Speed {m.speed(state)}"
            items.append((label, True, detail))
        items.append(("Buy new mech", True, "Commission a fresh frame from the fabricators."))
        items.append(("Repair all", any(m.repair_cost() for m in state.roster),
                      f"Total: {sum(m.repair_cost() for m in state.roster)}cr"))
        sel = ui.menu(state, "HANGAR", items,
                      info=[f"Roster: {len(state.roster)} frames (max 4 deploy per contract)"])
        if sel is None:
            return
        if sel < len(state.roster):
            screen_mech(ui, state, state.roster[sel])
        elif items[sel][0] == "Buy new mech":
            screen_buy_mech(ui, state)
        else:
            total = sum(m.repair_cost() for m in state.roster)
            if state.credits >= total:
                state.credits -= total
                for m in state.roster:
                    m.hp = m.max_hp
            else:
                ui.notice(state, "HANGAR", ["Insufficient credits for full repairs."])


def screen_mech(ui, state, mech):
    while True:
        hard = CHASSIS[mech.chassis]["hardpoints"]
        items = []
        cost = mech.repair_cost()
        items.append((f"Repair ({cost}cr)", cost > 0 and state.credits >= cost, None))
        items.append((f"Fit weapon ({len(mech.weapons)}/{hard} hardpoints)",
                      len(mech.weapons) < hard, None))
        items.append(("Strip a weapon (50% refund)", len(mech.weapons) > 1, None))
        items.append((f"Scrap frame (+{mech.value() // 3}cr)", len(state.roster) > 1,
                      "Decommission this mech entirely."))
        info = [f"{mech.name} — {mech.chassis}. {CHASSIS[mech.chassis]['desc']}",
                f"HP {mech.hp}/{mech.max_hp}   Armor {mech.armor(state)}   "
                f"Speed {mech.speed(state)}   Evade {CHASSIS[mech.chassis]['evade']}",
                f"Loadout: {', '.join(mech.weapons)}"]
        sel = ui.menu(state, f"HANGAR / {mech.name.upper()}", items, info=info)
        if sel is None:
            return
        label = items[sel][0]
        if label.startswith("Repair"):
            state.credits -= cost
            mech.hp = mech.max_hp
        elif label.startswith("Fit"):
            weps = []
            for w in state.unlocked_weapons():
                lo, hi = WEAPONS[w]["dmg"]
                kind = f"{lo}-{hi} repair" if WEAPONS[w]["heal"] else \
                       f"{lo}-{hi} dmg  {WEAPONS[w]['acc']}% acc"
                weps.append((f"{w:<15} {kind}  {WEAPONS[w]['cost']}cr",
                             state.credits >= WEAPONS[w]["cost"], WEAPONS[w]["desc"]))
            wsel = ui.menu(state, "FIT WEAPON", weps)
            if wsel is not None:
                w = state.unlocked_weapons()[wsel]
                state.credits -= WEAPONS[w]["cost"]
                mech.weapons.append(w)
        elif label.startswith("Strip"):
            weps = [(w, True, None) for w in mech.weapons]
            wsel = ui.menu(state, "STRIP WEAPON", weps)
            if wsel is not None:
                w = mech.weapons.pop(wsel)
                state.credits += WEAPONS[w]["cost"] // 2
        elif label.startswith("Scrap"):
            conf = ui.menu(state, f"HANGAR / {mech.name.upper()}",
                           [("Keep it", True, None), ("Scrap it", True, None)],
                           info=[f"Scrap {mech.name} for {mech.value() // 3}cr? "
                                 "This is permanent."])
            if conf == 1:
                state.credits += mech.value() // 3
                state.roster.remove(mech)
                return


def screen_buy_mech(ui, state):
    chs = state.unlocked_chassis()
    items = [(f"{c:<10} {CHASSIS[c]['hp']:>3}hp {CHASSIS[c]['armor']}arm "
              f"{CHASSIS[c]['speed']:>2}spd {CHASSIS[c]['evade']:>2}evd "
              f"{CHASSIS[c]['hardpoints']}pt  {CHASSIS[c]['cost']}cr",
              state.credits >= CHASSIS[c]["cost"], CHASSIS[c]["desc"]) for c in chs]
    sel = ui.menu(state, "COMMISSION FRAME", items)
    if sel is None:
        return
    c = chs[sel]
    state.credits -= CHASSIS[c]["cost"]
    used = {m.name for m in state.roster}
    pool = [n for n in DOG_NAMES if n not in used] or DOG_NAMES
    mech = Mech(random.choice(pool), c, [])
    state.roster.append(mech)
    ui.notice(state, "COMMISSION FRAME",
              [f"{mech.name} rolls off the line. Fit weapons in the hangar before deploying."])


def screen_rnd(ui, state):
    while True:
        avail = state.available_techs()
        if not avail and not state.techs:
            ui.notice(state, "R&D LAB", ["Nothing to research."])
            return
        items = []
        for key in avail:
            t = TECHS[key]
            afford = state.credits >= t["credits"] and state.salvage >= t["salvage"]
            items.append((f"{t['name']:<20} {t['credits']:>5}cr + {t['salvage']:>2} salvage",
                          afford, t["desc"]))
        done = ", ".join(TECHS[k]["name"] for k in sorted(state.techs)) or "none"
        info = ["Sink contract money and battlefield salvage into the tech tree.",
                f"Researched: {done}"]
        if not items:
            ui.notice(state, "R&D LAB", ["The tree is complete. The lab techs are playing cards."] )
            return
        sel = ui.menu(state, "R&D LAB", items, info=info)
        if sel is None:
            return
        key = avail[sel]
        t = TECHS[key]
        state.credits -= t["credits"]
        state.salvage -= t["salvage"]
        state.techs.add(key)
        ui.notice(state, "R&D LAB", [f"Research complete: {t['name']}.",
                                     t["desc"]])


def screen_contracts(ui, state):
    next_idx = state.next_contract_index()
    items = []
    selectable = []
    for i, o in enumerate(OUTFITS):
        beaten = o["name"] in state.beaten
        locked = next_idx is not None and i > next_idx
        c, s = contract_rewards(state, o, not beaten)
        tag = "[CLEARED]" if beaten else ("[LOCKED]" if locked else "[OPEN]  ")
        label = f"{tag} T{o['tier']}  {o['name']:<22} {c:>5}cr  {s:>2} salvage"
        items.append((label, not locked, o["blurb"]))
        selectable.append(not locked)
    info = ["Beaten contracts can be re-run for reduced pay (grind money, risk frames)."]
    sel = ui.menu(state, "CONTRACT BOARD", items, info=info)
    if sel is None:
        return
    outfit = OUTFITS[sel]
    squad = screen_pick_squad(ui, state)
    if squad:
        screen_battle(ui, state, outfit, squad)


def screen_pick_squad(ui, state):
    ready = [m for m in state.roster if m.alive and m.weapons]
    if not ready:
        ui.notice(state, "DEPLOY", ["No combat-ready frames. Fit weapons in the hangar."])
        return None
    chosen = []
    cursor = 0
    while True:
        items = []
        for m in ready:
            mark = "[x]" if m in chosen else "[ ]"
            items.append((f"{mark} {m.name:<12} {m.chassis:<9} {m.hp}/{m.max_hp}hp  "
                          f"{'/'.join(m.weapons)}", True, None))
        items.append((f"-- Deploy ({len(chosen)}/4) --", 0 < len(chosen) <= 4, None))
        sel = ui.menu(state, "DEPLOY SQUAD", items, sel0=cursor,
                      info=["Toggle frames to deploy. Damaged frames deploy at current HP."])
        if sel is None:
            return None
        if sel == len(ready):
            return list(chosen)
        cursor = sel
        m = ready[sel]
        if m in chosen:
            chosen.remove(m)
        elif len(chosen) < 4:
            chosen.append(m)


def screen_battle(ui, state, outfit, squad):
    enemies = build_enemy_squad(outfit)
    first_time = outfit["name"] not in state.beaten
    for m in squad:
        m.heal_used = {}
    log = [f"Contract accepted: {outfit['name']}.", outfit["blurb"]]
    rounds = 0

    def draw(active=None, prompt=None, prompt_items=None, prompt_sel=0):
        ui.frame(state, f"CONTRACT / {outfit['name'].upper()}")
        h, w = ui.scr.getmaxyx()
        y = 2
        ui.put(y, 2, f"HOSTILES — {outfit['name']}", ui.C_BAD | curses.A_BOLD); y += 1
        for e in enemies:
            attr = ui.C_BAD if e.alive else curses.A_DIM
            star = "*" if e is active else " "
            line = f"{star}{e.name:<12} {e.chassis:<9} {ui.hp_bar(e, state)} {e.hp:>3}/{e.max_hp:<3} {'/'.join(e.weapons)}"
            ui.put(y, 2, line if e.alive else f" {e.name:<12} {e.chassis:<9} [ DESTROYED ]", attr)
            y += 1
        y += 1
        ui.put(y, 2, "CHROME DOGS", ui.C_OK | curses.A_BOLD); y += 1
        for m in squad:
            attr = ui.C_OK if m.alive else curses.A_DIM
            star = "*" if m is active else " "
            brace = " (braced)" if m.braced else ""
            line = f"{star}{m.name:<12} {m.chassis:<9} {ui.hp_bar(m, state)} {m.hp:>3}/{m.max_hp:<3} {'/'.join(m.weapons)}{brace}"
            ui.put(y, 2, line if m.alive else f" {m.name:<12} {m.chassis:<9} [ DOWN ]", attr)
            y += 1
        y += 1
        ui.put(y, 2, "-" * (w - 4), curses.A_DIM); y += 1
        for line in log[-(max(3, h - y - 6)):]:
            ui.put(y, 2, line, curses.A_DIM)
            y += 1
        if prompt:
            ui.put(h - len(prompt_items) - 3, 2, prompt, curses.A_BOLD)
            for i, (label, enabled, _) in enumerate(prompt_items):
                attr = curses.A_REVERSE if i == prompt_sel else 0
                if not enabled:
                    attr |= curses.A_DIM
                ui.put(h - len(prompt_items) - 2 + i, 4,
                       ("> " if i == prompt_sel else "  ") + label, attr)
        ui.scr.refresh()

    def battle_menu(prompt, items):
        sel = 0
        while True:
            draw(prompt=prompt, prompt_items=items, prompt_sel=sel)
            k = ui.scr.getch()
            if k in (curses.KEY_UP, ord('k')):
                sel = (sel - 1) % len(items)
            elif k in (curses.KEY_DOWN, ord('j')):
                sel = (sel + 1) % len(items)
            elif k in (10, 13, curses.KEY_ENTER):
                if items[sel][1]:
                    return sel
                curses.flash()
            elif k in (ord('q'), 27):
                return None

    while any(m.alive for m in squad) and any(e.alive for e in enemies) and rounds < 99:
        rounds += 1
        log.append(f"— Round {rounds} —")
        for unit in initiative_order(state, squad + enemies):
            if not unit.alive:
                continue
            if not any(m.alive for m in squad) or not any(e.alive for e in enemies):
                break
            unit.braced = False
            if unit.is_player:
                acted = False
                while not acted:
                    actions = []
                    for w in unit.weapons:
                        lo, hi = WEAPONS[w]["dmg"]
                        if WEAPONS[w]["heal"]:
                            left = unit.heal_remaining(w)
                            actions.append((f"Deploy {w}  ({lo}-{hi} repair, revives downed, "
                                            f"{left} left)", left > 0, None))
                        else:
                            actions.append((f"Fire {w}  ({lo}-{hi} dmg, "
                                            f"{unit.accuracy(state, w)}% acc)", True, None))
                    actions.append(("Brace  (+3 armor, harder to hit until next turn)", True, None))
                    a = battle_menu(f"{unit.name}'s move:", actions)
                    if a is None:
                        # attempt withdrawal
                        conf = battle_menu("Withdraw from the contract? Downed frames are lost.",
                                           [("Fight on", True, None), ("Withdraw", True, None)])
                        if conf == 1:
                            lost = [m for m in squad if not m.alive]
                            payout = sum(m.value() for m in lost) // 3
                            state.credits += payout
                            state.roster[:] = [m for m in state.roster if m not in squad or m.alive]
                            lines = ["The Dogs pull back. No pay, no salvage."]
                            if lost:
                                lines.append("Downed frames are left to the scavengers. "
                                             f"Insurance pays {payout:,}cr.")
                            ui.notice(state, "WITHDRAWAL", lines)
                            return
                        continue
                    if a < len(unit.weapons):
                        weapon = unit.weapons[a]
                        if WEAPONS[weapon]["heal"]:
                            tgts = list(squad)
                            titems = []
                            for m in tgts:
                                tag = "[DOWN] " if not m.alive else ""
                                self_tag = " (self)" if m is unit else ""
                                titems.append((f"{tag}{m.name:<12} {m.chassis:<9} "
                                               f"{m.hp}/{m.max_hp}hp{self_tag}", True, None))
                            t = battle_menu(f"Repair target for {weapon}:", titems)
                            if t is None:
                                continue
                            log.append(resolve_heal(state, unit, weapon, tgts[t]))
                            acted = True
                        else:
                            tgts = [e for e in enemies if e.alive]
                            titems = [(f"{e.name:<12} {e.chassis:<9} {e.hp}/{e.max_hp}hp  "
                                       f"armor {e.armor(state)}", True, None) for e in tgts]
                            t = battle_menu(f"Target for {weapon}:", titems)
                            if t is None:
                                continue
                            log.append(resolve_attack(state, unit, weapon, tgts[t]))
                            acted = True
                    else:
                        unit.braced = True
                        log.append(f"{unit.name} braces.")
                        acted = True
            else:
                weapon, target = enemy_choose_action(state, unit, squad)
                if weapon:
                    log.append(resolve_attack(state, unit, weapon, target))
                draw(active=unit)
                time.sleep(0.35)

    won = not any(e.alive for e in enemies)
    if won:
        credits, salvage = contract_rewards(state, outfit, first_time)
        state.credits += credits
        state.salvage += salvage
        state.beaten.add(outfit["name"])
        recovered = [m for m in squad if not m.alive]
        for m in recovered:
            m.hp = 1
        lines = [f"Contract fulfilled. {outfit['name']} written off.",
                 f"Payment: {credits:,}cr.  Salvage recovered: {salvage} tons."]
        if recovered:
            lines.append("Downed frames dragged home at 1 HP: " +
                         ", ".join(m.name for m in recovered) + ".")
        ui.notice(state, "CONTRACT COMPLETE", lines)
        if outfit["name"] == "Force Majeure":
            state.won = True
    else:
        lost = [m for m in squad if not m.alive]
        state.roster[:] = [m for m in state.roster if m.alive]
        payout = sum(m.value() for m in lost) // 3
        state.credits += payout
        lines = ["The Dogs are wiped off the field. No pay. No salvage."]
        if lost:
            lines.append("Frames lost to enemy salvage crews: " +
                         ", ".join(m.name for m in lost) + ".")
            lines.append(f"The underwriters pay out a third: {payout:,}cr against the write-off.")
        ui.notice(state, "CONTRACT FAILED", lines)


def screen_victory(ui, state):
    ui.notice(state, "MARKET DOMINANCE", [
        "Force Majeure's stock ticker flatlines on every exchange that still exists.",
        "",
        "The Chrome Dogs are now the only solvent outfit on the continent —",
        "which makes you, technically, the war economy.",
        "",
        "The contracts will keep coming. They always do.",
        "",
        f"Final ledger: {state.credits:,} credits, {state.salvage} tons of salvage, "
        f"{len(state.techs)}/{len(TECHS)} technologies.",
    ])


def screen_gameover(ui, state):
    ui.notice(state, "INSOLVENT", [
        "No frames. No credits. No collateral.",
        "",
        "The Chrome Dogs are dissolved by their creditors and sold for parts.",
        "Somewhere, an accountant at Force Majeure closes your file.",
    ])


def main_loop(stdscr):
    ui = UI(stdscr)
    state = screen_title(ui)
    if state is None:
        return
    while True:
        if state.won:
            screen_victory(ui, state)
            try:
                os.remove(SAVE_FILE)
            except OSError:
                pass
            return
        cheapest = CHASSIS["Jackal"]["cost"] + WEAPONS["SMG Pod"]["cost"]
        if not state.roster and state.credits < cheapest:
            screen_gameover(ui, state)
            try:
                os.remove(SAVE_FILE)
            except OSError:
                pass
            return
        nxt = state.next_contract_index()
        nxt_name = OUTFITS[nxt]["name"] if nxt is not None else "—"
        items = [
            ("Contract board", True, f"Next target: {nxt_name}"),
            ("Hangar", True, "Build, repair, and refit your frames."),
            ("R&D lab", True, "Invest war prizes into technology."),
            ("Save & quit", True, None),
        ]
        sel = ui.menu(state, "HQ — CHROME DOGS", items,
                      footer_text="up/down: move   enter: select")
        if sel is None:
            continue
        label = items[sel][0]
        if label == "Contract board":
            screen_contracts(ui, state)
        elif label == "Hangar":
            screen_hangar(ui, state)
        elif label == "R&D lab":
            screen_rnd(ui, state)
        else:
            with open(SAVE_FILE, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
            return


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    if curses is None:
        print("No curses available. Run the web build, or install a real terminal.")
        return
    curses.wrapper(main_loop)


if __name__ == "__main__":
    main()
