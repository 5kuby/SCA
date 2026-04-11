#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Dict, List, Any
from pathlib import Path
from getpass import getpass
from datetime import datetime
import os
import re
import uuid

from UTIL import sns_command_helper
from UTIL import workspace_helper
from UTIL import memory_helper

try:
    from UTIL import sns_utils
except Exception:
    sns_utils = None

try:
    from UTIL import log_helper
except Exception:
    log_helper = None


def _log(msg: str):
    try:
        if log_helper is not None:
            log_helper.log_writer(msg)
    except Exception:
        pass


def _read_sessions_from_tmp() -> List[Dict[str, Any]]:
    sessions: List[Dict[str, Any]] = []
    if sns_utils is None:
        return sessions
    try:
        lines = sns_utils._read_tmp_file_lines()
        for ln in lines:
            parsed = sns_utils._parse_session_line(ln)
            if not parsed:
                continue
            session_number, ip_s, port_s, user_s, ts_str = parsed
            try:
                port_i = int(port_s)
            except Exception:
                port_i = 0
            sessions.append({
                "session_number": session_number,
                "ip": ip_s,
                "port": port_i,
                "username": user_s,
                "timestamp": ts_str
            })
    except Exception:
        pass
    return sessions


def _select_session_interactive() -> Optional[Dict[str, Any]]:
    tmp_sessions = _read_sessions_from_tmp()
    if not tmp_sessions:
        try:
            all_sess = memory_helper.get_all_sessions()
            if not all_sess:
                return None
            keys = list(all_sess.keys())
            if len(keys) == 1:
                return all_sess[keys[0]]
            print("Available sessions (from memory_helper):")
            for i, k in enumerate(keys, start=1):
                info = all_sess[k]
                ip = info.get("ip") or info.get("host") or "unknown"
                user = info.get("username") or info.get("user") or ""
                print(f"{i}) session_number={k} ip={ip} user={user}")
            sel = input("Select session by number (or press Enter to cancel) > ").strip()
            if not sel:
                return None
            idx = int(sel)
            if idx < 1 or idx > len(keys):
                print("Invalid selection.")
                return None
            return all_sess[keys[idx - 1]]
        except Exception:
            return None

    print("Sessions found in ./tmp/SNS_conn.tmp:")
    for i, s in enumerate(tmp_sessions, start=1):
        print(f"{i}) {s['session_number']} | {s['ip']}:{s['port']} | user={s['username']} | ts={s['timestamp']}")

    sel = input("Select session by number (or press Enter to cancel) > ").strip()
    if not sel:
        return None
    try:
        idx = int(sel)
        if idx < 1 or idx > len(tmp_sessions):
            print("Invalid selection.")
            return None
        chosen = tmp_sessions[idx - 1]
    except Exception:
        print("Invalid selection.")
        return None

    sess_num = chosen.get("session_number")
    try:
        all_sess = memory_helper.get_all_sessions()
        if isinstance(all_sess, dict) and sess_num in all_sess:
            return all_sess[sess_num]
    except Exception:
        pass

    return chosen


def _obtain_serial(timeout: int = 10) -> Optional[str]:
    """
    Ottiene il seriale della macchina usando SYSTEM PROPERTY.
    Rimuove il prefisso SerialNumber=.
    """
    try:
        resp = sns_command_helper.sns_command("SYSTEM PROPERTY", timeout=timeout)
        if resp.get("status") != "ok":
            return None

        raw = resp.get("result")
        if raw is None:
            return None

        text = raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)

        # Rimuovi header tipo "200 code=..."
        lines = text.splitlines()
        if lines and lines[0].strip().lower().startswith(("100", "101", "200")):
            lines = lines[1:]

        for ln in lines:
            ln = ln.strip()
            if ln.lower().startswith("serialnumber="):
                serial = ln.split("=", 1)[1].strip()
                serial = serial.strip('"').strip("'")
                return serial

        return None
    except Exception:
        return None


def backup(timeout: int = 120):
    ws_resp = workspace_helper.get_current_workspace()
    if ws_resp.get("status") != "ok":
        print("Error reading active workspace:", ws_resp.get("message"))
        return
    ws = ws_resp.get("result")
    if not ws:
        print("No active workspace.")
        return

    remote_dir = ws.get("backup_directory")
    if not remote_dir:
        print("backup_directory not available.")
        return

    remote_dir = str(remote_dir).replace("\\", "/").rstrip("/") + "/"

    session_info = _select_session_interactive()
    if not session_info:
        print("No session selected.")
        return

    sess_num = str(session_info.get("session_number") or "")
    os.environ["SNS_SELECTED_SESSION"] = sess_num

    try:
        pwd = getpass("Backup password (leave empty to omit) > ").strip()
        pwd_part = f" password={pwd}" if pwd else ""

        # ottieni seriale
        serial = _obtain_serial(timeout=10)
        if not serial:
            serial = f"unknown_{sess_num}"

        # timestamp consigliato
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        remote_filename = f"{serial}_{ts}.na"

        remote_path = f"{remote_dir}{remote_filename}"

        redirect_cmd = f"CONFIG BACKUP list=all{pwd_part} > {remote_path}"

        _log(f"backup: sending '{redirect_cmd}' to session {sess_num}")

        r = sns_command_helper.sns_command(redirect_cmd, timeout=timeout)

        if r.get("status") == "ok":
            print("Backup command sent. Remote response:")
            print(r.get("result"))
            print(f"Remote backup path: {remote_path}")
        else:
            print("Backup failed:", r.get("message"))
    finally:
        del os.environ["SNS_SELECTED_SESSION"]


def restore(timeout: int = 120):
    ws_resp = workspace_helper.get_current_workspace()
    if ws_resp.get("status") != "ok":
        print("Error reading active workspace:", ws_resp.get("message"))
        return
    ws = ws_resp.get("result")
    if not ws:
        print("No active workspace.")
        return

    backup_dir = ws.get("backup_directory")
    if not backup_dir:
        print("backup_directory not available.")
        return

    session_info = _select_session_interactive()
    if not session_info:
        print("No session selected.")
        return

    sess_num = str(session_info.get("session_number") or "")
    os.environ["SNS_SELECTED_SESSION"] = sess_num

    try:
        files = sorted([p for p in Path(backup_dir).iterdir() if p.is_file()])
        if not files:
            print("No backup files found.")
            return

        print("Available backup files:")
        for i, f in enumerate(files, start=1):
            print(f"{i}) {f.name}")

        sel = input("Selection > ").strip()
        if not sel:
            print("Cancelled.")
            return

        if sel.isdigit():
            idx = int(sel)
            if idx < 1 or idx > len(files):
                print("Invalid index.")
                return
            chosen_path = str(files[idx - 1].resolve())
        else:
            chosen_path = sel

        pwd = getpass("Restore password (leave empty to omit) > ").strip()
        pwd_part = f" password={pwd}" if pwd else ""

        command = f"CONFIG RESTORE list=all{pwd_part} < {chosen_path}"

        _log(f"restore: sending '{command}' to session {sess_num}")

        resp = sns_command_helper.sns_command(command, timeout=timeout)
        if resp.get("status") == "ok":
            print("Restore executed. Remote response:")
            print(resp.get("result"))
        else:
            print("Restore failed:", resp.get("message"))
    finally:
        del os.environ["SNS_SELECTED_SESSION"]