"""
SOLVENT web bridge — JSON command API over the game logic.
Loaded into Pyodide after solvent.py's logic layer. No curses, no DOM:
just state in, JSON out. The JS terminal is a dumb renderer.
"""
import json
import random

_G = {"state": None, "battle": None}


def _mech_view(m, state):
    return dict(uid=m.uid, name=m.name, chassis=m.chassis, weapons=list(m.weapons),
                hp=m.hp, max_hp=m.max_hp, alive=m.alive, braced=m.braced,
                armor=m.armor(state), speed=m.speed(state),
                evade=CHASSIS[m.chassis]["evade"],
                repair_cost=m.repair_cost(), value=m.value(),
                heal_left={w: m.heal_remaining(w) for w in m.weapons
                           if WEAPONS[w].get("heal")})


def _state_view():
    s = _G["state"]
    nxt = s.next_contract_index()
    contracts = []
    for i, o in enumerate(OUTFITS):
        beaten = o["name"] in s.beaten
        locked = nxt is not None and i > nxt
        c, sv = contract_rewards(s, o, not beaten)
        contracts.append(dict(name=o["name"], tier=o["tier"], blurb=o["blurb"],
                              beaten=beaten, locked=locked, credits=c, salvage=sv))
    techs = []
    for key in s.available_techs():
        t = TECHS[key]
        techs.append(dict(key=key, name=t["name"], desc=t["desc"],
                          credits=t["credits"], salvage=t["salvage"],
                          afford=s.credits >= t["credits"] and s.salvage >= t["salvage"]))
    chassis = []
    for c in s.unlocked_chassis():
        d = CHASSIS[c]
        chassis.append(dict(name=c, cost=d["cost"], hp=d["hp"], armor=d["armor"],
                            speed=d["speed"], evade=d["evade"], hardpoints=d["hardpoints"],
                            desc=d["desc"], afford=s.credits >= d["cost"]))
    weapons = []
    for w in s.unlocked_weapons():
        d = WEAPONS[w]
        weapons.append(dict(name=w, cost=d["cost"], lo=d["dmg"][0], hi=d["dmg"][1],
                            acc=d["acc"], heal=bool(d.get("heal")),
                            charges=d.get("charges", 0), desc=d["desc"],
                            afford=s.credits >= d["cost"]))
    return dict(credits=s.credits, salvage=s.salvage,
                researched=sorted(TECHS[k]["name"] for k in s.techs),
                roster=[_mech_view(m, s) for m in s.roster],
                contracts=contracts, techs=techs,
                shop_chassis=chassis, shop_weapons=weapons,
                won=s.won,
                game_over=(not s.roster and s.credits <
                           CHASSIS["Jackal"]["cost"] + WEAPONS["SMG Pod"]["cost"]))


# ---------------------------------------------------------------- battle glue

def _battle_over_check():
    b = _G["battle"]
    s = _G["state"]
    squad, enemies = b["squad"], b["enemies"]
    if any(e.alive for e in enemies) and any(m.alive for m in squad) \
            and b["round"] < 99:
        return None
    won = not any(e.alive for e in enemies)
    result = dict(kind="over", won=won)
    if won:
        credits, salvage = contract_rewards(s, b["outfit"], b["first_time"])
        s.credits += credits
        s.salvage += salvage
        s.beaten.add(b["outfit"]["name"])
        recovered = [m.name for m in squad if not m.alive]
        for m in squad:
            if not m.alive:
                m.hp = 1
        result.update(credits=credits, salvage=salvage, recovered=recovered,
                      final=b["outfit"]["name"] == "Force Majeure")
        if result["final"]:
            s.won = True
    else:
        lost = [m for m in squad if not m.alive]
        payout = sum(m.value() for m in lost) // 3
        s.credits += payout
        s.roster[:] = [m for m in s.roster if m.alive]
        result.update(lost=[m.name for m in lost], insurance=payout)
    _G["battle"] = None
    return result


def _battle_view(extra):
    b = _G["battle"]
    s = _G["state"]
    v = dict(kind=extra.get("kind", "view"),
             outfit=b["outfit"]["name"], round=b["round"],
             squad=[_mech_view(m, s) for m in b["squad"]],
             enemies=[_mech_view(e, s) for e in b["enemies"]],
             log=b["log"][-14:])
    v.update(extra)
    return v


def _start_battle(outfit_idx, squad_uids):
    s = _G["state"]
    outfit = OUTFITS[outfit_idx]
    squad = [m for m in s.roster if m.uid in squad_uids and m.alive and m.weapons]
    if not (0 < len(squad) <= 4):
        return dict(kind="error", msg="Deploy 1-4 armed frames.")
    for m in squad:
        m.heal_used = {}
        m.braced = False
    enemies = build_enemy_squad(outfit)
    _G["battle"] = dict(outfit=outfit, squad=squad, enemies=enemies,
                        first_time=outfit["name"] not in s.beaten,
                        round=0, order=[], ptr=0,
                        log=[f"Contract accepted: {outfit['name']}.",
                             outfit["blurb"]])
    return _battle_view({"kind": "started"})


def _battle_next():
    """Advance until player input is needed, an enemy acts, or it's over."""
    b = _G["battle"]
    s = _G["state"]
    if b is None:
        return dict(kind="error", msg="No battle in progress.")
    over = _battle_over_check()
    if over:
        return over
    while True:
        if b["ptr"] >= len(b["order"]):
            b["round"] += 1
            b["log"].append(f"— Round {b['round']} —")
            b["order"] = [u.uid for u in
                          initiative_order(s, b["squad"] + b["enemies"])]
            b["ptr"] = 0
        uid = b["order"][b["ptr"]]
        unit = next((u for u in b["squad"] + b["enemies"] if u.uid == uid), None)
        if unit is None or not unit.alive:
            b["ptr"] += 1
            continue
        over = _battle_over_check()
        if over:
            return over
        unit.braced = False
        if unit.is_player:
            actions = []
            for w in unit.weapons:
                d = WEAPONS[w]
                if d.get("heal"):
                    left = unit.heal_remaining(w)
                    actions.append(dict(type="heal", weapon=w, lo=d["dmg"][0],
                                        hi=d["dmg"][1], left=left,
                                        enabled=left > 0))
                else:
                    actions.append(dict(type="fire", weapon=w, lo=d["dmg"][0],
                                        hi=d["dmg"][1],
                                        acc=unit.accuracy(s, w), enabled=True))
            actions.append(dict(type="brace", enabled=True))
            return _battle_view(dict(kind="need_player", unit_uid=unit.uid,
                                     unit_name=unit.name, actions=actions))
        weapon, target = enemy_choose_action(s, unit, b["squad"])
        if weapon:
            b["log"].append(resolve_attack(s, unit, weapon, target))
        b["ptr"] += 1
        over = _battle_over_check()
        if over:
            return over
        return _battle_view(dict(kind="enemy_acted", unit_uid=unit.uid))


def _battle_player(act):
    b = _G["battle"]
    s = _G["state"]
    if b is None:
        return dict(kind="error", msg="No battle in progress.")
    uid = b["order"][b["ptr"]]
    unit = next(u for u in b["squad"] if u.uid == uid)
    if act["type"] == "brace":
        unit.braced = True
        b["log"].append(f"{unit.name} braces.")
    elif act["type"] == "fire":
        target = next(e for e in b["enemies"] if e.uid == act["target"])
        b["log"].append(resolve_attack(s, unit, act["weapon"], target))
    elif act["type"] == "heal":
        if unit.heal_remaining(act["weapon"]) <= 0:
            return dict(kind="error", msg="No charges left.")
        target = next(m for m in b["squad"] if m.uid == act["target"])
        b["log"].append(resolve_heal(s, unit, act["weapon"], target))
    b["ptr"] += 1
    over = _battle_over_check()
    if over:
        return over
    return _battle_view({"kind": "player_acted"})


def _battle_withdraw():
    b = _G["battle"]
    s = _G["state"]
    if b is None:
        return dict(kind="error", msg="No battle in progress.")
    lost = [m for m in b["squad"] if not m.alive]
    payout = sum(m.value() for m in lost) // 3
    s.credits += payout
    s.roster[:] = [m for m in s.roster if m not in b["squad"] or m.alive]
    _G["battle"] = None
    return dict(kind="withdrew", lost=[m.name for m in lost], insurance=payout)


# ---------------------------------------------------------------- commands

def api(cmd, payload_json="{}"):
    p = json.loads(payload_json)
    s = _G["state"]
    try:
        if cmd == "meta":
            return json.dumps(dict(
                title="S O L V E N T", byline="a Chrome Dogs operation / by Float64",
                intro=[
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
                ]))
        if cmd == "new_game":
            _G["state"] = new_game()
            _G["battle"] = None
            return json.dumps(_state_view())
        if cmd == "view":
            return json.dumps(_state_view())
        if cmd == "export_save":
            return json.dumps(dict(save=_G["state"].to_dict()))
        if cmd == "import_save":
            _G["state"] = GameState.from_dict(p["save"])
            _G["battle"] = None
            return json.dumps(_state_view())
        if cmd == "repair":
            m = next(x for x in s.roster if x.uid == p["uid"])
            cost = m.repair_cost()
            if cost and s.credits >= cost:
                s.credits -= cost
                m.hp = m.max_hp
            return json.dumps(_state_view())
        if cmd == "repair_all":
            total = sum(m.repair_cost() for m in s.roster)
            if s.credits >= total:
                s.credits -= total
                for m in s.roster:
                    m.hp = m.max_hp
            return json.dumps(_state_view())
        if cmd == "fit":
            m = next(x for x in s.roster if x.uid == p["uid"])
            w = p["weapon"]
            if (w in s.unlocked_weapons() and s.credits >= WEAPONS[w]["cost"]
                    and len(m.weapons) < CHASSIS[m.chassis]["hardpoints"]):
                s.credits -= WEAPONS[w]["cost"]
                m.weapons.append(w)
            return json.dumps(_state_view())
        if cmd == "strip":
            m = next(x for x in s.roster if x.uid == p["uid"])
            if len(m.weapons) > 1 and 0 <= p["index"] < len(m.weapons):
                w = m.weapons.pop(p["index"])
                s.credits += WEAPONS[w]["cost"] // 2
            return json.dumps(_state_view())
        if cmd == "scrap":
            m = next(x for x in s.roster if x.uid == p["uid"])
            if len(s.roster) > 1:
                s.credits += m.value() // 3
                s.roster.remove(m)
            return json.dumps(_state_view())
        if cmd == "buy":
            c = p["chassis"]
            if c in s.unlocked_chassis() and s.credits >= CHASSIS[c]["cost"]:
                s.credits -= CHASSIS[c]["cost"]
                used = {m.name for m in s.roster}
                pool = [n for n in DOG_NAMES if n not in used] or DOG_NAMES
                s.roster.append(Mech(random.choice(pool), c, []))
            return json.dumps(_state_view())
        if cmd == "research":
            key = p["key"]
            if key in s.available_techs():
                t = TECHS[key]
                if s.credits >= t["credits"] and s.salvage >= t["salvage"]:
                    s.credits -= t["credits"]
                    s.salvage -= t["salvage"]
                    s.techs.add(key)
            return json.dumps(_state_view())
        if cmd == "start_battle":
            return json.dumps(_start_battle(p["outfit"], p["uids"]))
        if cmd == "battle_next":
            return json.dumps(_battle_next())
        if cmd == "battle_player":
            return json.dumps(_battle_player(p))
        if cmd == "battle_withdraw":
            return json.dumps(_battle_withdraw())
        return json.dumps(dict(kind="error", msg=f"unknown command {cmd}"))
    except Exception as e:  # surface errors to JS console rather than dying
        return json.dumps(dict(kind="error", msg=f"{type(e).__name__}: {e}"))
