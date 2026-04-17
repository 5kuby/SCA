#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
from UTIL.menu_helper import menu_caller

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
            print("\nSelect SNS action (single key): ", end='', flush=True)
            choice = getch()

            if choice == "1":
                # Launch SNS menu
                menu_caller("sns")
                sys.exit(0)
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
