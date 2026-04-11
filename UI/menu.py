#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from UTIL.menu_helper import menu_caller

def main_menu():
    """
    Main menu loop. Calls submenus via menu_caller.
    Keeps running until the user chooses to exit.
    """
    while True:
        try:
            print("=== MAIN MENU ===")
            print("1) SNS")
            print("2) Vault")
            print("3) Workspaces")
            print("4) Quick Config Wizard")
            print("q) Quit")
            choice = input("\nSelect option > ").strip().lower()

            if choice == "1":
                # Launch SNS menu
                menu_caller("sns")
            elif choice == "2":
                # Launch Vault menu
                menu_caller("vault")
            elif choice == "3":
                # Launch Workspace menu
                menu_caller("workspace")
            elif choice == "4":
                # Launch Quick Config Wizard
                menu_caller("quick config wizard")
            elif choice == "q":
                print("Exiting...")
                return 0
            else:
                print("Invalid selection.")
        except KeyboardInterrupt:
            print("\nInterrupted. Exiting...")
            return 0
        except Exception as e:
            # Do not exit the whole program on submenu errors; show message and continue.
            print(f"[main_menu] Error while handling selection: {e}")
            try:
                from UTIL.log_helper import log_writer
                log_writer(f"main_menu error: {e}")
            except Exception:
                pass
            # Continue loop
