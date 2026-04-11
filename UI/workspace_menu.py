#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive workspace menu.
Navigation harmonized with other UI menus:
 - 'b' : back to previous menu
 - 'B' : back to MAIN MENU (via menu_caller)
"""

import os
import sys
from getpass import getpass

from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from UTIL.menu_helper import menu_caller
except Exception:
    menu_caller = None

try:
    from UTIL.workspace_helper import (
        init_store, list_workspaces, create_workspace, get_workspace,
        delete_workspace, activate_workspace, deactivate_workspace,
        get_current_workspace, update_workspace, create_and_activate,
        ensure_workspace_dirs_exist, resolve_workspace_dir
    )
except Exception:
    init_store = list_workspaces = create_workspace = get_workspace = delete_workspace = None
    activate_workspace = deactivate_workspace = get_current_workspace = update_workspace = None
    create_and_activate = ensure_workspace_dirs_exist = resolve_workspace_dir = None

# cross-platform single key
try:
    import msvcrt
    def getch():
        return msvcrt.getch().decode('utf-8', errors='ignore')
except Exception:
    import tty, termios
    def getch():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def wait_key(prompt="Press any key to continue..."):
    print(prompt, end='', flush=True)
    getch()
    print()

def workspace_menu():
    try:
        if init_store is not None:
            init_store()
    except Exception:
        pass

    while True:
        clear_screen()
        print("=== WORKSPACES ===")
        print("1) List workspaces")
        print("2) Create workspace")
        print("3) Edit workspace")
        print("4) Activate workspace")
        print("5) Deactivate workspace")
        print("6) Delete workspace")
        print("7) Show current workspace")
        print("8) Ensure workspace directories exist")
        print("b) Back")
        print("B) Back to MAIN MENU")

        print("\nSelect option (single key): ", end='', flush=True)
        choice = getch()

        if choice == '1':
            clear_screen()
            if list_workspaces is None:
                print("Workspace helper not available.")
            else:
                resp = list_workspaces()
                if resp.get("status") == "ok":
                    names = resp.get("result", [])
                    if not names:
                        print("No workspaces defined.")
                    else:
                        print("Workspaces:")
                        for n in names:
                            print(" -", n)
                else:
                    print("Error:", resp.get("message"))
            wait_key()

        elif choice == '2':
            clear_screen()
            if create_workspace is None:
                print("Workspace helper not available.")
                wait_key()
                continue
            name = input("Workspace name > ").strip()
            desc = input("Description (optional) > ").strip()
            resp = create_workspace(name, desc)
            if resp.get("status") == "ok":
                print("Workspace created.")
                if resp.get("warning"):
                    print("Warning:", resp.get("warning"))
            else:
                print("Error:", resp.get("message"))
            wait_key()

        elif choice == '3':
            clear_screen()
            if update_workspace is None:
                print("Workspace helper not available.")
                wait_key()
                continue
            resp = list_workspaces()
            if resp.get("status") != "ok":
                print("Error:", resp.get("message"))
                wait_key()
                continue
            names = resp.get("result", [])
            if not names:
                print("No workspaces to edit.")
                wait_key()
                continue
            print("Workspaces:")
            for i, n in enumerate(names, start=1):
                print(f"{i}) {n}")
            sel = input("\nSelect workspace by number or name: ").strip()
            if sel.isdigit():
                idx = int(sel)
                if idx < 1 or idx > len(names):
                    print("Invalid selection.")
                    wait_key()
                    continue
                name = names[idx-1]
            else:
                name = sel
            g = get_workspace(name)
            if g.get("status") != "ok":
                print("Error:", g.get("message"))
                wait_key()
                continue
            ws = g.get("result")
            print("Current description:", ws.get("description",""))
            new_desc = input("New description (leave empty to keep) > ").strip()
            resp_upd = update_workspace(name, description=new_desc if new_desc else None)
            if resp_upd.get("status") == "ok":
                print("Workspace updated.")
            else:
                print("Error:", resp_upd.get("message"))
            wait_key()

        elif choice == '4':
            clear_screen()
            if activate_workspace is None:
                print("Workspace helper not available.")
                wait_key()
                continue
            resp = list_workspaces()
            if resp.get("status") != "ok":
                print("Error:", resp.get("message"))
                wait_key()
                continue
            names = resp.get("result", [])
            if not names:
                print("No workspaces to activate.")
                wait_key()
                continue
            print("Workspaces:")
            for i, n in enumerate(names, start=1):
                print(f"{i}) {n}")
            sel = input("\nSelect workspace by number or name: ").strip()
            if sel.isdigit():
                idx = int(sel)
                if idx < 1 or idx > len(names):
                    print("Invalid selection.")
                    wait_key()
                    continue
                name = names[idx-1]
            else:
                name = sel
            create_choice = input("Create missing workspace directories if needed? (Y/n) > ").strip().lower()
            create_dirs = create_choice in ("", "y", "yes")
            resp_act = activate_workspace(name, create_dirs=create_dirs)
            if resp_act.get("status") == "ok":
                print("Workspace activated.")
                res = resp_act.get("result", {})
                print("Workspace directory:", res.get("workspace_directory"))
                print("Backup directory:", res.get("backup_directory"))
                if res.get("failed"):
                    print("Failed to create some directories:")
                    for f in res.get("failed", []):
                        print(" -", f)
            else:
                print("Error:", resp_act.get("message"))
            wait_key()

        elif choice == '5':
            clear_screen()
            if deactivate_workspace is None:
                print("Workspace helper not available.")
                wait_key()
                continue
            resp = deactivate_workspace()
            if resp.get("status") == "ok":
                print("Workspace deactivated.")
            else:
                print("Error:", resp.get("message"))
            wait_key()

        elif choice == '6':
            clear_screen()
            if delete_workspace is None:
                print("Workspace helper not available.")
                wait_key()
                continue
            resp = list_workspaces()
            if resp.get("status") != "ok":
                print("Error:", resp.get("message"))
                wait_key()
                continue
            names = resp.get("result", [])
            if not names:
                print("No workspaces to delete.")
                wait_key()
                continue
            for i, n in enumerate(names, start=1):
                print(f"{i}) {n}")
            sel = input("\nSelect workspace by number or name to delete: ").strip()
            if sel.isdigit():
                idx = int(sel)
                if idx < 1 or idx > len(names):
                    print("Invalid selection.")
                    wait_key()
                    continue
                name = names[idx-1]
            else:
                name = sel
            confirm = input(f"Confirm delete workspace '{name}'? (type YES to confirm) > ").strip()
            if confirm == "YES":
                resp_del = delete_workspace(name)
                if resp_del.get("status") == "ok":
                    print("Workspace deleted.")
                else:
                    print("Error:", resp_del.get("message"))
            else:
                print("Aborted.")
            wait_key()

        elif choice == '7':
            clear_screen()
            if get_current_workspace is None:
                print("Workspace helper not available.")
                wait_key()
                continue
            resp = get_current_workspace()
            if resp.get("status") != "ok":
                print("Error:", resp.get("message"))
            else:
                cur = resp.get("result")
                if not cur:
                    print("No active workspace.")
                else:
                    print("Active workspace:", cur.get("name"))
                    print("Workspace directory:", cur.get("workspace_directory"))
                    print("Backup directory:", cur.get("backup_directory"))
                    print("Last activated:", cur.get("last_activated"))
            wait_key()

        elif choice == '8':
            clear_screen()
            if ensure_workspace_dirs_exist is None:
                print("Workspace helper not available.")
                wait_key()
                continue
            resp = list_workspaces()
            if resp.get("status") != "ok":
                print("Error:", resp.get("message"))
                wait_key()
                continue
            names = resp.get("result", [])
            if not names:
                print("No workspaces.")
                wait_key()
                continue
            for i, n in enumerate(names, start=1):
                print(f"{i}) {n}")
            sel = input("\nSelect workspace by number or name: ").strip()
            if sel.isdigit():
                idx = int(sel)
                if idx < 1 or idx > len(names):
                    print("Invalid selection.")
                    wait_key()
                    continue
                name = names[idx-1]
            else:
                name = sel
            resp_ok = ensure_workspace_dirs_exist(name)
            if resp_ok.get("status") == "ok":
                res = resp_ok.get("result", {})
                print("Created:")
                for p in res.get("created", []):
                    print(" -", p)
                if res.get("failed"):
                    print("Failed:")
                    for f in res.get("failed", []):
                        print(" -", f)
            else:
                print("Error:", resp_ok.get("message"))
            wait_key()

        elif choice.lower() == 'b':
            return

        elif choice == 'B':
            if menu_caller is not None:
                try:
                    menu_caller("main")
                except Exception:
                    pass
            return

        else:
            continue
