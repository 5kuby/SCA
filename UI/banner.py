#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from colorama import init as colorama_init, Fore, Style

colorama_init(autoreset=True)

BANNER = r"""
 ____   _                                _      _        _      _ 
/ ___| | |_  ___   _ __  _ __ ___   ___ | |__  (_)  ___ | |  __| |
\___ \ | __|/ _ \ | '__|| '_ ` _ \ / __|| '_ \ | | / _ \| | / _` |
 ___) || |_| (_) || |   | | | | | |\__ \| | | || ||  __/| || (_| |
|____/  \__|\___/ |_| __|_| |_| |_||___/|_| |_||_| \___||_| \__,_|
 / ___| ___   _ __   / _|(_)  __ _                                
| |    / _ \ | '_ \ | |_ | | / _` |                               
| |___| (_) || | | ||  _|| || (_| |                               
 \____|\___/ |_| |_||_|  |_|_\__, |           _                   
   / \    ___  ___ (_) ___ | |___/_ _  _ __  | |_                 
  / _ \  / __|/ __|| |/ __|| __|/ _` || '_ \ | __|                
 / ___ \ \__ \\__ \| |\__ \| |_| (_| || | | || |_                 
/_/   \_\|___/|___/|_||___/ \__|\__,_||_| |_| \__|                
"""

DISCLAIMER = (
    "IMPORTANT NOTICE:\n"
    "This is NOT an official Stormshield tool or product.\n"
    "It is provided by a third party and is released under the GNU General Public License (GPL).\n"
    "Use at your own risk. No warranty is provided.\n"
)

def clear_screen():
    os.system("clear" if os.name == "posix" else "cls")

def _win_wait_key(prompt):
    import msvcrt
    print(Fore.CYAN + prompt + Style.RESET_ALL, end="", flush=True)
    try:
        msvcrt.getch()
    except Exception:
        pass
    print()
    return True

def _posix_wait_key_tty(prompt):
    import tty, termios
    try:
        fd = os.open('/dev/tty', os.O_RDONLY)
    except OSError:
        fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        print(Fore.CYAN + prompt + Style.RESET_ALL, end="", flush=True)
        tty.setraw(fd)
        os.read(fd, 1)
        print()
        return True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if fd != sys.stdin.fileno():
            os.close(fd)

def _is_interactive():
    return sys.stdout.isatty() and (sys.stdin.isatty() or os.path.exists('/dev/tty'))

def _wait_for_keypress(prompt="Press any key to confirm and continue...", debug=False):
    """
    Wait for a single keypress. Uses /dev/tty on POSIX to be robust against stdin redirection.
    Auto-confirms in non-interactive environments.
    """
    if not _is_interactive():
        if debug:
            print(Fore.MAGENTA + "[debug] Non-interactive: auto-confirming" + Style.RESET_ALL)
        return True
    try:
        if os.name == "nt":
            return _win_wait_key(prompt)
        else:
            return _posix_wait_key_tty(prompt)
    except Exception:
        try:
            input(Fore.CYAN + prompt + Style.RESET_ALL)
            return True
        except Exception:
            return False

def show_banner(skip_confirm=False, debug=False):
    """
    Show ASCII art and the disclaimer (disclaimer printed below the art),
    then wait for a single keypress (unless skip_confirm=True).
    This is the single function to call from your main or run as a script.
    """
    clear_screen()
    # ASCII art first
    print(Fore.BLUE + BANNER + Style.RESET_ALL)
    # disclaimer directly below
    print(Fore.YELLOW + DISCLAIMER + Style.RESET_ALL)
    # optional confirmation
    if not skip_confirm:
        ok = _wait_for_keypress(debug=debug)
        if not ok:
            print(Fore.RED + "Confirmation not received. Exiting." + Style.RESET_ALL)
            return 1
    # title line after confirmation for clarity
    print(Fore.GREEN + "SCA - Stormshield CLI Assistant\n" + Fore.RESET)
    return 0

if __name__ == "__main__":
    skip = "--no-confirm" in sys.argv[1:]
    debug = "--debug" in sys.argv[1:]
    rc = show_banner(skip_confirm=skip, debug=debug)
    sys.exit(rc)
