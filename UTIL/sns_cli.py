#!/usr/bin/env python3
"""
Launches the external 'snscli' command using an existing SNS session from SNS_conn.tmp.
Supports multiple sessions and logs errors using log_writer.

This module uses UTIL.sns_utils for file helpers and UTIL.memory_helper (if available)
to retrieve stored session passwords.
"""

import sys
import subprocess

# Import helpers
try:
    from UTIL.sns_utils import _read_tmp_file_lines, _parse_session_line
    from UTIL.log_helper import log_writer
except Exception as e:
    print(f"Critical import error: {e}")
    sys.exit(1)

# Optional memory helper
try:
    from UTIL import memory_helper
except Exception:
    memory_helper = None


# ---------------------------------------------------------
# LOAD SESSIONS
# ---------------------------------------------------------
def load_all_sessions():
    try:
        lines = _read_tmp_file_lines()
    except Exception as e:
        log_writer(f"[SNSCLI] Error reading SNS_conn.tmp: {e}")
        print("Unable to read SNS_conn.tmp")
        return []

    sessions = []
    for line in lines:
        parsed = _parse_session_line(line)
        if parsed:
            session_number, ip, port, username, timestamp = parsed
            sessions.append({
                "session_number": session_number,
                "ip": ip,
                "port": port,
                "username": username,
                "timestamp": timestamp
            })
        else:
            log_writer(f"[SNSCLI] Malformed session entry ignored: {line}")

    return sessions


# ---------------------------------------------------------
# SESSION SELECTION
# ---------------------------------------------------------
def select_session(sessions):
    if not sessions:
        print("No active SNS sessions found.")
        return None

    if len(sessions) == 1:
        return sessions[0]

    print("\n=== ACTIVE SNS SESSIONS ===")
    for idx, s in enumerate(sessions, start=1):
        print(f"{idx}) Session {s['session_number']} - {s['ip']}:{s['port']} "
              f"User: {s['username']}  Started: {s['timestamp']}")

    while True:
        choice = input("\nSelect session number > ").strip()
        try:
            choice = int(choice)
            if 1 <= choice <= len(sessions):
                return sessions[choice - 1]
        except ValueError:
            pass

        print("Invalid selection. Try again.")


# ---------------------------------------------------------
# LAUNCH SNSCLI
# ---------------------------------------------------------
def launch_snscli(ip, port, username, password):
    """
    Launch snscli. Note: passing password on command line may expose it in process list.
    This function preserves existing behavior (password passed as argument) for compatibility.
    """
    cmd = [
        "snscli",
        "--host", ip,
        "--port", str(port),
        "--user", username,
        "--password", password,
        "--no-sslverifypeer",
        "--no-sslverifyhost"
    ]

    print("\nLaunching snscli...\n")

    try:
        subprocess.run(cmd)
    except FileNotFoundError:
        log_writer("[SNSCLI] snscli command not found in PATH")
        print("Error: 'snscli' command not found. Is it installed?")
    except Exception as e:
        log_writer(f"[SNSCLI] Error launching snscli: {e}")
        print("Error launching snscli.")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    sessions = load_all_sessions()
    session = select_session(sessions)
    if not session:
        return

    print("\nUsing session:")
    print(f"  Session:  {session['session_number']}")
    print(f"  Target:   {session['ip']}:{session['port']}")
    print(f"  User:     {session['username']}")
    print(f"  Started:  {session['timestamp']}\n")

    # Try to retrieve password from memory_helper if available
    password = None
    if memory_helper is not None and hasattr(memory_helper, "get_session"):
        try:
            stored = memory_helper.get_session(session["session_number"])
            if stored and stored.get("password"):
                # Ask user whether to use stored password
                use_stored = input("Use stored password from memory? (Y/n) > ").strip().lower()
                if use_stored in ("", "y", "yes"):
                    password = stored.get("password")
        except Exception as e:
            log_writer(f"[SNSCLI] memory_helper access error: {e}")

    if password is None:
        # Fallback: ask user for password
        password = input(f"Password for {session['username']}@{session['ip']} > ").strip()

    launch_snscli(
        session["ip"],
        session["port"],
        session["username"],
        password
    )


if __name__ == "__main__":
    main()
