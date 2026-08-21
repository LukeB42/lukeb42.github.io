"""
TOUR DE FORCE: INTERDICTION FORCE

2205. Ninety years after a directed nanomachine matrix walked out of a
black site alone and answered to the name Gene Carpenter, DISA still
officially doesn't exist and still fields the one piece of hardware that
makes any of this survivable: the vapor suit. Eight billion pounds
sterling of nanomachine swarm per operative, woven into a kinetic-
abatement layer that strips incoming slugs for feedstock and prints
fresh charge into the suit's systems. Regular rounds cannot hurt a suited
operative - the suit eats them and gets stronger.

The one thing no suit stops is bioweaponized ordnance: rounds cultured
with a necrotising fasciitis payload that ride straight through the
weave. It doesn't drop you on the spot - it seeds a shadow in the weave
that spreads the longer you keep pushing, eating you alive one dark
patch at a time, and burns back out fast the moment you hold position
and let the swarm work.

Four suits, this time, not one. LOCKE SMITH leads a fireteam that
doesn't officially exist any more than DISA does: IAN FORMANT on point,
ROSE GARDNER running the suits' tech stack from inside the squad instead
of a control room, DAISY FIELDS closing kills. Get to extraction. Or
leave nobody standing to report you didn't.
"""

# --------------------------------------------------------------------------
# Cast / org
# --------------------------------------------------------------------------

PLAYER_NAME = "Locke Smith"
SQUAD_NAMES = ["Locke Smith", "Ian Formant", "Rose Gardner", "Daisy Fields"]
HANDLER_NAME = "Olive Branch"
ORG_NAME = "DISA"
ORG_FULL_NAME = "Department of Integrated Security Activities"
MISSION_YEAR = 2205

VAPOR_SUIT_COST = "£8,000,000,000"
VAPOR_SUIT_COST_SQUAD = "£32,000,000,000"

GAME_TITLE = "TOUR DE FORCE: INTERDICTION FORCE"

SPLASH_TEXT = """Ninety years ago a directed nanomachine matrix walked out of a black
site alone, wearing eight billion pounds of hardware DISA never
officially built, and answered to the name Gene Carpenter. The suit is
common knowledge now, inside the rooms where it's allowed to be knowledge
at all: a kinetic-abatement swarm that strips incoming rounds for
feedstock and prints them back out as charge. Regular gunfire cannot hurt
a suited operative. It just feeds them.
Bio-coated rounds are the exception - a cultured necrotising fasciitis
payload that slips straight through the weave. It won't drop you on
contact. It seeds a shadow in the weave that spreads for as long as you
keep pushing through it, eating you alive one dark patch at a time.
Hold position and let the swarm burn the dark back out, and it's gone
in seconds.
Four suits this time, not one: LOCKE SMITH, IAN FORMANT, ROSE GARDNER,
DAISY FIELDS. Thirty-two billion pounds of hardware that, on paper,
does not exist, deployed by an agency that, on paper, does not exist.
Get to extraction. Or don't leave anyone who can say you didn't."""

# --------------------------------------------------------------------------
# Tiles / environments (shared with the overworld map generator)
# --------------------------------------------------------------------------

FLOOR = "."
GRASS = "\""
WALL = "#"
RUBBLE = ","
DOOR = "="
EXFIL_SYMBOL = "X"

ENV_RUIN = "ruin"
ENV_BUNKER = "bunker"

FOG_UNSEEN = 0
FOG_EXPLORED = 1
FOG_VISIBLE = 2

# --------------------------------------------------------------------------
# Weapon / threat model (identical logic to TDF, reframed for squad combat)
# --------------------------------------------------------------------------

WEAPON_VAPOR = "vapor"   # kinetic - harmless to a suited target, feeds Suit Charge
WEAPON_NECRO = "necro"   # bio-coated - the only thing that actually hurts

WEAPON_META = {
    WEAPON_VAPOR: dict(glyph="V", desc="Standard AP - the suit eats it and prints charge."),
    WEAPON_NECRO: dict(glyph="B", desc="Bio-coated round - necrotising fasciitis. Slips the weave."),
}

# --------------------------------------------------------------------------
# Battle tuning
# --------------------------------------------------------------------------

NECRO_LOAD_CAP = 100
NECRO_LOAD_PER_HIT = 22
NECRO_DRAIN_DIVISOR = 5          # hp lost on an acting turn = load // this
NECRO_DEFEND_DECAY = 40          # load burned off by choosing Defend
NECRO_CRITICAL_DRAIN = 8         # extra flat hp/turn once load caps out

# Outside a fight the swarm keeps working unopposed - load bleeds off on
# its own between engagements, one overworld tick at a time.
NECRO_OVERWORLD_DECAY_PER_TICK = 1

SC_REGEN_PER_TURN = 6
SC_REGEN_DEFENDING = 12
SC_FEEDSTOCK_PER_VAPOR_HIT = 8

DEFEND_DMG_REDUCTION = 0.5

# --------------------------------------------------------------------------
# Squad roster - base stats and role flavour. Abilities live in party.py.
# --------------------------------------------------------------------------

SQUAD_BASE_STATS = {
    "Locke Smith":  dict(role="Vanguard", max_hp=140, atk=16, dfn=10, spd=9,  max_sc=40, row="front"),
    "Ian Formant":  dict(role="Heavy",    max_hp=180, atk=14, dfn=16, spd=6,  max_sc=30, row="front"),
    "Rose Gardner": dict(role="Tech",     max_hp=100, atk=10, dfn=8,  spd=10, max_sc=50, row="back"),
    "Daisy Fields": dict(role="Striker",  max_hp=110, atk=20, dfn=7,  spd=11, max_sc=35, row="back"),
}

# Human-readable site-tier names for log lines - "dumb" is the acronym
# (deep underground military base), not a plain word, so .title() would
# mangle it.
TIER_DISPLAY_NAMES = {
    "militia": "Militia",
    "dumb": "DUMB",
    "blacksite": "Black Site",
}

# --------------------------------------------------------------------------
# Overworld / mission tiers
# --------------------------------------------------------------------------

LEVELS = [
    dict(name="Rustwater Compound", world_w=240, world_h=120,
         env=ENV_RUIN, palette="sand", tier="militia",
         n_squads=15, squad_size=(2, 3), vapor_bias=0.6, boss_squad=False,
         blurb="Ninety years on it's still a scrap-fed militia outpost. Sand, "
               "dead grass, and nobody who'll admit DISA was ever here."),
    dict(name="Deniable Assets Site", world_w=150, world_h=80,
         env=ENV_BUNKER, palette="bunker", tier="dumb",
         n_squads=8, squad_size=(2, 4), vapor_bias=0.45, boss_squad=True,
         blurb="A DUMB - deep underground military base. Poured concrete, "
               "blast doors, and a containment officer who won't fall easy."),
    dict(name="Force Majeure Black Site", world_w=180, world_h=100,
         env=ENV_RUIN, palette="blood", tier="blacksite",
         n_squads=10, squad_size=(3, 4), vapor_bias=0.3, boss_squad=True,
         blurb="The event no contract survives. Bio rounds everywhere you "
               "look, and a Handler waiting at the end of it."),
]

# --------------------------------------------------------------------------
# Codec-style pre-mission briefings - Olive Branch runs mission control;
# the squad talks over each other the way people who trust each other do.
# One theme is picked at random per deployment.
# --------------------------------------------------------------------------

CODEC_THEMES = [
    dict(title="FOUR SUITS, ONE INVOICE", lines=[
        ("OLIVE", "Squad, come in. DISA's tracking unregistered hardware movement on site."),
        ("LOCKE", "Define 'unregistered.' We're four vapor suits deep into 'unregistered.'"),
        ("OLIVE", "Fair. Confirm what's there, get out, nothing with your names on it if it goes loud."),
        ("IAN", "It always goes loud. It's fine. That's what the suits are for."),
        ("OLIVE", "Try to remember that's a joke, Ian."),
        ("LOCKE", "Copy. Squad's moving in."),
    ]),
    dict(title="GHOST STORY", lines=[
        ("ROSE", "Olive, there's a name in the old DISA archive on this site. Gene Carpenter."),
        ("OLIVE", "Before your time. Before mine, honestly. One operative, no suit doctrine to follow, "
                   "just improvised. Case study, mostly, at this point."),
        ("DAISY", "One suit and a body count like that? I'd take the doctrine, thanks."),
        ("IAN", "Four suits and a doctrine, and we still open every op with a legend. Comforting."),
        ("LOCKE", "Copy the history lesson. Squad's moving."),
    ]),
    dict(title="OFF THE BOOKS", lines=[
        ("OLIVE", "There's an auction running on-site. Nanotech blueprints, no export license, no questions."),
        ("ROSE", "Guest list reads like everyone DISA's not allowed to admit exists. Including all four of you."),
        ("OLIVE", "Shut it down. Buyers don't need to be breathing when you leave - your call."),
        ("DAISY", "It's always my call by the time it matters."),
        ("LOCKE", "Squad's advancing. Keep the channel clean."),
    ]),
    dict(title="STATIC ON THE LINE", lines=[
        ("OLIVE", "This is a welfare check. DISA outstation on site went dark six hours ago."),
        ("IAN", "Last transmission?"),
        ("OLIVE", "Channel noise. No words. We don't like that."),
        ("ROSE", "Could be jamming. Could be everyone in there is already necrotic-loaded past caring."),
        ("LOCKE", "Then we go find out which. Moving in."),
    ]),
    dict(title="PAPER TRAIL", lines=[
        ("OLIVE", "There's a ledger on-site tying this outfit's funding straight back to a DISA line item."),
        ("ROSE", "Which is awkward, since officially we've never heard of them."),
        ("OLIVE", "Pull the ledger. Whatever else happens on-site is secondary to that drive."),
        ("DAISY", "So the priority order is: drive, squad, everything else. Got it."),
        ("OLIVE", "That's not - Daisy. Just get the drive."),
        ("LOCKE", "Copy. Moving to confirm."),
    ]),
    dict(title="SECOND OPINION", lines=[
        ("OLIVE", "We've got an operative captured on site three days ago. Still alive, as of an hour ago."),
        ("IAN", "Their interrogators aren't known for patience. That clock isn't on our side."),
        ("LOCKE", "Then we don't waste it talking. Squad's moving, full pace."),
        ("ROSE", "Formation discipline, Locke. Full pace doesn't mean front-loading Ian into every room."),
        ("IAN", "It's usually worked."),
    ]),
]
