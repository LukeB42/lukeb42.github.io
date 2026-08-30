#!/usr/bin/env python3
"""
Build the browser version of L.E.E.T.

Inlines web_curses.py (the in-browser curses shim), leet.py itself
(untouched), and web_bridge.py (glue) into template.html. Re-run after
changing any of those files:

    python3 -m py_compile leet.py web_curses.py web_bridge.py
    python3 build_web.py
"""


def main():
    curses_shim = open("web_curses.py").read()
    game = open("leet.py").read()
    bridge = open("web_bridge.py").read()

    blobs = (
        (curses_shim, "web_curses.py"),
        (game, "leet.py"),
        (bridge, "web_bridge.py"),
    )
    for blob, name in blobs:
        if "</script" in blob:
            raise SystemExit(f"{name} contains '</script', which would break inlining")

    html = open("template.html").read()
    html = (html
            .replace("__PY_CURSES__", curses_shim)
            .replace("__PY_LEET__", game)
            .replace("__PY_BRIDGE__", bridge))
    with open("index.html", "w") as f:
        f.write(html)
    sizes = ", ".join(f"{name} {len(blob):,}" for blob, name in blobs)
    print(f"index.html written ({len(html):,} bytes; {sizes})")


if __name__ == "__main__":
    main()
