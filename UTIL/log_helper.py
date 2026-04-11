#!/usr/bin/env python3
import os
import configparser
from datetime import datetime
from typing import Union

THIS_DIR = os.path.abspath(os.path.dirname(__file__))  # expected: .../project/UTIL
DEFAULT_PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))  # .../project
CONFIG_DIR_NAME = "ConfigFiles"
CONFIG_FILENAME = "SCAconfig.ini"

def _config_path_from_project_root(project_root: str) -> str:
    return os.path.join(project_root, CONFIG_DIR_NAME, CONFIG_FILENAME)

def _read_installpath(config_path: str) -> Union[str, None]:
    parser = configparser.ConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
    except Exception:
        return None
    if "installpath" in parser.defaults():
        return parser.defaults()["installpath"]
    for section in parser.sections():
        if parser.has_option(section, "installpath"):
            return parser.get(section, "installpath")
    return None

def _resolve_project_root() -> str:
    candidate_config = _config_path_from_project_root(DEFAULT_PROJECT_ROOT)
    if os.path.isfile(candidate_config):
        installpath = _read_installpath(candidate_config)
        if installpath:
            if not os.path.isabs(installpath):
                config_dir = os.path.dirname(candidate_config)
                installpath = os.path.abspath(os.path.join(config_dir, installpath))
            return installpath
    return DEFAULT_PROJECT_ROOT

PROJECT_ROOT = _resolve_project_root()
LOG_PATH = os.path.join(PROJECT_ROOT, "log", "SCAlog.log")

def log_writer(message: Union[str, bytes]) -> int:
    """
    Append message to <project_root>/log/SCAlog.log.
    Returns 0 on success, 1 on error.
    Does NOT create directories.
    Timestamp uses the operating system timezone.
    """
    try:
        if isinstance(message, bytes):
            message = message.decode("utf-8", errors="replace")
        # Use local system timezone for timestamp
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        entry = f"{timestamp} - {message}\n"
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
        return 0
    except Exception:
        return 1

if __name__ == "__main__":
    result = log_writer("Starting example script from UTIL (local timezone)")
    if result == 0:
        print(f"Message written to {LOG_PATH}")
    else:
        print("Error writing to log")
