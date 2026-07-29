#!/usr/bin/env python3
"""
Build the browser version of SOLVENT.

Reads solvent.py (single source of truth for game logic) and web_api.py,
inlines them into template.html, writes index.html. Re-run after any
balance change:

    python3 solvent.py --selftest && python3 build_web.py
"""

UI_MARKER = ("# ----------------------------------------------------------------------------\n"
             "# CURSES UI")

def main():
    solvent = open("solvent.py").read()
    logic = solvent.split(UI_MARKER)[0]
    api = open("web_api.py").read()
    for blob, name in ((logic, "solvent.py"), (api, "web_api.py")):
        if "</script" in blob:
            raise SystemExit(f"{name} contains '</script', which would break inlining")
    html = open("template.html").read()
    html = html.replace("__PY_LOGIC__", logic).replace("__PY_API__", api)
    with open("index.html", "w") as f:
        f.write(html)
    print(f"index.html written ({len(html):,} bytes; "
          f"logic {len(logic):,}, api {len(api):,})")

if __name__ == "__main__":
    main()
