#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wizard_menu.py

Simple menu to choose which wizard to run.

Options:
  1) Base config   -> calls QuickConfig("Base")
  2) Back to MAIN  -> returns to main menu via menu_helper.menu_caller("main")

This module performs imports lazily inside functions to avoid circular imports.
"""

from __future__ import annotations

import sys
from typing import Any, Optional


def wizard_menu() -> Optional[Any]:
    """
    Display a small menu to the user and dispatch the chosen action.

    Returns the value returned by the invoked menu (if any), or None.
    """
    while True:
        print("")
        print("Select wizard to run:")
        print("1) Base config")
        print("2) Back to MAIN")
        choice = input("Enter choice [1-2]: ").strip().lower()

        if choice in ("1", "1)", "base", "base config", "base_config"):
            # Import QuickConfig lazily to avoid import-time cycles
            try:
                from UTIL.quick_config_wizard import QuickConfig  # type: ignore
            except Exception as e:
                print(f"[wizard_menu] Unable to import QuickConfig: {e}")
                return None

            try:
                # Call QuickConfig with the base name "Base"
                QuickConfig("Base")
            except Exception as e:
                print(f"[wizard_menu] QuickConfig raised an exception: {e}")
            # After running the wizard, return to caller (menu_helper or caller loop)
            return None

        elif choice in ("2", "2)", "back", "main", "back to main"):
            # Return to main menu by calling menu_helper.menu_caller("main")
            try:
                # Import locally to avoid circular import at module load time
                from menu_helper import menu_caller  # type: ignore
            except Exception as e:
                print(f"[wizard_menu] Unable to import menu_helper: {e}")
                return None

            try:
                return menu_caller("main")
            except Exception as e:
                print(f"[wizard_menu] Error while returning to main menu: {e}")
                return None

        else:
            print("Invalid choice. Please enter 1 or 2.")
