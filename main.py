#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from pathlib import Path

from UI.banner import show_banner
from Flows.init_flow import default_config_check, default_config_init
from Flows.init_flow import default_log_folder_check, default_log_folder_init
from UI.RuntimeMessages import messages_helper

# Dispatcher for menus
from UTIL.menu_helper import menu_caller

# Optional memory helper initialization
try:
    from UTIL import memory_helper
except Exception:
    memory_helper = None


TMP_DIR_NAME = "tmp"
SNS_TMP_NAME = "SNS_conn.tmp"


def ensure_tmp_and_sns_file(tmp_dir_name: str = TMP_DIR_NAME, filename: str = SNS_TMP_NAME) -> None:
    """
    Ensure that a tmp directory exists next to main.py, remove SNS_conn.tmp if present,
    and create an empty SNS_conn.tmp file.
    """
    script_dir = Path(__file__).resolve().parent
    tmp_dir = script_dir / tmp_dir_name
    tmp_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = tmp_dir / filename

    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except Exception:
            raise

    try:
        tmp_path.touch(exist_ok=True)
    except Exception:
        raise


def main():
    """
    Main application logic.
    """
    ensure_tmp_and_sns_file()

    # Initialize memory helper if available
    if memory_helper is not None:
        try:
            memory_helper.init_store()
        except Exception:
            pass

    rc_banner = show_banner()

    # Log folder check/init
    rc_log_check = default_log_folder_check()
    if rc_log_check != 0:
        rc_log_init = default_log_folder_init()
        if rc_log_init == 0:
            messages_helper(1010)

    rc_config = default_config_check()
    if rc_config == 0:
        # Call MAIN MENU through the dispatcher
        menu_caller("main")
        sys.exit(0)
    else:
        messages_helper(10)

    rc_init = default_config_init()
    if rc_init != 0:
        messages_helper(2010)
        sys.exit(rc_init)
    else:
        # If config init succeeded but main menu was not launched yet
        menu_caller("main")
        sys.exit(0)


if __name__ == "__main__":
    main()
