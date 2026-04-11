"""
runtimemessages.py

Loads runtime messages from ../ConfigFiles/messages.ini
and exposes messages_helper() to print them with the correct
color and prefix based on the numeric range.

Also writes the same (color-stripped) message to the log via
UTIL/log_helper.log_writer(message).
"""

import configparser
import os
import re
from typing import Dict, Tuple, Optional

from colorama import init as colorama_init, Fore, Style

# Import the existing log_writer function (already implemented)
from UTIL.log_helper import log_writer

# Initialize colorama for cross-platform ANSI support
colorama_init(autoreset=True)

# Colorama color constants
CYAN = Fore.CYAN
ORANGE = Fore.YELLOW
RED = Fore.RED
RESET = Style.RESET_ALL


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences so logs contain plain text."""
    ansi_re = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    return ansi_re.sub("", text)


def _resolve_style(code: int) -> Tuple[str, str]:
    """Determines the color and prefix based on the numeric range."""
    if 0 <= code <= 999:
        return CYAN, "INFO"
    elif 1000 <= code <= 1999:
        return ORANGE, "WARN"
    elif 2000 <= code <= 2999:
        return RED, "ERR"
    else:
        return CYAN, "INFO"  # fallback


def _load_messages() -> Dict[int, str]:
    """
    Loads messages from ../ConfigFiles/messages.ini.

    Assumes project structure:
    project_root/
    ├─ ConfigFiles/messages.ini
    └─ UI/runtimemessages.py  <-- this file
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    config_path = os.path.join(base_dir, "ConfigFiles", "messages.ini")

    parser = configparser.ConfigParser()
    read_files = parser.read(config_path, encoding="utf-8")

    messages: Dict[int, str] = {}

    if not read_files:
        return messages

    if "Messages" in parser:
        for key, value in parser["Messages"].items():
            try:
                code = int(key)
                messages[code] = value.strip()
            except ValueError:
                continue

    return messages


MESSAGES = _load_messages()


def _print_message(code: int, text: str) -> None:
    """Prints a message with the correct color and prefix and logs it."""
    color, prefix = _resolve_style(code)
    formatted = f"{color}[{prefix}] {text}{RESET}"
    print(formatted)

    # Log plain-text message (strip ANSI)
    plain = f"[{prefix}] {text}"
    log_writer(plain)


def messages_helper(code, debug: bool = False) -> None:
    """
    Prints a message based on the provided code.
    Accepts int or numeric string; optional debug to print diagnostics.
    Also writes the displayed message to the log via log_writer().
    """
    # Normalize code to int
    try:
        code_int = int(code)
    except (ValueError, TypeError):
        info_text = f"[INFO] Invalid code value: {repr(code)}"
        print(f"{CYAN}{info_text}{RESET}")
        # write to log without ANSI
        log_writer(_strip_ansi(info_text))
        return

    if debug:
        debug_msg = f"DEBUG: code value: {code_int} (type: {type(code_int)})"
        print(debug_msg)
        log_writer(debug_msg)

    text: Optional[str] = MESSAGES.get(code_int)

    color, prefix = _resolve_style(code_int)
    if debug:
        debug_res = f"DEBUG: resolved prefix: {prefix}, color repr: {repr(color)}"
        print(debug_res)
        log_writer(debug_res)

    if text is None:
        display_text = f"No message is defined for code {code_int}."
        # print with color and prefix
        print(f"{color}[{prefix}] {display_text}{RESET}")
        # log plain text
        log_writer(f"[{prefix}] {display_text}")
        return

    _print_message(code_int, text)


# -------------------------------------------------------------
# Test runner: allows running this script directly for debugging
# -------------------------------------------------------------
if __name__ == "__main__":
    print("Testing messages_helper()...\n")

    # Quick diagnostics: show that color codes render correctly
    print("Color test:", f"{RED}RED{RESET}", f"{ORANGE}ORANGE{RESET}", f"{CYAN}CYAN{RESET}")
    print()

    # Example test codes (including an ERR-range code)
    test_codes = [0, 1, 500, 1200, 2010, 2500, 9999]

    for code in test_codes:
        print(f"Calling messages_helper({code})")
        messages_helper(code, debug=True)
        print()
