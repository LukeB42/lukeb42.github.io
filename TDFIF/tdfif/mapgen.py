"""Tile-map generation and line-of-sight, adapted from TDF's world/bunker
generators. Same tile vocabulary, same generation approach - the overworld
here is for navigation and stealth/contact, not gunfire, but it should
feel like the same universe to walk around in."""

import random

from .constants import DOOR, FLOOR, GRASS, RUBBLE, WALL


def _sign(n):
    return (n > 0) - (n < 0)


def line_of_sight(grid, x0, y0, x1, y1):
    """Bresenham walk; False if a WALL or a closed blast DOOR sits strictly
    between the two endpoints."""
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while (x, y) != (x1, y1):
        if (x, y) != (x0, y0) and grid[y][x] in (WALL, DOOR):
            return False
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return True


def generate_world(width, height):
    grid = [[FLOOR for _ in range(width)] for _ in range(height)]

    for x in range(width):
        grid[0][x] = WALL
        grid[height - 1][x] = WALL
    for y in range(height):
        grid[y][0] = WALL
        grid[y][width - 1] = WALL

    n_blocks = (width * height) // 200
    for _ in range(n_blocks):
        bw = random.randint(2, 6)
        bh = random.randint(2, 5)
        bx = random.randint(2, width - bw - 2)
        by = random.randint(2, height - bh - 2)
        for y in range(by, by + bh):
            for x in range(bx, bx + bw):
                grid[y][x] = WALL

    n_patches = max(8, (width * height) // 550)
    for _ in range(n_patches):
        cx = random.randint(2, width - 3)
        cy = random.randint(2, height - 3)
        r = random.randint(5, 13)
        core2 = (r * 0.6) ** 2
        r2 = r * r
        for yy in range(max(1, cy - r), min(height - 1, cy + r + 1)):
            for xx in range(max(1, cx - r), min(width - 1, cx + r + 1)):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                if d2 > r2 or grid[yy][xx] != FLOOR:
                    continue
                if d2 <= core2 or random.random() < 0.75:
                    grid[yy][xx] = GRASS

    for _ in range(width * height // 70):
        x = random.randint(1, width - 2)
        y = random.randint(1, height - 2)
        if grid[y][x] == FLOOR:
            grid[y][x] = RUBBLE

    return grid


def clear_area(grid, cx, cy, radius):
    for y in range(max(1, cy - radius), min(len(grid) - 1, cy + radius + 1)):
        for x in range(max(1, cx - radius), min(len(grid[0]) - 1, cx + radius + 1)):
            grid[y][x] = FLOOR


def _carve_room(grid, x0, y0, w, h):
    width, height = len(grid[0]), len(grid)
    x0 = max(1, min(width - 3, x0))
    y0 = max(1, min(height - 3, y0))
    x1 = max(x0 + 1, min(width - 2, x0 + w))
    y1 = max(y0 + 1, min(height - 2, y0 + h))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            grid[y][x] = FLOOR
    return (x0, y0, x1, y1)


def _carve_corridor(grid, x0, y0, x1, y1, door_chance=0.55):
    width, height = len(grid[0]), len(grid)
    pts = []
    if random.random() < 0.5:
        for x in range(min(x0, x1), max(x0, x1) + 1):
            pts.append((x, y0))
        for y in range(min(y0, y1), max(y0, y1) + 1):
            pts.append((x1, y))
    else:
        for y in range(min(y0, y1), max(y0, y1) + 1):
            pts.append((x0, y))
        for x in range(min(x0, x1), max(x0, x1) + 1):
            pts.append((x, y1))
    for x, y in pts:
        if 1 <= x < width - 1 and 1 <= y < height - 1 and grid[y][x] == WALL:
            grid[y][x] = FLOOR
    for x, y in (pts[0], pts[-1]) if pts else ():
        if 1 <= x < width - 1 and 1 <= y < height - 1 and random.random() < door_chance:
            grid[y][x] = DOOR


def generate_bunker_world(width, height, anchor):
    grid = [[WALL for _ in range(width)] for _ in range(height)]
    ax, ay = anchor

    rw, rh = random.randint(8, 12), random.randint(6, 9)
    rooms = [_carve_room(grid, ax - rw // 2, ay - rh // 2, rw, rh)]

    n_rooms = max(14, (width * height) // 1600)
    for _ in range(n_rooms):
        rw, rh = random.randint(6, 14), random.randint(5, 10)
        rx = random.randint(2, max(3, width - rw - 3))
        ry = random.randint(2, max(3, height - rh - 3))
        room = _carve_room(grid, rx, ry, rw, rh)
        prev = rooms[-1]
        cx0, cy0 = (prev[0] + prev[2]) // 2, (prev[1] + prev[3]) // 2
        cx1, cy1 = (room[0] + room[2]) // 2, (room[1] + room[3]) // 2
        _carve_corridor(grid, cx0, cy0, cx1, cy1)
        rooms.append(room)

    for _ in range(width * height // 140):
        x = random.randint(1, width - 2)
        y = random.randint(1, height - 2)
        if grid[y][x] == FLOOR and random.random() < 0.5:
            grid[y][x] = RUBBLE

    for x in range(width):
        grid[0][x] = WALL
        grid[height - 1][x] = WALL
    for y in range(height):
        grid[y][0] = WALL
        grid[y][width - 1] = WALL

    return grid


def move_towards(grid, world_w, world_h, x, y, tx, ty, tile_free):
    """Step (x, y) one tile towards (tx, ty), diagonal-first, using
    tile_free(nx, ny) -> bool. Returns the new (x, y)."""
    dx, dy = _sign(tx - x), _sign(ty - y)
    candidates = []
    if dx and dy:
        candidates.append((x + dx, y + dy))
    if dx:
        candidates.append((x + dx, y))
    if dy:
        candidates.append((x, y + dy))
    for nx, ny in candidates:
        if tile_free(nx, ny):
            return nx, ny
    return x, y
