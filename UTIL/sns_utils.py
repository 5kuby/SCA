#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared SNS utilities

Provides:
- _find_root_from_ini
- _ensure_tmp_and_get_file
- _append_session_line_direct
- _read_tmp_file_lines
- _parse_session_line
- _generate_session_number
- _current_iso_timestamp_with_tz
- _format_duration_seconds

These helpers are intentionally minimal and filesystem-focused.
"""

import configparser
import secrets
import string
import os
from pathlib import Path
from datetime import datetime

# -------------------------------------------------------------------
# Root / tmp helpers
# -------------------------------------------------------------------

def _find_root_from_ini() -> Path:
    module_dir = Path(__file__).parent.resolve()
    cwd = Path.cwd().resolve()

    # 1) file.ini in cwd or module_dir
    for base in (cwd, module_dir):
        ini = base / "file.ini"
        if ini.exists():
            try:
                cfg = configparser.ConfigParser()
                cfg.read(ini)
                if cfg.defaults() and "root" in cfg.defaults():
                    root = cfg.defaults().get("root")
                    if root:
                        return Path(root).expanduser().resolve()
                if cfg.has_section("paths") and cfg.has_option("paths", "root"):
                    root = cfg.get("paths", "root")
                    if root:
                        return Path(root).expanduser().resolve()
            except Exception:
                pass

    # 2) search for main.py upward from cwd
    cur = cwd
    while True:
        if (cur / "main.py").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent

    # 3) search for main.py upward from module_dir
    cur = module_dir
    while True:
        if (cur / "main.py").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent

    # 4) fallback to cwd
    return cwd


def _ensure_tmp_and_get_file(filename: str = "SNS_conn.tmp") -> Path:
    """
    Ensures that ./tmp exists (where ./ is the determined root) and returns the Path to SNS_conn.tmp.
    """
    root = _find_root_from_ini()
    tmp_dir = root / "tmp"
    try:
        tmp_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return tmp_dir / filename


# -------------------------------------------------------------------
# File I/O helpers
# -------------------------------------------------------------------

def _append_session_line_direct(ip: str, port: int, username: str, session_number: str, timestamp_iso: str, filename: str = "SNS_conn.tmp") -> bool:
    """
    Appends a line:
    <SESSION_NUMBER> <IP> <PORT> <USERNAME> <TIMESTAMP_ISO>

    Writes in binary mode, flushes and fsyncs for persistence.
    """
    file_path = _ensure_tmp_and_get_file(filename)
    line = f"{session_number} {ip} {int(port)} {username} {timestamp_iso}\n"
    try:
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        with open(str(file_path), "ab") as f:
            data = line.encode("utf-8")
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        return True
    except Exception as e:
        # Minimal fallback: print error (do not raise)
        print(f"[SNS FILE WRITE ERROR] {file_path}: {e}")
        return False


def _read_tmp_file_lines(filename: str = "SNS_conn.tmp") -> list:
    """
    Reads all non-empty lines from SNS_conn.tmp and returns them as a list of strings.
    """
    file_path = _ensure_tmp_and_get_file(filename)
    try:
        if not file_path.exists():
            return []
        with file_path.open("r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip()]
        return lines
    except Exception as e:
        print(f"[SNS FILE READ ERROR] {file_path}: {e}")
        return []


def _parse_session_line(line: str):
    """
    Parses a line in the format:
    <SESSION_NUMBER> <IP> <PORT> <USERNAME> <TIMESTAMP_ISO>

    Returns (session_number, ip, port, username, timestamp_str) or None if invalid.
    """
    if not line:
        return None
    parts = line.strip().split(maxsplit=4)
    if len(parts) < 5:
        return None
    session_number, ip, port_str, username, timestamp_str = parts
    try:
        port = int(port_str)
    except Exception:
        return None
    return session_number, ip, port, username, timestamp_str


# -------------------------------------------------------------------
# Session utilities
# -------------------------------------------------------------------

def _generate_session_number(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _current_iso_timestamp_with_tz() -> str:
    return datetime.now().astimezone().isoformat()


def _format_duration_seconds(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
