"""Shared curses plumbing: safe draw helpers, palettes, and the
splash/mission-select/codec screens. All game logic lives elsewhere;
this module only ever touches the screen."""

import curses
import textwrap

from . import constants as C

# --------------------------------------------------------------------------
# Pair numbers, shared across every screen
# --------------------------------------------------------------------------

PAIR_PLAYER = 1
PAIR_WALL = 3
PAIR_HUD = 4
PAIR_DANGER = 5
PAIR_WARN = 6
PAIR_VAPOR = 8
PAIR_NECRO = 9
PAIR_FLOOR = 11
PAIR_GRASS = 12
PAIR_EXFIL = 13
PAIR_ACCENT = 14
PAIR_DOOR = 15
PAIR_GOOD = 17
PAIR_ELITE = 18

PAIR_MENU_CHROME = 24
PAIR_CLOSED_PHOSPHOR = 25
PAIR_CODEC_CHROME = 20
CODEC_SPEAKER_PAIRS = {"OLIVE": 21, "LOCKE": 22, "IAN": 26, "ROSE": 27, "DAISY": 28}


def _palette_sand(has_256):
    return {1: curses.COLOR_CYAN, 3: curses.COLOR_WHITE, 4: curses.COLOR_GREEN,
            5: curses.COLOR_RED, 6: curses.COLOR_YELLOW, 8: curses.COLOR_MAGENTA,
            9: curses.COLOR_RED, 11: curses.COLOR_YELLOW, 12: curses.COLOR_GREEN,
            13: curses.COLOR_GREEN, 14: curses.COLOR_WHITE, 15: curses.COLOR_WHITE,
            17: curses.COLOR_GREEN, 18: curses.COLOR_MAGENTA}


def _palette_bunker(has_256):
    if has_256:
        concrete, concrete_lt, steel, hazard = 240, 250, 111, 178
    else:
        concrete, concrete_lt, steel, hazard = curses.COLOR_WHITE, curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_YELLOW
    return {1: curses.COLOR_CYAN, 3: concrete, 4: steel, 5: curses.COLOR_RED,
            6: hazard, 8: steel, 9: curses.COLOR_RED, 11: concrete_lt,
            12: concrete, 13: hazard, 14: curses.COLOR_WHITE, 15: hazard,
            17: curses.COLOR_CYAN, 18: hazard}


def _palette_blood(has_256):
    if has_256:
        blood_red, blood_orange = 88, 166
    else:
        blood_red, blood_orange = curses.COLOR_RED, curses.COLOR_YELLOW
    return {1: blood_orange, 3: blood_red, 4: blood_orange, 5: blood_red,
            6: blood_red, 8: blood_orange, 9: blood_red, 11: blood_orange,
            12: blood_red, 13: blood_orange, 14: blood_orange, 15: blood_red,
            17: blood_orange, 18: blood_red}


PALETTES = {"sand": _palette_sand, "bunker": _palette_bunker, "blood": _palette_blood}


def apply_palette(name):
    has_256 = curses.COLORS >= 256
    for pair_num, color in PALETTES[name](has_256).items():
        curses.init_pair(pair_num, color, -1)


def init_colors():
    curses.start_color()
    curses.use_default_colors()

    menu_color = 166 if curses.COLORS >= 256 else curses.COLOR_YELLOW
    curses.init_pair(PAIR_MENU_CHROME, menu_color, -1)
    curses.init_pair(PAIR_CLOSED_PHOSPHOR, curses.COLOR_GREEN, -1)

    curses.init_pair(PAIR_CODEC_CHROME, curses.COLOR_YELLOW, -1)
    olive_color = 58 if curses.COLORS >= 256 else curses.COLOR_YELLOW
    curses.init_pair(CODEC_SPEAKER_PAIRS["OLIVE"], olive_color, -1)
    curses.init_pair(CODEC_SPEAKER_PAIRS["LOCKE"], curses.COLOR_GREEN, -1)
    curses.init_pair(CODEC_SPEAKER_PAIRS["IAN"], curses.COLOR_WHITE, -1)
    curses.init_pair(CODEC_SPEAKER_PAIRS["ROSE"], curses.COLOR_MAGENTA, -1)
    curses.init_pair(CODEC_SPEAKER_PAIRS["DAISY"], curses.COLOR_RED, -1)

    apply_palette(C.LEVELS[0]["palette"])


# --------------------------------------------------------------------------
# Safe draw primitives
# --------------------------------------------------------------------------

def safe_addstr(stdscr, y, x, text, attr=0):
    max_y, max_x = stdscr.getmaxyx()
    if y < 0 or y >= max_y or x >= max_x or x < 0:
        return
    text = text[:max(0, max_x - x)]
    if not text:
        return
    try:
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass


def safe_addch(stdscr, y, x, ch, attr=0):
    max_y, max_x = stdscr.getmaxyx()
    if 0 <= y < max_y and 0 <= x < max_x - 1:
        try:
            stdscr.addch(y, x, ch, attr)
        except curses.error:
            pass


def bar(ratio, width, invert=False):
    ratio = max(0.0, min(1.0, ratio))
    filled = int(round(ratio * width))
    b = "#" * filled + "-" * (width - filled)
    good, mid, bad = (PAIR_DANGER, PAIR_WARN, PAIR_HUD) if invert else (PAIR_HUD, PAIR_WARN, PAIR_DANGER)
    if ratio > 0.66:
        pair = bad if invert else good
    elif ratio > 0.33:
        pair = mid
    else:
        pair = good if invert else bad
    return b, pair


# --------------------------------------------------------------------------
# Splash / mission select / codec briefing
# --------------------------------------------------------------------------

def draw_splash(stdscr):
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    lines = [C.GAME_TITLE, ""] + C.SPLASH_TEXT.split("\n") + ["", "Press any key to deploy..."]
    start_y = max(0, (max_y - len(lines)) // 2)
    for i, line in enumerate(lines):
        y = start_y + i
        if y >= max_y:
            break
        x = max(0, (max_x - len(line)) // 2)
        attr = curses.A_BOLD if i == 0 else 0
        try:
            stdscr.addstr(y, x, line[:max_x - 1], curses.color_pair(PAIR_MENU_CHROME) | attr)
        except curses.error:
            pass
    stdscr.refresh()


def draw_mission_select(stdscr, index, max_unlocked=0, status_msg=None):
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    title = "CHOOSE YOUR SITE"
    try:
        stdscr.addstr(1, max(0, (max_x - len(title)) // 2), title, curses.color_pair(PAIR_MENU_CHROME) | curses.A_BOLD)
    except curses.error:
        pass
    row = 3
    for i, lvl in enumerate(C.LEVELS):
        locked = i > max_unlocked
        marker = ">" if i == index else " "
        tag = "  [LOCKED]" if locked else ""
        line = f"{marker} {i + 1}) {lvl['name']}  ({lvl['world_w']}x{lvl['world_h']}, {lvl['n_squads']} hostile squads){tag}"
        if i == index:
            attr = curses.A_REVERSE | (curses.A_DIM if locked else 0)
        else:
            attr = curses.color_pair(PAIR_MENU_CHROME) | (curses.A_DIM if locked else 0)
        try:
            stdscr.addstr(row, 4, line[:max_x - 5], attr)
        except curses.error:
            pass
        row += 1
        if i == index:
            blurb = lvl["blurb"] if not locked else f"Complete {C.LEVELS[i - 1]['name']} to unlock this site."
            try:
                stdscr.addstr(row, 8, blurb[:max_x - 9], curses.A_DIM)
            except curses.error:
                pass
            row += 1
        row += 1
    hint = f"Up/Down: choose   Enter/1-{len(C.LEVELS)}: deploy   Q: quit"
    try:
        stdscr.addstr(row + 1, 4, hint, curses.color_pair(PAIR_MENU_CHROME))
    except curses.error:
        pass
    if status_msg:
        try:
            stdscr.addstr(row + 2, 4, status_msg[:max_x - 5], curses.color_pair(PAIR_DANGER) | curses.A_BOLD)
        except curses.error:
            pass
    stdscr.refresh()


def draw_codec(stdscr, theme, index):
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    header = f"INCOMING TRANSMISSION :: {theme['title']}"
    sub = f"{C.ORG_NAME} SECURE CHANNEL // {C.HANDLER_NAME.upper()} TO FIRETEAM"
    try:
        stdscr.addstr(1, max(0, (max_x - len(header)) // 2), header, curses.color_pair(PAIR_CODEC_CHROME) | curses.A_BOLD)
        stdscr.addstr(2, max(0, (max_x - len(sub)) // 2), sub[:max_x - 1], curses.A_DIM)
    except curses.error:
        pass

    lines = theme["lines"]
    shown = lines[:index + 1]
    row = 4
    for i, (speaker, text) in enumerate(shown):
        is_current = (i == len(shown) - 1)
        pair = CODEC_SPEAKER_PAIRS.get(speaker, PAIR_CODEC_CHROME)
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
        stdscr.addstr(max_y - 2, 4, hint, curses.color_pair(PAIR_CODEC_CHROME))
    except curses.error:
        pass
    stdscr.refresh()


def draw_closed(stdscr):
    stdscr.erase()
    try:
        stdscr.addstr(0, 0, "Session closed.", curses.color_pair(PAIR_CLOSED_PHOSPHOR) | curses.A_BOLD)
    except curses.error:
        pass
    stdscr.refresh()
