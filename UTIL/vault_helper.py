#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vault_helper

Encrypted vault manager.
Uses memory_helper to store (vault_path -> password) pairs.
Logs exclusively through log_helper.
"""

from typing import Optional, Dict, Any, List
import os
import json
import tempfile
import errno
import base64
from pathlib import Path

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# -------------------------------------------------------------------
# Logging wrappers (log exclusively through log_helper)
# -------------------------------------------------------------------

try:
    from UTIL import log_helper
except Exception:
    log_helper = None

try:
    from UTIL import memory_helper
except Exception:
    memory_helper = None


def _log_debug(msg: str) -> None:
    try:
        if log_helper is not None:
            if hasattr(log_helper, "debug"):
                log_helper.debug(msg)
            else:
                log_helper.info(f"DEBUG: {msg}")
    except Exception:
        pass


def _log_info(msg: str) -> None:
    try:
        if log_helper is not None:
            log_helper.info(msg)
    except Exception:
        pass


def _log_warning(msg: str) -> None:
    try:
        if log_helper is not None:
            if hasattr(log_helper, "warning"):
                log_helper.warning(msg)
            else:
                log_helper.info(f"WARNING: {msg}")
    except Exception:
        pass


def _log_error(msg: str) -> None:
    try:
        if log_helper is not None:
            if hasattr(log_helper, "error"):
                log_helper.error(msg)
            else:
                log_helper.info(f"ERROR: {msg}")
    except Exception:
        pass


# -------------------------------------------------------------------
# Configuration and state
# -------------------------------------------------------------------

DEFAULT_SECRETS_DIRS = ['./Secrets']
DEFAULT_VAULT_BASENAME = 'vault.json'

VAULT_FILENAME = os.path.join(DEFAULT_SECRETS_DIRS[0], DEFAULT_VAULT_BASENAME)
_LOCK_FILENAME = VAULT_FILENAME + '.lock'

_VAULT_STATE: Dict[str, Any] = {
    'opened': False,
    'entries': []
}

_KDF_ITERATIONS = 200_000
_SALT_SIZE = 16
_AES_KEY_SIZE = 32
_NONCE_SIZE = 12


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _ensure_dir_exists(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        _log_warning(f"Failed to ensure directory {path}: {e}")


def _atomic_write_json(path: str, data: Any) -> bool:
    try:
        dirpath = os.path.dirname(os.path.abspath(path)) or '.'
        fd, tmp_path = tempfile.mkstemp(prefix='.tmp_vault_', dir=dirpath)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        return True
    except Exception as e:
        _log_error(f"Atomic write failed for {path}: {e}")
        return False


def _derive_key(password: str, salt: bytes, iterations: int = _KDF_ITERATIONS) -> bytes:
    pwd = password.encode('utf-8')
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_AES_KEY_SIZE,
        salt=salt,
        iterations=iterations
    )
    key = kdf.derive(pwd)
    _log_debug(f"Derived key with iterations={iterations} salt_len={len(salt)}")
    return key


def _encrypt_blob(plaintext: bytes, password: str) -> Dict[str, Any]:
    salt = os.urandom(_SALT_SIZE)
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return {
        'salt': base64.b64encode(salt).decode('ascii'),
        'nonce': base64.b64encode(nonce).decode('ascii'),
        'iterations': _KDF_ITERATIONS,
        'ciphertext': base64.b64encode(ciphertext).decode('ascii')
    }


def _decrypt_blob(blob: Dict[str, Any], password: str) -> Optional[bytes]:
    try:
        salt = base64.b64decode(blob['salt'])
        nonce = base64.b64decode(blob['nonce'])
        ciphertext = base64.b64decode(blob['ciphertext'])
        iterations = int(blob.get('iterations', _KDF_ITERATIONS))

        key = _derive_key(password, salt, iterations)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext
    except Exception as e:
        _log_warning(f"Failed to decrypt blob: {e}")
        return None


def _read_wrapper(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, 'rb') as f:
            raw = f.read()
        return json.loads(raw.decode('utf-8'))
    except Exception as e:
        _log_warning(f"Failed to read wrapper for {path}: {e}")
        return None


def _update_lock_filename_for_vault(path: str) -> None:
    global _LOCK_FILENAME
    _LOCK_FILENAME = path + '.lock'


def _acquire_lock() -> bool:
    try:
        fd = os.open(_LOCK_FILENAME, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, str(os.getpid()).encode('utf-8'))
        finally:
            os.close(fd)
        return True
    except OSError as e:
        if e.errno == errno.EEXIST:
            _log_warning(f"Lock file already exists: {_LOCK_FILENAME}")
            return False
        _log_error(f"Error acquiring lock {_LOCK_FILENAME}: {e}")
        raise


def _release_lock() -> None:
    try:
        if os.path.exists(_LOCK_FILENAME):
            os.remove(_LOCK_FILENAME)
    except Exception as e:
        _log_warning(f"Failed to remove lock {_LOCK_FILENAME}: {e}")


def _list_vault_files() -> List[str]:
    found = []
    for d in DEFAULT_SECRETS_DIRS:
        if os.path.isdir(d):
            for entry in os.listdir(d):
                if entry.endswith('.json'):
                    found.append(os.path.join(d, entry))
    return found


# -------------------------------------------------------------------
# Helper: get single entry (by index or by name)
# -------------------------------------------------------------------
def _get_entry_by_index_or_name(key: str) -> Optional[Dict[str, Any]]:
    """
    key: index (1-based) or entry name
    Returns the entry dict or None if not found.
    Uses the in-memory _VAULT_STATE['entries'] which is a list of CSV-like strings:
      "index,name,host,port,username,password"
    """
    try:
        entries = _VAULT_STATE.get('entries', [])
        if not entries:
            return None

        # Try numeric index (1-based)
        try:
            idx = int(str(key).strip())
            if idx <= 0:
                return None
            if idx - 1 < len(entries):
                line = entries[idx - 1]
                parts = line.split(',')
                return {
                    "index": parts[0] if len(parts) > 0 else "",
                    "name": parts[1] if len(parts) > 1 else "",
                    "host": parts[2] if len(parts) > 2 else "",
                    "port": parts[3] if len(parts) > 3 else "",
                    "username": parts[4] if len(parts) > 4 else "",
                    "password": parts[5] if len(parts) > 5 else ""
                }
            return None
        except Exception:
            pass

        # Otherwise try to match by name (case-insensitive)
        name_lower = str(key).strip().lower()
        for line in entries:
            parts = line.split(',')
            ename = parts[1] if len(parts) > 1 else ""
            if ename and ename.strip().lower() == name_lower:
                return {
                    "index": parts[0] if len(parts) > 0 else "",
                    "name": ename,
                    "host": parts[2] if len(parts) > 2 else "",
                    "port": parts[3] if len(parts) > 3 else "",
                    "username": parts[4] if len(parts) > 4 else "",
                    "password": parts[5] if len(parts) > 5 else ""
                }

        # No match
        return None
    except Exception as ex:
        _log_warning(f"_get_entry_by_index_or_name error: {ex}")
        return None


def read_action(arg1: str) -> Dict[str, Any]:
    """
    Public action handler for retrieving a single entry.
    arg1: index (1-based) or entry name
    Returns a dict: {"status":"ok","result":{...}} or {"status":"error","message":...}
    """
    if not _VAULT_STATE.get('opened', False):
        return {"status": "error", "message": "Vault is not open"}

    if arg1 is None:
        return {"status": "error", "message": "Missing entry identifier (index or name)"}

    entry = _get_entry_by_index_or_name(arg1)
    if entry is None:
        return {"status": "error", "message": f"Entry not found: {arg1}"}

    # Normalize output keys expected by UI
    result = {
        "name": entry.get('name') or "",
        "ip": entry.get('host'),
        "port": entry.get('port'),
        "username": entry.get('username'),
        "password": entry.get('password'),
        "raw": dict(entry)
    }

    return {"status": "ok", "result": result}


# -------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------

def vault_manager(action: str,
                  arg1: Optional[str] = None,
                  arg2: Optional[Any] = None,
                  password: Optional[str] = None,
                  vault_name: Optional[str] = None) -> Dict[str, Any]:

    global VAULT_FILENAME, _VAULT_STATE

    action = (action or '').strip().lower()
    _log_info(f"vault_manager called action={action} vault_name={vault_name} arg1={arg1}")

    def _ok(result: Any = None) -> Dict[str, Any]:
        return {'status': 'ok', 'result': result}

    def _err(msg: str) -> Dict[str, Any]:
        _log_error(f"vault_manager error ({action}): {msg}")
        return {'status': 'error', 'message': msg}

    # ---------------------------------------------------------------
    # initialize
    # ---------------------------------------------------------------
    if action == 'initialize':
        if not vault_name or not password:
            return _err("initialize requires vault_name and password")

        vault_path = vault_name
        if not os.path.isabs(vault_path) and os.path.dirname(vault_path) == '':
            vault_dir = DEFAULT_SECRETS_DIRS[0]
            _ensure_dir_exists(vault_dir)
            vault_path = os.path.join(vault_dir, vault_name)

        vault_path = os.path.abspath(vault_path)
        data = {'entries': []}

        wrapper = _encrypt_blob(json.dumps(data).encode('utf-8'), password)
        if not _atomic_write_json(vault_path, wrapper):
            return _err("Failed to write vault file")

        VAULT_FILENAME = vault_path
        _update_lock_filename_for_vault(VAULT_FILENAME)

        return _ok({'vault': VAULT_FILENAME})

    # ---------------------------------------------------------------
    # list
    # ---------------------------------------------------------------
    if action == 'list':
        files = _list_vault_files()
        basenames = [os.path.basename(p) for p in files]
        return _ok(basenames)

    # ---------------------------------------------------------------
    # open
    # ---------------------------------------------------------------
    if action == 'open':
        if not vault_name or not password:
            return _err("open requires vault_name and password")

        vault_path = vault_name
        if not os.path.isabs(vault_path):
            candidate = os.path.join(DEFAULT_SECRETS_DIRS[0], vault_path)
            if os.path.exists(candidate):
                vault_path = candidate

        vault_path = os.path.abspath(vault_path)
        wrapper = _read_wrapper(vault_path)
        if wrapper is None:
            return _err("Failed to read vault wrapper")

        plaintext = _decrypt_blob(wrapper, password)
        if plaintext is None:
            return _err("Failed to open vault: wrong password or corrupted file")

        data = json.loads(plaintext.decode('utf-8'))

        # store password in memory_helper
        if memory_helper is not None:
            memory_helper.set(vault_path, password)

        VAULT_FILENAME = vault_path
        _update_lock_filename_for_vault(VAULT_FILENAME)

        _VAULT_STATE['opened'] = True
        _VAULT_STATE['entries'] = data.get('entries', [])

        try:
            _acquire_lock()
        except Exception:
            pass

        return _ok({'vault': VAULT_FILENAME, 'entries_count': len(_VAULT_STATE['entries'])})

    # ---------------------------------------------------------------
    # l_entries
    # ---------------------------------------------------------------
    if action == 'l_entries':

        # 1. If vault already opened
        if _VAULT_STATE.get('opened'):
            vault_path = VAULT_FILENAME
            password = memory_helper.get(vault_path) if memory_helper else None
            if not password:
                return _err("Password not found in memory for opened vault")

        else:
            # 2. Try to find any vault with a lock file
            vault_path = None
            for d in DEFAULT_SECRETS_DIRS + ['.']:
                for lf in Path(d).glob('*.lock'):
                    candidate = str(lf)[:-5]
                    pwd = memory_helper.get(candidate) if memory_helper else None
                    if pwd:
                        vault_path = candidate
                        password = pwd
                        break
                if vault_path:
                    break

            if not vault_path:
                return _err("No vault opened")

            wrapper = _read_wrapper(vault_path)
            if wrapper is None:
                return _err("Failed to read vault wrapper")

            plaintext = _decrypt_blob(wrapper, password)
            if plaintext is None:
                return _err("Failed to decrypt vault")

            data = json.loads(plaintext.decode('utf-8'))
            _VAULT_STATE['opened'] = True
            _VAULT_STATE['entries'] = data.get('entries', [])
            VAULT_FILENAME = vault_path
            _update_lock_filename_for_vault(VAULT_FILENAME)

        # 3. Format entries as table
        entries = _VAULT_STATE.get('entries', [])
        if not entries:
            return _ok("No entries in vault")

        table_lines = []
        header = f"{'INDEX':<6} {'NAME':<20} {'HOST':<20} {'PORT':<6} {'USERNAME':<20} {'PASSWORD':<20}"
        table_lines.append(header)
        table_lines.append("-" * len(header))

        for line in entries:
            parts = line.split(',')
            index = parts[0] if len(parts) > 0 else ''
            name = parts[1] if len(parts) > 1 else ''
            host = parts[2] if len(parts) > 2 else ''
            port = parts[3] if len(parts) > 3 else ''
            username = parts[4] if len(parts) > 4 else ''
            password = parts[5] if len(parts) > 5 else ''

            table_lines.append(
                f"{index:<6} {name:<20} {host:<20} {port:<6} {username:<20} {password:<20}"
            )

        return _ok("\n".join(table_lines))

    # ---------------------------------------------------------------
    # add_entry
    # ---------------------------------------------------------------
    if action == 'add_entry':
        if not _VAULT_STATE.get('opened'):
            return _err("Vault not opened")

        vault_path = VAULT_FILENAME
        pwd = memory_helper.get(vault_path) if memory_helper else None
        if not pwd:
            return _err("Password not found in memory for opened vault")

        if not arg1:
            return _err("add_entry requires arg1=name")

        if not isinstance(arg2, dict):
            return _err("add_entry requires arg2=dict with host, port, username, password")

        name = arg1
        host = arg2.get("host", "")
        port = arg2.get("port", "")
        username = arg2.get("username", "")
        password = arg2.get("password", "")

        entries = _VAULT_STATE.get('entries', [])
        if entries:
            try:
                last_index = max(int(e.split(',')[0]) for e in entries)
            except Exception:
                last_index = len(entries)
            new_index = last_index + 1
        else:
            new_index = 1

        line = f"{new_index},{name},{host},{port},{username},{password}"
        entries.append(line)

        data = {'entries': entries}
        wrapper = _encrypt_blob(json.dumps(data).encode('utf-8'), pwd)

        if not _atomic_write_json(vault_path, wrapper):
            return _err("Failed to write updated vault")

        _VAULT_STATE['entries'] = entries

        return _ok({"added": new_index})

    # ---------------------------------------------------------------
    # read (single entry)
    # ---------------------------------------------------------------
    if action == 'read':
        # arg1 expected: index (1-based) or name
        if not _VAULT_STATE.get('opened'):
            return _err("Vault is not open")
        if not arg1:
            return _err("read requires arg1=index_or_name")
        return read_action(arg1)

    # ---------------------------------------------------------------
    # unknown action
    # ---------------------------------------------------------------
    return _err(f"Unknown action: {action}")
