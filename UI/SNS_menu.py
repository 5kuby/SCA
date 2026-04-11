#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SNS menu aggiornato

Mostra l'opzione Backup / Restore solo se:
 - esiste un workspace attivo (file tmp/active_workspace.json),
 - e c'è almeno una sessione attiva (SNS_conn.tmp o memory_helper).

Il resto del menu mantiene le funzionalità esistenti.
"""

import sys
import os
from getpass import getpass
from typing import Optional

# CROSS-PLATFORM SINGLE KEY INPUT
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

# Helpers
try:
    from UTIL import memory_helper
except Exception:
    memory_helper = None

try:
    from UTIL import workspace_helper
except Exception:
    workspace_helper = None

try:
    from UTIL import SNS_connection
except Exception:
    SNS_connection = None

# utilities to inspect SNS_conn.tmp
try:
    from UTIL import sns_utils
except Exception:
    sns_utils = None

# Import backup/restore helper
try:
    from UTIL import sns_backup_restore
except Exception:
    sns_backup_restore = None

# For SNS connection actions used elsewhere
try:
    from UTIL.SNS_connection import SNS_connection as SNS_conn_func
except Exception:
    SNS_conn_func = None

LAST_SNS_PARAMS = {}

def _has_active_workspace() -> bool:
    """
    Ritorna True se esiste un workspace attivo (file tmp/active_workspace.json).
    Usa workspace_helper.get_current_workspace() che preferisce il file tmp.
    """
    try:
        if workspace_helper is None:
            return False
        resp = workspace_helper.get_current_workspace()
        if resp.get("status") != "ok":
            return False
        return bool(resp.get("result"))
    except Exception:
        return False

def _has_any_session() -> bool:
    """
    Ritorna True se esiste almeno una sessione attiva.
    Controlla prima tmp/SNS_conn.tmp (preferito), poi memory_helper come fallback.
    """
    try:
        # preferiamo leggere il file tmp/SNS_conn.tmp
        if sns_utils is not None:
            lines = sns_utils._read_tmp_file_lines()
            if lines:
                return True
        # fallback: memory_helper
        if memory_helper is not None and hasattr(memory_helper, "get_all_sessions"):
            all_sess = memory_helper.get_all_sessions()
            if isinstance(all_sess, dict) and len(all_sess) > 0:
                return True
    except Exception:
        pass
    return False

def sns_management():
    while True:
        clear_screen()
        print("=== SNS MANAGEMENT ===")
        print("1) OPEN SNS CONNECTION")
        print("2) LIST ACTIVE CONNECTIONS")
        print("3) CLI")

        # Show Backup/Restore only if both a workspace is active and at least one session exists
        show_backup = False
        try:
            if _has_active_workspace() and _has_any_session():
                show_backup = True
        except Exception:
            show_backup = False

        if show_backup:
            print("4) BACKUP / RESTORE")
        print("b) Back")
        print("B) Back to MAIN MENU")

        print("\nSelect SNS action (single key): ", end='', flush=True)
        choice = getch()

        if choice == '1':
            sns_open_connection()
        elif choice == '2':
            sns_list_connections()
        elif choice == '3':
            sns_cli()
        elif choice == '4' and show_backup:
            sns_backup_menu()
        elif choice == 'b':
            return
        elif choice == 'B':
            sys.stdout.flush()
            clear_screen()
            try:
                from UTIL.menu_helper import menu_caller
                menu_caller("main")
            except Exception:
                pass
            return
        else:
            continue

def sns_open_connection():
    while True:
        clear_screen()
        print("=== OPEN SNS CONNECTION ===")
        print("1) MANUAL CONNECTION")
        print("2) OPEN SAVED ENTRY")
        print("b) Back")
        print("B) Back to MAIN MENU")

        print("\nSelect option (single key): ", end='', flush=True)
        choice = getch()

        if choice == '1':
            sns_manual_connection()
        elif choice == '2':
            sns_open_saved_entry()
        elif choice == 'b':
            return
        elif choice == 'B':
            sys.stdout.flush()
            clear_screen()
            try:
                from UTIL.menu_helper import menu_caller
                menu_caller("main")
            except Exception:
                pass
            return
        else:
            continue

def sns_manual_connection():
    clear_screen()
    print("=== MANUAL SNS CONNECTION ===")

    firewall_ip = input("Firewall IP address > ").strip()

    port_input = input("Firewall port [default 443] > ").strip()
    if port_input == "":
        firewall_port = 443
    else:
        try:
            firewall_port = int(port_input)
        except ValueError:
            firewall_port = 443

    username = input("Username > ").strip()
    password = input("Password > ").strip()

    try:
        from UTIL.SNS_connection import SNS_connection
    except Exception:
        print("SNS_connection module not available.")
        wait_key()
        return

    result = SNS_connection("open", firewall_ip, firewall_port, username, password)

    if result == 0:
        print("\nConnection established successfully.")
        global LAST_SNS_PARAMS
        LAST_SNS_PARAMS = {
            "ip": firewall_ip,
            "port": firewall_port,
            "username": username,
            "password": password
        }
    else:
        print("\nConnection failed.")

    wait_key("\nPress any key to return to SNS MANAGEMENT...")
    return

def sns_open_saved_entry():
    clear_screen()
    print("=== OPEN SAVED ENTRY ===")

    try:
        from UTIL.vault_helper import vault_manager
    except Exception as e:
        print(f"Vault manager not available: {e}")
        wait_key()
        return

    resp = vault_manager("list")
    if resp.get("status") != "ok":
        print("Error listing vaults:", resp.get("message"))
        wait_key()
        return

    vaults = resp.get("result", [])
    if not vaults:
        print("No vaults available.")
        wait_key()
        return

    print("\nAvailable vaults:")
    for i, v in enumerate(vaults, start=1):
        print(f"{i}) {v}")

    selection = input("\nSelect a vault by number: ").strip()
    if not selection.isdigit():
        print("Invalid selection.")
        wait_key()
        return

    index = int(selection)
    if index < 1 or index > len(vaults):
        print("Invalid selection.")
        wait_key()
        return

    vault_name = vaults[index - 1]
    password = getpass("Vault password: ")

    resp = vault_manager("open", vault_name=vault_name, password=password)
    if resp.get("status") != "ok":
        print("Error opening vault:", resp.get("message"))
        wait_key()
        return

    resp = vault_manager("l_entries")
    if resp.get("status") != "ok":
        print("Error reading entries:", resp.get("message"))
        wait_key()
        return

    print("\nEntries in vault:")
    print(resp.get("result"))

    entry_index = input("\nSelect entry index: ").strip()
    if not entry_index.isdigit():
        print("Invalid index.")
        wait_key()
        return

    try:
        resp_get = vault_manager("read", arg1=entry_index)
    except Exception as e:
        resp_get = {"status": "error", "message": str(e)}

    entry = None
    if resp_get.get("status") == "ok":
        entry = resp_get.get("result")
    else:
        # fallback parsing (if needed)
        table_text = resp.get("result") if resp.get("result") else ""
        for ln in table_text.splitlines():
            if ln.strip().startswith(entry_index + " "):
                parts = ln.split()
                if len(parts) >= 6:
                    entry = {
                        "ip": parts[2],
                        "port": parts[3],
                        "username": parts[4],
                        "password": parts[5]
                    }
                    break

    if entry is None:
        print("\nError retrieving entry:", resp_get.get("message", "Unknown error"))
        wait_key()
        return

    ip = entry.get("ip")
    try:
        port = int(entry.get("port"))
    except Exception:
        port = 443
    username = entry.get("username")
    password = entry.get("password")

    try:
        from UTIL.SNS_connection import SNS_connection
    except Exception:
        print("SNS_connection not available.")
        wait_key()
        return

    result = SNS_connection("open", ip, port, username, password)

    if result == 0:
        print("\nConnection established successfully.")
        global LAST_SNS_PARAMS
        LAST_SNS_PARAMS = {
            "ip": ip,
            "port": port,
            "username": username,
            "password": password
        }
    else:
        print("\nConnection failed.")

    wait_key("\nPress any key to return to SNS MANAGEMENT...")
    return

def sns_list_connections():
    clear_screen()
    try:
        from UTIL.SNS_connection import SNS_connection
    except Exception:
        print("SNS_connection not available.")
        wait_key()
        return

    try:
        SNS_connection("list", None, None, None, None)
    except Exception:
        pass

    wait_key("\nPress any key to return to SNS MANAGEMENT...")
    return

def sns_cli():
    clear_screen()
    try:
        from UTIL.sns_cli import main as sns_cli_main
    except Exception:
        print("sns_cli module not available.")
        wait_key()
        return

    try:
        sns_cli_main()
    except Exception:
        pass

    wait_key("\nPress any key to return to SNS MANAGEMENT...")
    return

def sns_backup_menu():
    """
    Menu semplice per backup/restore. Richiede sessione e workspace attivi.
    """
    while True:
        clear_screen()
        print("=== SNS BACKUP / RESTORE ===")
        print("1) Backup")
        print("2) Restore")
        print("b) Back")

        print("\nSelect option (single key): ", end='', flush=True)
        choice = getch()

        if choice == '1':
            # call backup helper
            if sns_backup_restore is None:
                print("Backup helper non disponibile.")
                wait_key()
                continue
            sns_backup_restore.backup()
            wait_key()
        elif choice == '2':
            if sns_backup_restore is None:
                print("Backup helper non disponibile.")
                wait_key()
                continue
            sns_backup_restore.restore()
            wait_key()
        elif choice.lower() == 'b':
            return
        else:
            continue
