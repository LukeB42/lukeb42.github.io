#!/usr/bin/env python3
"""Entry point for TOUR DE FORCE: INTERDICTION FORCE."""

import curses

from tdfif.app import main

if __name__ == "__main__":
    curses.wrapper(main)
