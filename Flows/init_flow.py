#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Initialization helpers for the project.

Ensures:
 - ConfigFiles/SCAconfig.ini exists (default_config_init)
 - log folder exists (default_log_folder_init)
 - Workspaces directory exists (new)
 - tmp directory is cleared at initialization (new)
"""

import os
import configparser
from pathlib import Path
import shutil

def _find_project_root(max_levels=5):
    """
    Search upward from this file's directory for a directory containing main.py.
    Returns the directory path if found, otherwise returns the directory of this file.
    """
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(max_levels):
        candidate_main = os.path.join(current, "main.py")
        if os.path.isfile(candidate_main):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.dirname(os.path.abspath(__file__))


def default_config_check():
    """
    Check for the presence of ./ConfigFiles/SCAconfig.ini (relative to project root where main.py lives).
    Returns:
        0 -> if the file exists
        1 -> if the file does NOT exist
    """
    project_root = _find_project_root()
    config_path = os.path.join(project_root, "ConfigFiles", "SCAconfig.ini")

    if os.path.isfile(config_path):
        return 0
    else:
        return 1


def default_config_init():
    """
    Ensure the ./ConfigFiles and ./Secrets directories exist (siblings of main.py) and create SCAconfig.ini inside ConfigFiles.
    Behavior:
      - Determine project root by locating main.py (searching upward).
      - Ensure ConfigFiles exists or attempt to create it; if creation fails, return 1.
      - Verify Secrets existence first; if missing, attempt to create it; if creation fails, return 1.
      - Write SCAconfig.ini with absolute paths for ConfigFiles, Secrets, and InstallPath (InstallPath is the directory where main.py resides).
    Returns:
        0 -> on successful creation
        1 -> on any error during directory or file creation
    """
    try:
        project_root = _find_project_root()
        config_dir = os.path.join(project_root, "ConfigFiles")
        secrets_dir = os.path.join(project_root, "Secrets")

        # Ensure ConfigFiles directory exists or create it
        try:
            os.makedirs(config_dir, exist_ok=True)
        except Exception:
            return 1
        if not os.path.isdir(config_dir):
            return 1

        # Verify Secrets directory existence first; if missing, attempt to create it
        if os.path.exists(secrets_dir):
            if not os.path.isdir(secrets_dir):
                return 1
        else:
            try:
                os.makedirs(secrets_dir, exist_ok=True)
            except Exception:
                return 1
            if not os.path.isdir(secrets_dir):
                return 1

        # Use absolute paths in the INI
        abs_config_dir = os.path.abspath(config_dir)
        abs_secrets_dir = os.path.abspath(secrets_dir)
        abs_install_path = os.path.abspath(project_root)
        ini_path = os.path.join(config_dir, "SCAconfig.ini")

        config = configparser.ConfigParser()
        config['Paths'] = {
            'ConfigFiles': abs_config_dir,
            'Secrets': abs_secrets_dir,
            'InstallPath': abs_install_path
        }

        # Write the INI file (overwrites if exists)
        try:
            with open(ini_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
        except Exception:
            return 1

        # Final sanity checks
        if not os.path.isfile(ini_path):
            return 1

        return 0

    except Exception:
        return 1


def default_log_folder_check():
    """
    Check for the presence of ./log directory (relative to project root where main.py lives).
    Returns:
        0 -> if the log folder exists
        1 -> if the log folder does NOT exist
    """
    project_root = _find_project_root()
    log_dir = os.path.join(project_root, "log")

    if os.path.isdir(log_dir):
        return 0
    else:
        return 1


def default_log_folder_init():
    """
    Ensure the ./log directory exists (sibling of main.py).
    Behavior:
      - Determine project root by locating main.py (searching upward).
      - If log exists and is a directory, return 0.
      - If missing, attempt to create it; if creation fails or path is not a directory, return 1.
    Returns:
        0 -> on successful creation or if already exists
        1 -> on any error during directory creation
    """
    try:
        project_root = _find_project_root()
        log_dir = os.path.join(project_root, "log")

        # If path exists but is not a directory, fail
        if os.path.exists(log_dir) and not os.path.isdir(log_dir):
            return 1

        # Create log directory if missing
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            return 1

        # Verify creation
        if not os.path.isdir(log_dir):
            return 1

        return 0

    except Exception:
        return 1


# -------------------------------------------------------------------
# New: ensure Workspaces directory and clear tmp
# -------------------------------------------------------------------
def ensure_workspaces_and_clear_tmp():
    """
    Ensure Workspaces directory exists in project root and clear tmp directory.
    Returns 0 on success, 1 on failure.
    """
    try:
        project_root = _find_project_root()
        workspaces_dir = os.path.join(project_root, "Workspaces")
        tmp_dir = os.path.join(project_root, "tmp")

        # Ensure Workspaces directory
        try:
            os.makedirs(workspaces_dir, exist_ok=True)
        except Exception:
            return 1
        if not os.path.isdir(workspaces_dir):
            return 1

        # Ensure tmp directory exists
        try:
            os.makedirs(tmp_dir, exist_ok=True)
        except Exception:
            return 1
        if not os.path.isdir(tmp_dir):
            return 1

        # Clear tmp directory contents
        try:
            for entry in os.listdir(tmp_dir):
                path = os.path.join(tmp_dir, entry)
                try:
                    if os.path.isfile(path) or os.path.islink(path):
                        os.unlink(path)
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                except Exception:
                    # ignore individual failures
                    pass
        except Exception:
            # ignore clearing failures but return success if dirs exist
            pass

        return 0
    except Exception:
        return 1


# Optional direct usage example
if __name__ == "__main__":
    init_result = default_config_init()
    check_result = default_config_check()
    log_check = default_log_folder_check()
    log_init = default_log_folder_init()
    ws_init = ensure_workspaces_and_clear_tmp()
    print(f"default_config_init returned: {init_result}")
    print(f"default_config_check returned: {check_result}")
    print(f"default_log_folder_check returned: {log_check}")
    print(f"default_log_folder_init returned: {log_init}")
    print(f"ensure_workspaces_and_clear_tmp returned: {ws_init}")
