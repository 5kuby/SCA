#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SNS Connection Manager
----------------------

Exposes the function:

    SNS_connection(action, ip, port, username, password)

and a helper:

    save_connection_to_vault(ip, port, username, password)

Behavior:
- "open" : opens SSLClient, keeps the session in memory and appends a line to ./tmp/SNS_conn.tmp
           also stores session info in memory_helper.set_session(session_number, info_dict)
- "close": closes in‑memory sessions matching ip:port and removes session entries from memory_helper
- "list" : reads ./tmp/SNS_conn.tmp, computes durations and prints entries with duration in HH:MM:SS

Note: writing to SNS_conn.tmp is direct (does not use log_writer) and is fsync'ed for persistence.
"""

import importlib
import threading
import itertools
import time
import os
from datetime import datetime
from typing import Dict, Any

# Logger (used only for informational logs; file writing is direct)
try:
    from UTIL.log_helper import log_writer
except Exception:
    def log_writer(msg: str):
        print("[LOG]", msg)

# Optional memory helper for storing session info
try:
    from UTIL import memory_helper
except Exception:
    memory_helper = None

# Import shared sns utilities
try:
    from UTIL.sns_utils import (
        _ensure_tmp_and_get_file,
        _append_session_line_direct,
        _read_tmp_file_lines,
        _parse_session_line,
        _generate_session_number,
        _current_iso_timestamp_with_tz,
        _format_duration_seconds
    )
except Exception:
    # If import fails, define minimal fallbacks (should not happen in normal setup)
    def _ensure_tmp_and_get_file():
        from pathlib import Path
        return Path.cwd() / "tmp" / "SNS_conn.tmp"
    def _append_session_line_direct(*args, **kwargs):
        return False
    def _read_tmp_file_lines(*args, **kwargs):
        return []
    def _parse_session_line(*args, **kwargs):
        return None
    def _generate_session_number(length=8):
        return "X"*length
    def _current_iso_timestamp_with_tz():
        return datetime.now().astimezone().isoformat()
    def _format_duration_seconds(s):
        return "00:00:00"


# Minimal interface for linters
class SSLClientInterface:
    def __init__(self, host: str, port: int, user: str, password: str,
                 sslverifyhost: bool = True, sslverifypeer: bool = True) -> None:
        raise NotImplementedError

    def send_command(self, cmd: str) -> Any:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError


# In‑memory session tracking
_SESSIONS: Dict[int, Dict[str, Any]] = {}
_session_id_counter = itertools.count(1)
_sessions_lock = threading.Lock()


# --------------------------------------------------------------------
# Keepalive worker
# --------------------------------------------------------------------

def _keepalive_worker(session_id: int, client: object, interval: int = 60) -> None:
    """
    Keepalive: sends harmless commands to keep the session alive.
    """
    try:
        while True:
            time.sleep(interval)
            with _sessions_lock:
                if session_id not in _SESSIONS:
                    break
            try:
                if hasattr(client, "send_command"):
                    client.send_command("SYSTEM PROPERTY")
            except Exception as e:
                log_writer(f"Keepalive: session {session_id} lost: {e}")
                with _sessions_lock:
                    _SESSIONS.pop(session_id, None)
                try:
                    if hasattr(client, "disconnect"):
                        client.disconnect()
                except Exception:
                    pass
                # Also remove from memory_helper session store if available
                try:
                    if memory_helper is not None:
                        all_sessions = memory_helper.get_all_sessions() if hasattr(memory_helper, "get_all_sessions") else {}
                        for sid, info in list(all_sessions.items()):
                            try:
                                if info.get("ip") == _SESSIONS.get(session_id, {}).get("ip") and \
                                   int(info.get("port", 0)) == int(_SESSIONS.get(session_id, {}).get("port", 0)):
                                    memory_helper.delete_session(sid)
                            except Exception:
                                pass
                except Exception:
                    pass
                break
    except Exception as e:
        log_writer(f"Keepalive worker error for session {session_id}: {e}")


# --------------------------------------------------------------------
# Vault helper moved here: save connection to vault
# --------------------------------------------------------------------

def save_connection_to_vault(ip: str, port: int, username: str, password: str) -> dict:
    """
    Save a connection entry into a selected vault using UTIL.vault_helper.

    This function encapsulates the vault selection/opening and the call to
    vault_manager("add_entry", arg1=entry_name, arg2=dict).

    Returns a dict with keys: status ("ok" or "error"), message (str).
    """
    try:
        from UTIL.vault_helper import vault_manager
    except Exception as e:
        msg = f"Vault manager not available: {e}"
        log_writer(msg)
        return {"status": "error", "message": msg}

    # List vaults
    resp = vault_manager("list")
    if resp.get("status") != "ok":
        msg = f"Error listing vaults: {resp.get('message')}"
        log_writer(msg)
        return {"status": "error", "message": msg}

    vaults = resp.get("result", [])
    if not vaults:
        msg = "No vaults available."
        return {"status": "error", "message": msg}

    # Present vaults to caller via return value; the UI should select one.
    # To keep compatibility with previous behavior (UI selected vault by index),
    # we return the list so the caller can choose.
    return {"status": "ok", "result": vaults}


def add_entry_to_vault(vault_name: str, entry_name: str, ip: str, port: int, username: str, password: str) -> dict:
    """
    Add an entry to a specific vault. Handles opening the vault if needed.

    Returns a dict with keys: status ("ok" or "error"), message (str).
    """
    try:
        from UTIL.vault_helper import vault_manager
    except Exception as e:
        msg = f"Vault manager not available: {e}"
        log_writer(msg)
        return {"status": "error", "message": msg}

    # NOTE: previous implementation checked vault_manager("check_open") and required
    # the vault_name to be present in the returned list. That check was brittle because
    # different vault_manager implementations may return different formats.
    # To be robust, attempt to call add_entry directly and return its response.
    try:
        entry_dict = {
            "host": ip,
            "port": str(port),
            "username": username,
            "password": password
        }

        resp = vault_manager(
            "add_entry",
            arg1=entry_name,
            arg2=entry_dict
        )

        # Return vault_manager response as-is (caller will display message)
        return resp

    except Exception as e:
        msg = f"Error adding entry to vault: {e}"
        log_writer(msg)
        return {"status": "error", "message": msg}


def open_vault_with_password(vault_name: str, vault_password: str) -> dict:
    """
    Attempt to open the vault with the provided password.
    Returns vault_manager response dict.
    """
    try:
        from UTIL.vault_helper import vault_manager
    except Exception as e:
        msg = f"Vault manager not available: {e}"
        log_writer(msg)
        return {"status": "error", "message": msg}

    try:
        resp = vault_manager("open", vault_name=vault_name, password=vault_password)
        return resp
    except Exception as e:
        msg = f"Error opening vault: {e}"
        log_writer(msg)
        return {"status": "error", "message": msg}


# --------------------------------------------------------------------
# Main API
# --------------------------------------------------------------------

def SNS_connection(action: str, ip: str, port: int, username: str, password: str) -> int:
    """
    Main entry point.
    """
    action = (action or "").lower().strip()
    if action not in ("open", "close", "list"):
        log_writer(f"SNS_connection: invalid action: {action}")
        return 1

    # ----------------------------------------------------------------
    # LIST
    # ----------------------------------------------------------------
    if action == "list":
        file_path = _ensure_tmp_and_get_file()
        print(f"[SNS FILE PATH] {file_path}")

        lines = _read_tmp_file_lines()

        header_lines = [
            "=== ACTIVE SNS CONNECTIONS ===",
            "",
            "Active connections:",
            ""
        ]

        if not lines:
            print("\n".join(header_lines + ["No active connections found!."]))
            return 0

        now = datetime.now().astimezone()
        entries = []
        for ln in lines:
            parsed = _parse_session_line(ln)
            if not parsed:
                continue
            session_number, ip_s, port_s, user_s, ts_str = parsed

            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.astimezone()
            except Exception:
                duration = "00:00:00"
                entries.append({
                    "session_number": session_number,
                    "ip": ip_s,
                    "port": port_s,
                    "user": user_s,
                    "duration": duration
                })
                continue

            try:
                delta = now - ts.astimezone(now.tzinfo)
                seconds = int(delta.total_seconds())
            except Exception:
                seconds = 0

            duration = _format_duration_seconds(seconds)
            entries.append({
                "session_number": session_number,
                "ip": ip_s,
                "port": port_s,
                "user": user_s,
                "duration": duration
            })

        output_lines = header_lines[:]
        for e in entries:
            output_lines.append(
                f"{e['session_number']} | {e['ip']}:{e['port']} | user={e['user']} | duration={e['duration']}"
            )
        print("\n".join(output_lines))
        return 0

    # ----------------------------------------------------------------
    # Import Stormshield SSLClient
    # ----------------------------------------------------------------
    try:
        mod = importlib.import_module("stormshield.sns.sslclient")
        RealSSLClient = getattr(mod, "SSLClient")
    except Exception as e:
        log_writer(f"Unable to import stormshield.sns.sslclient: {e}")
        return 1

    # ----------------------------------------------------------------
    # OPEN
    # ----------------------------------------------------------------
    if action == "open":
        try:
            client = RealSSLClient(
                host=ip,
                port=int(port),
                user=username,
                password=password,
                sslverifyhost=False,
                sslverifypeer=False
            )

            session_id = next(_session_id_counter)
            created_ts = time.time()

            with _sessions_lock:
                _SESSIONS[session_id] = {
                    "client": client,
                    "ip": ip,
                    "port": int(port),
                    "user": username,
                    "created": created_ts
                }

            session_number = _generate_session_number(8)
            timestamp_iso = _current_iso_timestamp_with_tz()

            appended = _append_session_line_direct(
                ip=str(ip),
                port=int(port),
                username=str(username),
                session_number=session_number,
                timestamp_iso=timestamp_iso
            )

            if not appended:
                with _sessions_lock:
                    _SESSIONS.pop(session_id, None)
                try:
                    if hasattr(client, "disconnect"):
                        client.disconnect()
                except Exception:
                    pass
                print(f"[SNS] Failed to persist session {session_id} to SNS_conn.tmp")
                return 1

            # Store session info in memory_helper if available
            try:
                if memory_helper is not None and hasattr(memory_helper, "set_session"):
                    info = {
                        "ip": str(ip),
                        "port": int(port),
                        "username": str(username),
                        "password": str(password),
                        "created": timestamp_iso,
                        "session_number": session_number
                    }
                    memory_helper.set_session(session_number, info)
            except Exception as e:
                log_writer(f"memory_helper: failed to store session info for {session_number}: {e}")

            t = threading.Thread(target=_keepalive_worker, args=(session_id, client), daemon=True)
            t.start()

            log_writer(f"Opened session {session_id} to {ip}:{port} (session_number={session_number})")
            return 0

        except Exception as e:
            log_writer(f"Error opening SSLClient to {ip}:{port} - {e}")
            return 1

    # ----------------------------------------------------------------
    # CLOSE (accetta un session_id e rimuove la riga dal tmp)
    # ----------------------------------------------------------------
    if action == "close":
        session_id = ip  # il chiamante passa il session_id nel parametro ip
        closed = False

        # 1) Rimuovi la sessione da memory_helper usando il session_id
        try:
            if memory_helper is not None and hasattr(memory_helper, "delete_session"):
                memory_helper.delete_session(session_id)
                log_writer(f"Removed session_id={session_id} from memory_helper")
        except Exception as e:
            log_writer(f"Error removing session_id={session_id} from memory_helper: {e}")

        # 2) Rimuovi la riga dal file SNS_conn.tmp usando il session_id
        try:
            from UTIL.sns_utils import _remove_session_from_tmp
            _remove_session_from_tmp(session_id)
            log_writer(f"Removed session_id={session_id} from SNS_conn.tmp")
        except Exception as e:
            log_writer(f"Error removing session_id={session_id} from SNS_conn.tmp: {e}")

        # 3) Chiudi eventuali sessioni in memoria (_SESSIONS) che hanno stesso IP/porta
        #    (comportamento originale, lasciato intatto)
        with _sessions_lock:
            to_close = [
                sid for sid, v in _SESSIONS.items()
                if v["ip"] == ip and v["port"] == int(port)
            ]

        for sid in to_close:
            try:
                with _sessions_lock:
                    entry = _SESSIONS.pop(sid, None)

                if entry and entry.get("client"):
                    try:
                        entry["client"].disconnect()
                    except Exception as e:
                        log_writer(f"Error disconnecting session {sid}: {e}")

                log_writer(f"Closed session {sid} to {ip}:{port}")
                closed = True

            except Exception as e:
                log_writer(f"Error closing session {sid}: {e}")

        return 0 if closed else 1


    return 1
