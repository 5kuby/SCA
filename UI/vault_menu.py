#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vault_menu.py

Updated to work with the new vault_helper + memory_helper architecture.
Harmonized navigation with SNS menu: 'b' returns to previous menu, 'B' returns to MAIN MENU.
"""

from getpass import getpass
from typing import List, Tuple
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent
_project_root_str = str(_project_root)
if _project_root_str not in sys.path:
    sys.path.insert(0, _project_root_str)

# Import vault_manager
try:
    from UTIL.vault_helper import vault_manager
except Exception:
    vault_manager = None

# Import memory_helper
try:
    from UTIL import memory_helper
except Exception:
    memory_helper = None

# Import menu dispatcher
try:
    from UTIL.menu_helper import menu_caller
except Exception:
    menu_caller = None

# Optional direct main_menu fallback (kept for compatibility)
try:
    from UI.menu import main_menu
except Exception:
    try:
        from .menu import main_menu
    except Exception:
        main_menu = None


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def _vault_is_open() -> bool:
    """
    A vault is considered open if memory_helper contains at least one entry.
    """
    if memory_helper is None:
        return False

    try:
        store = memory_helper.get_all()
        return len(store) > 0
    except Exception:
        return False


def _get_open_vault_path() -> str:
    """
    Returns the path of the currently opened vault.
    """
    if memory_helper is None:
        return ""

    try:
        store = memory_helper.get_all()
        if not store:
            return ""
        return list(store.keys())[0]
    except Exception:
        return ""


def _print_table(rows: List[Tuple[str, str]]) -> None:
    """
    Print a simple two-column table.
    """
    if not rows:
        return
    width = max(len(r[0]) for r in rows) + 4
    for left, right in rows:
        print(f"{left:<{width}}{right}")


def vault_menu() -> None:
    """
    Main vault menu.
    Navigation:
      - 'b' : Back (return to previous menu)
      - 'B' : Back to MAIN MENU (via menu_caller)
    """
    while True:
        clear_screen()
        print("=== VAULT MENU ===")
        print("1) List vaults")
        print("2) Open vault")
        print("3) List entries (l_entries)")

        if _vault_is_open():
            print("4) Add entry")
            print("5) Delete entry")
            print("6) Save vault")
            print("7) Close vault")

        print("b) Back")
        print("B) Back to MAIN MENU")

        choice = input("Select an option: ").strip()

        # ---------------------------------------------------------
        # b) Back to previous menu
        # ---------------------------------------------------------
        if choice.lower() == "b":
            # Prefer dispatcher if available, otherwise call main_menu if present
            if main_menu is not None:
                try:
                    return main_menu()
                except Exception:
                    return None
            if menu_caller is not None:
                try:
                    return menu_caller("main")
                except Exception:
                    return None
            return None

        # ---------------------------------------------------------
        # B) Back to MAIN MENU via dispatcher
        # ---------------------------------------------------------
        if choice == "B":
            if menu_caller is not None:
                try:
                    menu_caller("main")
                except Exception:
                    pass
            return

        # ---------------------------------------------------------
        # 1) List vaults
        # ---------------------------------------------------------
        if choice == "1":
            clear_screen()
            if vault_manager is None:
                print("Vault manager not available.")
            else:
                resp = vault_manager("list")
                if resp.get("status") == "ok":
                    print("Available vaults:")
                    for v in resp.get("result", []):
                        print(" -", v)
                else:
                    print("Error:", resp.get("message"))
            input("\nPress Enter to continue...")

        # ---------------------------------------------------------
        # 2) Open vault (improved: list + numeric selection)
        # ---------------------------------------------------------
        elif choice == "2":
            clear_screen()
            if vault_manager is None:
                print("Vault manager not available.")
                input("\nPress Enter to continue...")
                continue

            resp = vault_manager("list")
            if resp.get("status") != "ok":
                print("Error:", resp.get("message"))
                input("\nPress Enter to continue...")
                continue

            vaults = resp.get("result", [])
            if not vaults:
                print("No vaults found.")
                input("\nPress Enter to continue...")
                continue

            print("Available vaults:")
            for i, v in enumerate(vaults, start=1):
                print(f"{i}) {v}")

            selection = input("\nSelect a vault by number: ").strip()
            if not selection.isdigit():
                print("Invalid selection.")
                input("\nPress Enter to continue...")
                continue

            index = int(selection)
            if index < 1 or index > len(vaults):
                print("Invalid selection.")
                input("\nPress Enter to continue...")
                continue

            vault_name = vaults[index - 1]
            password = getpass("Password: ")

            resp = vault_manager("open", vault_name=vault_name, password=password)
            if resp.get("status") == "ok":
                print(f"Vault '{vault_name}' opened successfully.")
            else:
                print("Error:", resp.get("message"))

            input("\nPress Enter to continue...")

        # ---------------------------------------------------------
        # 3) List entries
        # ---------------------------------------------------------
        elif choice == "3":
            clear_screen()
            if vault_manager is None:
                print("Vault manager not available.")
            else:
                resp = vault_manager("l_entries")
                if resp.get("status") == "ok":
                    print(resp.get("result"))
                else:
                    print("Error:", resp.get("message"))
            input("\nPress Enter to continue...")

        # ---------------------------------------------------------
        # 4) Add entry
        # ---------------------------------------------------------
        elif choice == "4" and _vault_is_open():
            clear_screen()
            if vault_manager is None:
                print("Vault manager not available.")
                input("\nPress Enter to continue...")
                continue

            name = input("Name: ").strip()
            host = input("Host: ").strip()
            port = input("Port: ").strip()
            username = input("Username: ").strip()
            password = getpass("Password: ")

            # Use new API: arg1 = entry_name, arg2 = dict
            resp = vault_manager("add_entry",
                                 arg1=name,
                                 arg2={
                                     "host": host,
                                     "port": port,
                                     "username": username,
                                     "password": password
                                 })

            if resp.get("status") == "ok":
                print("Entry added.")
            else:
                print("Error:", resp.get("message"))

            input("\nPress Enter to continue...")

        # ---------------------------------------------------------
        # 5) Delete entry
        # ---------------------------------------------------------
        elif choice == "5" and _vault_is_open():
            clear_screen()
            if vault_manager is None:
                print("Vault manager not available.")
                input("\nPress Enter to continue...")
                continue

            index = input("Index to delete: ").strip()
            resp = vault_manager("delete_entry", arg1=index)
            if resp.get("status") == "ok":
                print("Entry deleted.")
            else:
                print("Error:", resp.get("message"))
            input("\nPress Enter to continue...")

        # ---------------------------------------------------------
        # 6) Save vault
        # ---------------------------------------------------------
        elif choice == "6" and _vault_is_open():
            clear_screen()
            if vault_manager is None:
                print("Vault manager not available.")
            else:
                resp = vault_manager("save")
                if resp.get("status") == "ok":
                    print("Vault saved.")
                else:
                    print("Error:", resp.get("message"))
            input("\nPress Enter to continue...")

        # ---------------------------------------------------------
        # 7) Close vault
        # ---------------------------------------------------------
        elif choice == "7" and _vault_is_open():
            clear_screen()
            vault_path = _get_open_vault_path()
            try:
                if memory_helper:
                    # If memory_helper supports deletion, prefer it; otherwise set to None
                    if hasattr(memory_helper, "delete"):
                        memory_helper.delete(vault_path)
                    else:
                        memory_helper.set(vault_path, None)
            except Exception:
                pass

            print("Vault closed.")
            input("\nPress Enter to continue...")

        else:
            clear_screen()
            print("Invalid option.")
            input("\nPress Enter to continue...")
