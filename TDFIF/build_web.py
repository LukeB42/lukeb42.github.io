#!/usr/bin/env python3
"""
Build the browser version of Tour De Force: Interdiction Force.

Inlines web_curses.py (the in-browser curses shim), every tdfif/*.py
module (untouched), and web_bridge.py (glue) into template.html. Unlike
TDF's single-file game, TDFIF is a real package with relative imports
between its modules, so each one gets its own placeholder/script tag
instead of being merged into one blob - the boot script in template.html
writes them out as real files in Pyodide's virtual filesystem and does a
genuine `import tdfif.app`, so the relative imports resolve normally.

Re-run after changing any tdfif/*.py file, web_curses.py, or
web_bridge.py:

    python3 -m py_compile tdfif/*.py web_curses.py web_bridge.py
    python3 build_web.py
"""

import os

TDFIF_MODULES = [
    ("__PY_TDFIF_INIT__", "__init__.py"),
    ("__PY_TDFIF_CONSTANTS__", "constants.py"),
    ("__PY_TDFIF_MAPGEN__", "mapgen.py"),
    ("__PY_TDFIF_PARTY__", "party.py"),
    ("__PY_TDFIF_ENEMIES__", "enemies.py"),
    ("__PY_TDFIF_BATTLE__", "battle.py"),
    ("__PY_TDFIF_UI__", "ui.py"),
    ("__PY_TDFIF_BATTLE_UI__", "battle_ui.py"),
    ("__PY_TDFIF_OVERWORLD__", "overworld.py"),
    ("__PY_TDFIF_APP__", "app.py"),
]


def main():
    curses_shim = open("web_curses.py").read()
    bridge = open("web_bridge.py").read()
    modules = [(placeholder, filename, open(os.path.join("tdfif", filename)).read())
               for placeholder, filename in TDFIF_MODULES]

    blobs = [(curses_shim, "web_curses.py"), (bridge, "web_bridge.py")]
    blobs += [(src, f"tdfif/{filename}") for _, filename, src in modules]
    for blob, name in blobs:
        if "</script" in blob:
            raise SystemExit(f"{name} contains '</script', which would break inlining")

    html = open("template.html").read()
    html = (html
            .replace("__PY_CURSES__", curses_shim)
            .replace("__PY_BRIDGE__", bridge))
    for placeholder, _, src in modules:
        html = html.replace(placeholder, src)

    with open("index.html", "w") as f:
        f.write(html)
    sizes = ", ".join(f"{name} {len(blob):,}" for blob, name in blobs)
    print(f"index.html written ({len(html):,} bytes; {sizes})")


if __name__ == "__main__":
    main()
