#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workspace_helper.py

Gestione dei Workspaces. Ogni Workspace è rappresentato da una directory
<project_root>/Workspaces/<name> che contiene almeno la sottodirectory Backup.

Persistenza:
 - Workspaces: <project_root>/Workspaces/workspaces.json
 - Workspace attivo: <project_root>/tmp/active_workspace.json
"""

from typing import Optional, Dict, Any, List
import json
from pathlib import Path
from datetime import datetime
import shutil

# Optional logging
try:
    from UTIL import log_helper
except Exception:
    log_helper = None


# -------------------------------------------------------------------
# Logging compatibile con log_helper.log_writer
# -------------------------------------------------------------------
def _log_info(msg: str) -> None:
    try:
        if log_helper is not None:
            log_helper.log_writer(f"INFO: {msg}")
    except Exception:
        pass

def _log_error(msg: str) -> None:
    try:
        if log_helper is not None:
            log_helper.log_writer(f"ERROR: {msg}")
    except Exception:
        pass


# -------------------------------------------------------------------
# Paths and project root detection
# -------------------------------------------------------------------
def _find_project_root(max_levels: int = 8) -> Path:
    cur = Path(__file__).resolve().parent
    for _ in range(max_levels):
        if (cur / "main.py").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return Path.cwd().resolve()

_PROJECT_ROOT = _find_project_root()
_WORKSPACES_DIR = _PROJECT_ROOT / "Workspaces"
_WORKSPACES_FILE = _WORKSPACES_DIR / "workspaces.json"
_TMP_DIR = _PROJECT_ROOT / "tmp"
_ACTIVE_FILE = _TMP_DIR / "active_workspace.json"


# -------------------------------------------------------------------
# Low-level helpers
# -------------------------------------------------------------------
def _ensure_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        _log_error(f"_ensure_dir failed for {path}: {e}")
        return False

def _atomic_write_json(path: Path, data: Any) -> bool:
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        _ensure_dir(path.parent)
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            try:
                import os
                os.fsync(f.fileno())
            except Exception:
                pass
        tmp.replace(path)
        return True
    except Exception as e:
        _log_error(f"_atomic_write_json failed for {path}: {e}")
        return False

def _read_json(path: Path) -> Optional[Any]:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _log_error(f"_read_json failed for {path}: {e}")
        return None


# -------------------------------------------------------------------
# Store init / load / save
# -------------------------------------------------------------------
def init_store() -> Dict[str, Any]:
    try:
        if not _ensure_dir(_WORKSPACES_DIR):
            return {"status": "error", "message": f"Failed to create Workspaces dir: {_WORKSPACES_DIR}"}
        if not _ensure_dir(_TMP_DIR):
            return {"status": "error", "message": f"Failed to create tmp dir: {_TMP_DIR}"}

        # svuota tmp
        try:
            for child in _TMP_DIR.iterdir():
                try:
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                    elif child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                except Exception:
                    pass
        except Exception as e:
            _log_error(f"Failed to clear tmp dir {_TMP_DIR}: {e}")

        # crea workspaces.json se manca
        if not _WORKSPACES_FILE.exists():
            base = {"workspaces": {}, "current": None}
            if not _atomic_write_json(_WORKSPACES_FILE, base):
                return {"status": "error", "message": "Failed to create workspaces file"}

        # reset current se manca active file
        if not _ACTIVE_FILE.exists():
            data = _read_json(_WORKSPACES_FILE)
            if isinstance(data, dict) and data.get("current"):
                data["current"] = None
                _atomic_write_json(_WORKSPACES_FILE, data)

        return {"status": "ok", "result": {"workspaces_file": str(_WORKSPACES_FILE), "tmp_dir": str(_TMP_DIR)}}
    except Exception as e:
        _log_error(f"init_store error: {e}")
        return {"status": "error", "message": str(e)}

def _load_store() -> Dict[str, Any]:
    data = _read_json(_WORKSPACES_FILE)
    if not isinstance(data, dict):
        data = {"workspaces": {}, "current": None}
    if "workspaces" not in data:
        data["workspaces"] = {}
    if "current" not in data:
        data["current"] = None
    return data

def _save_store(data: Dict[str, Any]) -> bool:
    return _atomic_write_json(_WORKSPACES_FILE, data)


# -------------------------------------------------------------------
# CRUD Workspaces
# -------------------------------------------------------------------
def list_workspaces() -> Dict[str, Any]:
    try:
        data = _load_store()
        names = list(data.get("workspaces", {}).keys())
        return {"status": "ok", "result": names}
    except Exception as e:
        _log_error(f"list_workspaces error: {e}")
        return {"status": "error", "message": str(e)}

def get_workspace(name: str) -> Dict[str, Any]:
    try:
        data = _load_store()
        ws = data.get("workspaces", {}).get(name)
        if not ws:
            return {"status": "error", "message": "Workspace not found"}
        return {"status": "ok", "result": ws}
    except Exception as e:
        _log_error(f"get_workspace error: {e}")
        return {"status": "error", "message": str(e)}

def create_workspace(name: str, description: str = "") -> Dict[str, Any]:
    try:
        if not name or not name.strip():
            return {"status": "error", "message": "Invalid workspace name"}
        name = name.strip()
        data = _load_store()
        if name in data["workspaces"]:
            return {"status": "error", "message": "Workspace already exists"}

        workspace_dir_rel = str(Path("Workspaces") / name)
        workspace_dir_abs = (_PROJECT_ROOT / workspace_dir_rel).resolve()

        ws = {
            "name": name,
            "description": description or "",
            "workspace_directory": workspace_dir_rel,
            "created": datetime.now().astimezone().isoformat(),
            "last_activated": None
        }

        data["workspaces"][name] = ws
        if not _save_store(data):
            return {"status": "error", "message": "Failed to persist workspace"}

        # create directories
        try:
            workspace_dir_abs.mkdir(parents=True, exist_ok=True)
            (workspace_dir_abs / "Backup").mkdir(parents=True, exist_ok=True)
        except Exception as e:
            _log_error(f"Failed to create workspace directories for {name}: {e}")
            return {"status": "ok", "result": ws, "warning": f"Workspace created but failed to create directories: {e}"}

        return {"status": "ok", "result": ws}
    except Exception as e:
        _log_error(f"create_workspace error: {e}")
        return {"status": "error", "message": str(e)}

def update_workspace(name: str, description: Optional[str] = None) -> Dict[str, Any]:
    try:
        data = _load_store()
        ws = data.get("workspaces", {}).get(name)
        if not ws:
            return {"status": "error", "message": "Workspace not found"}
        if description is not None:
            ws["description"] = description
        data["workspaces"][name] = ws
        if not _save_store(data):
            return {"status": "error", "message": "Failed to persist workspace"}
        return {"status": "ok", "result": ws}
    except Exception as e:
        _log_error(f"update_workspace error: {e}")
        return {"status": "error", "message": str(e)}

def delete_workspace(name: str) -> Dict[str, Any]:
    try:
        data = _load_store()
        ws = data.get("workspaces", {}).get(name)
        if not ws:
            return {"status": "error", "message": "Workspace not found"}

        # se attivo → disattiva
        if data.get("current") == name:
            deactivate_workspace()
            data = _load_store()

        # path assoluto
        workspace_dir_rel = ws.get("workspace_directory") or str(Path("Workspaces") / name)
        workspace_dir_abs = (_PROJECT_ROOT / workspace_dir_rel).resolve()

        # rimuovi dal JSON
        data["workspaces"].pop(name, None)
        if not _save_store(data):
            return {"status": "error", "message": "Failed to persist deletion"}

        # elimina directory fisica
        try:
            if workspace_dir_abs.exists():
                shutil.rmtree(workspace_dir_abs, ignore_errors=True)
        except Exception as e:
            _log_error(f"Failed to delete workspace directory {workspace_dir_abs}: {e}")
            return {
                "status": "ok",
                "result": {"deleted": name},
                "warning": f"Workspace deleted but directory removal failed: {e}"
            }

        return {"status": "ok", "result": {"deleted": name}}
    except Exception as e:
        _log_error(f"delete_workspace error: {e}")
        return {"status": "error", "message": str(e)}


# -------------------------------------------------------------------
# Activation / current workspace
# -------------------------------------------------------------------
def _write_active_file(payload: Dict[str, Any]) -> bool:
    try:
        _ensure_dir(_TMP_DIR)
        return _atomic_write_json(_ACTIVE_FILE, payload)
    except Exception as e:
        _log_error(f"_write_active_file error: {e}")
        return False

def _remove_active_file() -> None:
    try:
        if _ACTIVE_FILE.exists():
            _ACTIVE_FILE.unlink()
    except Exception:
        pass

def activate_workspace(name: str, create_dirs: bool = True) -> Dict[str, Any]:
    try:
        data = _load_store()
        ws = data.get("workspaces", {}).get(name)
        if not ws:
            return {"status": "error", "message": "Workspace not found"}

        workspace_dir_rel = ws.get("workspace_directory") or str(Path("Workspaces") / name)
        workspace_dir_abs = (_PROJECT_ROOT / workspace_dir_rel).resolve()
        backup_dir_abs = (workspace_dir_abs / "Backup").resolve()

        created = []
        failed = []

        if create_dirs:
            try:
                workspace_dir_abs.mkdir(parents=True, exist_ok=True)
                created.append(str(workspace_dir_abs))
            except Exception as e:
                failed.append({"path": str(workspace_dir_abs), "error": str(e)})
            try:
                backup_dir_abs.mkdir(parents=True, exist_ok=True)
                created.append(str(backup_dir_abs))
            except Exception as e:
                failed.append({"path": str(backup_dir_abs), "error": str(e)})

        ws["last_activated"] = datetime.now().astimezone().isoformat()
        data["workspaces"][name] = ws
        data["current"] = name
        if not _save_store(data):
            return {"status": "error", "message": "Failed to persist activation"}

        active_payload = {
            "name": name,
            "activated_at": ws["last_activated"],
            "workspace_directory": str(workspace_dir_abs),
            "backup_directory": str(backup_dir_abs)
        }
        _write_active_file(active_payload)

        result = {
            "workspace_directory": str(workspace_dir_abs),
            "backup_directory": str(backup_dir_abs),
            "created": created,
            "failed": failed
        }
        return {"status": "ok", "result": result}
    except Exception as e:
        _log_error(f"activate_workspace error: {e}")
        return {"status": "error", "message": str(e)}

def deactivate_workspace() -> Dict[str, Any]:
    try:
        data = _load_store()
        data["current"] = None
        if not _save_store(data):
            return {"status": "error", "message": "Failed to persist deactivation"}
        _remove_active_file()
        return {"status": "ok", "result": None}
    except Exception as e:
        _log_error(f"deactivate_workspace error: {e}")
        return {"status": "error", "message": str(e)}

def get_current_workspace() -> Dict[str, Any]:
    try:
        active = _read_json(_ACTIVE_FILE)
        if isinstance(active, dict) and active.get("name"):
            return {"status": "ok", "result": active}
        return {"status": "ok", "result": None}
    except Exception as e:
        _log_error(f"get_current_workspace error: {e}")
        return {"status": "error", "message": str(e)}


# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------
def resolve_workspace_dir(name_or_index: Any) -> Dict[str, Any]:
    try:
        data = _load_store()
        names = list(data.get("workspaces", {}).keys())
        if isinstance(name_or_index, int) or (isinstance(name_or_index, str) and str(name_or_index).isdigit()):
            idx = int(name_or_index)
            if idx == 0:
                idx = 1
            idx0 = idx - 1
            if idx0 < 0 or idx0 >= len(names):
                return {"status": "error", "message": "Index out of range"}
            name = names[idx0]
        else:
            name = str(name_or_index)
        ws = data.get("workspaces", {}).get(name)
        if not ws:
            return {"status": "error", "message": "Workspace not found"}
        workspace_dir_rel = ws.get("workspace_directory") or str(Path("Workspaces") / name)
        workspace_dir_abs = (_PROJECT_ROOT / workspace_dir_rel).resolve()
        return {"status": "ok", "result": str(workspace_dir_abs)}
    except Exception as e:
        _log_error(f"resolve_workspace_dir error: {e}")
        return {"status": "error", "message": str(e)}

def ensure_workspace_dirs_exist(name: str) -> Dict[str, Any]:
    try:
        data = _load_store()
        ws = data.get("workspaces", {}).get(name)
        if not ws:
            return {"status": "error", "message": "Workspace not found"}
        workspace_dir_rel = ws.get("workspace_directory") or str(Path("Workspaces") / name)
        workspace_dir_abs = (_PROJECT_ROOT / workspace_dir_rel).resolve()
        backup_dir_abs = (workspace_dir_abs / "Backup").resolve()
        created = []
        failed = []
        try:
            workspace_dir_abs.mkdir(parents=True, exist_ok=True)
            created.append(str(workspace_dir_abs))
        except Exception as e:
            failed.append({"path": str(workspace_dir_abs), "error": str(e)})
        try:
            backup_dir_abs.mkdir(parents=True, exist_ok=True)
            created.append(str(backup_dir_abs))
        except Exception as e:
            failed.append({"path": str(backup_dir_abs), "error": str(e)})
        return {"status": "ok", "result": {"created": created, "failed": failed}}
    except Exception as e:
        _log_error(f"ensure_workspace_dirs_exist error: {e}")
        return {"status": "error", "message": str(e)}

def create_and_activate(name: str, description: str) -> Dict[str, Any]:
    c = create_workspace(name, description)
    if c.get("status") != "ok":
        return c
    return activate_workspace(name, create_dirs=True)
