#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sns_command_helper.py

Exposes a single function:

    sns_command(command: str, timeout: int = 30) -> dict

Behavior:
 - Reads active sessions from ./tmp/SNS_conn.tmp
 - If SNS_SELECTED_SESSION is set, uses that session automatically
 - Otherwise asks the user to select a session
 - Resolves the SNS client object
 - Sends ONLY the provided NSRPC command string
 - Logs the command using UTIL.log_helper.log_writer()
 - Returns {"status":"ok","result":...} or {"status":"error","message":...}
"""

from typing import Any, Dict, Optional, List
from pathlib import Path
import os

# Optional imports
try:
    import UTIL.SNS_connection as SNS_conn_wrapper
except Exception:
    SNS_conn_wrapper = None

try:
    from UTIL import memory_helper
except Exception:
    memory_helper = None

# optional logger helper (only log_writer exists)
try:
    from UTIL import log_helper
except Exception:
    log_helper = None


# ---------------------------------------------------------------------------
# Logging wrappers (COMPATIBILI con log_helper.log_writer)
# ---------------------------------------------------------------------------

def _log_debug(msg: str) -> None:
    try:
        if log_helper is not None:
            log_helper.log_writer(f"DEBUG: {msg}")
    except Exception:
        pass

def _log_info(msg: str) -> None:
    try:
        if log_helper is not None:
            log_helper.log_writer(f"INFO: {msg}")
    except Exception:
        pass

def _log_warning(msg: str) -> None:
    try:
        if log_helper is not None:
            log_helper.log_writer(f"WARNING: {msg}")
    except Exception:
        pass

def _log_error(msg: str) -> None:
    try:
        if log_helper is not None:
            log_helper.log_writer(f"ERROR: {msg}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Session file reader
# ---------------------------------------------------------------------------

def _tmp_sessions_file() -> Path:
    return Path.cwd().resolve() / "tmp" / "SNS_conn.tmp"


def _read_tmp_sessions() -> List[Dict[str, Any]]:
    sessions: List[Dict[str, Any]] = []
    file_path = _tmp_sessions_file()
    try:
        if not file_path.exists():
            return sessions
        with file_path.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                parts = ln.split(maxsplit=4)
                if len(parts) < 5:
                    continue
                session_number, ip_s, port_s, user_s, ts_str = parts
                try:
                    port_i = int(port_s)
                except Exception:
                    continue
                sessions.append({
                    "session_number": session_number,
                    "ip": ip_s,
                    "port": port_i,
                    "username": user_s,
                    "timestamp": ts_str
                })
    except Exception:
        return []
    return sessions


# ---------------------------------------------------------------------------
# Interactive selection
# ---------------------------------------------------------------------------

def _choose_session_interactive(sessions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not sessions:
        return None
    print("Active SNS sessions (from ./tmp/SNS_conn.tmp):")
    for i, s in enumerate(sessions, start=1):
        ts = s.get("timestamp") or ""
        print(f"{i}) {s['session_number']} | {s['ip']}:{s['port']} | user={s['username']} | ts={ts}")
    sel = input("Select session by number (or press Enter to cancel) > ").strip()
    if not sel:
        return None
    try:
        idx = int(sel)
        if idx < 1 or idx > len(sessions):
            print("Invalid selection.")
            return None
        return sessions[idx - 1]
    except Exception:
        print("Invalid selection.")
        return None


# ---------------------------------------------------------------------------
# Session resolution
# ---------------------------------------------------------------------------

def _find_session_by_number(sessions: List[Dict[str, Any]], session_number: str) -> Optional[Dict[str, Any]]:
    if not sessions or not session_number:
        return None
    for s in sessions:
        if str(s.get("session_number")) == str(session_number):
            return s
    return None


def _resolve_client_from_session_info(session_info: Dict[str, Any]) -> Optional[Any]:
    if not session_info:
        return None

    # 1) public helper
    try:
        if SNS_conn_wrapper is not None and hasattr(SNS_conn_wrapper, "get_client_from_session"):
            client = SNS_conn_wrapper.get_client_from_session(session_info)
            if client is not None:
                return client
    except Exception:
        pass

    # 2) direct client
    client = session_info.get("client")
    if client is not None:
        return client

    # 3) internal _SESSIONS
    try:
        if SNS_conn_wrapper is not None and hasattr(SNS_conn_wrapper, "_SESSIONS"):
            sessions_dict = getattr(SNS_conn_wrapper, "_SESSIONS", None)
            if isinstance(sessions_dict, dict):
                target_ip = str(session_info.get("ip") or "").strip()
                target_port = int(session_info.get("port") or 0)
                target_user = str(session_info.get("username") or "").strip()
                for sid, entry in sessions_dict.items():
                    try:
                        e_ip = str(entry.get("ip") or "").strip()
                        e_port = int(entry.get("port") or 0)
                        e_user = str(entry.get("user") or "").strip()
                        if e_ip == target_ip and e_port == target_port and (not target_user or e_user == target_user):
                            return entry.get("client")
                    except Exception:
                        continue
    except Exception:
        pass

    # 4) memory_helper
    try:
        if memory_helper is not None and hasattr(memory_helper, "get_all_sessions"):
            all_sess = memory_helper.get_all_sessions()
            if isinstance(all_sess, dict):
                sess_num = session_info.get("session_number")
                if sess_num and sess_num in all_sess:
                    info = all_sess[sess_num]
                    if info and info.get("client"):
                        return info.get("client")
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Logging of commands
# ---------------------------------------------------------------------------

def _log_command(command: str, session_info: Optional[Dict[str, Any]]):
    """
    Log the command and target session using UTIL.log_helper.log_writer().
    """
    try:
        if log_helper is None:
            return
        target = "unknown"
        if session_info:
            sn = session_info.get("session_number") or ""
            ip = session_info.get("ip") or ""
            target = f"{sn} @ {ip}" if sn or ip else "unknown"
        log_helper.log_writer(f"SNS_COMMAND -> target={target} command={command}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# MAIN FUNCTION
# ---------------------------------------------------------------------------

def sns_command(command: str, timeout: int = 30) -> Dict[str, Any]:
    if not command or not isinstance(command, str):
        return {"status": "error", "message": "Invalid command string"}

    sessions = _read_tmp_sessions()

    preselected = os.environ.get("SNS_SELECTED_SESSION")
    session_info = None

    if preselected:
        session_info = _find_session_by_number(sessions, preselected)
        if session_info is None:
            try:
                if memory_helper is not None and hasattr(memory_helper, "get_all_sessions"):
                    all_sess = memory_helper.get_all_sessions()
                    if isinstance(all_sess, dict) and preselected in all_sess:
                        session_info = all_sess[preselected]
            except Exception:
                session_info = None

    if session_info is None:
        if not sessions:
            try:
                if memory_helper is not None and hasattr(memory_helper, "get_all_sessions"):
                    all_sess = memory_helper.get_all_sessions()
                else:
                    all_sess = {}
            except Exception:
                all_sess = {}

            if isinstance(all_sess, dict) and all_sess:
                keys = list(all_sess.keys())
                print("Sessions available from memory_helper:")
                for i, k in enumerate(keys, start=1):
                    info = all_sess[k]
                    ip = info.get("ip") or "unknown"
                    user = info.get("username") or ""
                    print(f"{i}) session_number={k} ip={ip} user={user}")
                sel = input("Select session by number (or press Enter to cancel) > ").strip()
                if not sel:
                    return {"status": "error", "message": "Operation cancelled by user"}
                try:
                    idx = int(sel)
                    if idx < 1 or idx > len(keys):
                        return {"status": "error", "message": "Invalid selection"}
                    session_info = all_sess[keys[idx - 1]]
                except Exception:
                    return {"status": "error", "message": "Invalid selection"}
            else:
                return {"status": "error", "message": "No active SNS sessions found"}
        else:
            chosen = _choose_session_interactive(sessions)
            if not chosen:
                return {"status": "error", "message": "Operation cancelled or invalid selection"}
            session_info = chosen

    # LOG COMMAND
    _log_command(command, session_info)

    # RESOLVE CLIENT
    client = _resolve_client_from_session_info(session_info)
    if client is None:
        return {"status": "error", "message": "Unable to resolve SNS client for the selected session"}

    # SEND COMMAND
    try:
        if not hasattr(client, "send_command"):
            return {"status": "error", "message": "Resolved client does not support send_command"}
        resp = client.send_command(command, timeout=timeout)
        return {"status": "ok", "result": resp}
    except Exception as e:
        return {"status": "error", "message": f"Command execution failed: {e}"}
