#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QuickConfig Wizard — Final Advanced Version
Does NOT open any SNS session directly.
Uses ONLY memory_helper to ensure no active sessions exist.
Prompts for SNS admin password at startup.
Injects post-restore network configuration commands before reboot.
"""

from __future__ import annotations

from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
import os
import ipaddress
import configparser
import sys
import subprocess

# -------------------------
# Default SNS connection parameters
# -------------------------
DEFAULT_SNS_IP = "10.0.0.254"
DEFAULT_SNS_PORT = 443
DEFAULT_SNS_USERNAME = "admin"
DEFAULT_SNS_PASSWORD = "admin"

# -------------------------
# Resolve installpath and update sys.path BEFORE importing UTIL.*
# -------------------------
def _read_installpath_from_ini() -> Optional[str]:
    start_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [start_dir]
    if os.path.basename(start_dir).lower() == "util":
        parent = os.path.abspath(os.path.join(start_dir, os.pardir))
        candidates.insert(0, parent)

    ini_rel = os.path.join("ConfigFiles", "SCAconfig.ini")
    for start in candidates:
        current = start
        while True:
            ini_path = os.path.join(current, ini_rel)
            if os.path.isfile(ini_path):
                try:
                    cfg = configparser.ConfigParser()
                    cfg.read(ini_path)
                    installpath = None
                    if cfg.defaults() and "installpath" in cfg.defaults():
                        installpath = cfg.defaults().get("installpath")
                    if installpath is None:
                        for section in cfg.sections():
                            if "installpath" in cfg[section]:
                                installpath = cfg[section].get("installpath")
                                break
                    if installpath:
                        installpath = os.path.expanduser(os.path.expandvars(installpath.strip()))
                        if not os.path.isabs(installpath):
                            ini_dir = os.path.dirname(ini_path)
                            installpath = os.path.normpath(os.path.join(ini_dir, installpath))
                        return os.path.abspath(installpath)
                except Exception:
                    return None
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
    return None

_installpath = _read_installpath_from_ini()
if _installpath:
    if _installpath not in sys.path:
        sys.path.insert(0, _installpath)
    util_dir = os.path.join(_installpath, "UTIL")
    if os.path.isdir(util_dir) and util_dir not in sys.path:
        sys.path.insert(0, util_dir)
else:
    this_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.abspath(os.path.join(this_dir, os.pardir))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

# -------------------------
# IMPORTS
# -------------------------
from UTIL import memory_helper
from UTIL import log_helper

# -------------------------
# Logging wrapper
# -------------------------
def _log(msg: str) -> None:
    try:
        if log_helper is not None:
            log_helper.log_writer(msg)
    except Exception:
        pass


# -------------------------
# Input parsing
# -------------------------
def _parse_user_input(raw: str) -> Tuple[str, Optional[ipaddress.IPv4Interface]]:
    if not isinstance(raw, str):
        raise ValueError("Input must be a string.")
    token = raw.strip()
    if not token:
        raise ValueError("Empty input.")
    lower = token.lower()
    if lower == "quit":
        return "quit", None
    if lower == "dhcp":
        return "dhcp", None
    try:
        iface = ipaddress.ip_interface(token)
        if isinstance(iface, ipaddress.IPv4Interface):
            return "ip", iface
        else:
            raise ValueError("Only IPv4 addresses are accepted.")
    except Exception as exc:
        raise ValueError(f"Invalid input format: {exc}")


# -------------------------
# Compute LAN network address
# -------------------------
def _compute_network_address(ip_str: str, mask: int) -> str:
    iface = ipaddress.ip_interface(f"{ip_str}/{mask}")
    return f"{iface.network.network_address}/{mask}"


# -------------------------
# SNSCLI restore with injected commands
# -------------------------
def _run_restore_via_snscli(password: str, installpath: str, safe_name: str,
                            LAN_address: str, LAN_mask: int,
                            WAN_address: str, WAN_mask: int,
                            FW_GTW: str, LAN_net_address: str):

    file_path = os.path.abspath(os.path.join(installpath, "DefaultConfig", f"{safe_name}.na"))

    commands = f"""MODIFY ON
CONFIG RESTORE list=all < {file_path}

CONFIG NETWORK INTERFACE ADDRESS REMOVE address=dhcp ifname=ethernet0
CONFIG NETWORK INTERFACE ADDRESS ADD ifname=ethernet0 address={WAN_address} addressComment= mask={WAN_mask} refAddress={WAN_address}
CONFIG NETWORK INTERFACE ADDRESS REMOVE mask=24 refAddress=192.168.1.254 address=192.168.1.254 ifname=ethernet1
CONFIG NETWORK INTERFACE ADDRESS ADD ifname=ethernet1 address={LAN_address} addressComment= mask={LAN_mask} refAddress={LAN_address}
CONFIG NETWORK ACTIVATE

config object network new name=LAN comment="Rete IT locale " ip={LAN_net_address} mask={LAN_mask} update=1
config object host new name=LAN_GTW comment="" ip="{LAN_address}" resolve=static mac="" update=1
config object host new name=GTW comment="" ip="{FW_GTW}" resolve=static mac="" update=1
config object host new name=SNS_PUBLIC comment="" ip="{WAN_address}" resolve=static mac="" update=1
config object activate

SYSTEM REBOOT
"""

    cmd = [
        "snscli",
        "--host", DEFAULT_SNS_IP,
        "--port", str(DEFAULT_SNS_PORT),
        "--user", DEFAULT_SNS_USERNAME,
        "--password", password,
        "--no-sslverifypeer",
        "--no-sslverifyhost"
    ]

    _log(f"QuickConfig: launching snscli for restore: {cmd}")

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    out, err = proc.communicate(commands)

    _log(f"snscli stdout: {out}")
    _log(f"snscli stderr: {err}")

    if proc.returncode != 0:
        raise RuntimeError(f"snscli failed with code {proc.returncode}")

    _log("QuickConfig: restore completed successfully.")


# -------------------------
# MAIN QUICKCONFIG
# -------------------------
def QuickConfig(arg: str) -> None:
    if not isinstance(arg, str) or not arg:
        _log("QuickConfig: arg must be a non-empty string.")
        raise ValueError("arg must be a non-empty string")

    safe_name = os.path.basename(arg)
    installpath = _installpath

    na_file_path = os.path.normpath(os.path.join(installpath, "DefaultConfig", f"{safe_name}.na"))
    na_file_path = os.path.abspath(na_file_path)
    _log(f"QuickConfig: resolved .na file for restore: '{na_file_path}'.")

    if not os.path.isfile(na_file_path):
        _log(f"QuickConfig: configuration file not found: '{na_file_path}'. Abort.")
        raise FileNotFoundError(f"Configuration file not found: {na_file_path}")

    # ---------------------------------------------------------
    # 0) SNS admin password prompt
    # ---------------------------------------------------------
    print("SNS admin password, press ENTER for the default (admin):")
    pw = input("> ").strip()
    sns_password = pw if pw else DEFAULT_SNS_PASSWORD
    _log("QuickConfig: SNS password set (default used if empty).")

    # ---------------------------------------------------------
    # 1) Ensure NO SNS sessions are currently active
    # ---------------------------------------------------------
    try:
        all_sessions = memory_helper.get_all_sessions()
    except Exception:
        all_sessions = {}

    if all_sessions:
        print("Error: There are active SNS sessions. Close them before proceeding.")
        _log("QuickConfig: active sessions found in memory_helper. Abort.")
        return

    _log("QuickConfig: no active sessions. Proceeding with wizard.")

    # ---------------------------------------------------------
    # 2) NETWORK INFORMATION COLLECTION
    # ---------------------------------------------------------
    print("")
    print("Enter addresses in the form 192.168.1.254/24 or 192.168.1.254/255.255.255.0, type DHCP for DHCP, or quit to exit.")
    _log("QuickConfig: starting network information collection.")

    while True:
        try:
            raw_lan = input("1) Insert the LAN address: ").strip()
            kind_lan, lan_iface = _parse_user_input(raw_lan)
            if kind_lan == "quit":
                _log("QuickConfig: wizard aborted by user (quit).")
                return

            raw_wan = input("2) Insert the WAN address: ").strip()
            kind_wan, wan_iface = _parse_user_input(raw_wan)
            if kind_wan == "quit":
                _log("QuickConfig: wizard aborted by user (quit).")
                return

            raw_fw = input("3) Insert the Firewall gateway: ").strip()
            kind_fw, fw_iface = _parse_user_input(raw_fw)
            if kind_fw == "quit":
                _log("QuickConfig: wizard aborted by user (quit).")
                return

        except ValueError as ve:
            _log(f"QuickConfig: invalid input: {ve}. Restarting input.")
            print("")
            continue

        if kind_lan == "dhcp":
            LAN_address = "DHCP"
            LAN_mask = None
        else:
            LAN_address = str(lan_iface.ip)
            LAN_mask = int(lan_iface.network.prefixlen)

        if kind_wan == "dhcp":
            WAN_address = "DHCP"
            WAN_mask = None
        else:
            WAN_address = str(wan_iface.ip)
            WAN_mask = int(wan_iface.network.prefixlen)

        if kind_fw == "dhcp":
            FW_GTW = "DHCP"
            GTW_mask = None
        else:
            FW_GTW = str(fw_iface.ip)
            GTW_mask = int(fw_iface.network.prefixlen)

        if (kind_wan == "ip") and (kind_fw == "ip"):
            wan_network = ipaddress.ip_network(f"{WAN_address}/{WAN_mask}", strict=False)
            fw_network = ipaddress.ip_network(f"{FW_GTW}/{GTW_mask}", strict=False)

            if not (ipaddress.ip_address(FW_GTW) in wan_network and ipaddress.ip_address(WAN_address) in fw_network):
                print("Error: WAN and Firewall gateway are not in the same subnet. Try again or type 'quit'.")
                _log("QuickConfig: WAN and FW gateway not in same subnet.")
                continue

        break

    # ---------------------------------------------------------
    # 3) Compute LAN network address
    # ---------------------------------------------------------
    if LAN_address != "DHCP":
        LAN_net_address = _compute_network_address(LAN_address, LAN_mask)
    else:
        LAN_net_address = None

    # ---------------------------------------------------------
    # 4) RESTORE VIA SNSCLI (NO SNS CONNECTION OPENED BY WIZARD)
    # ---------------------------------------------------------
    _log("QuickConfig: starting restore via snscli (no SNS session opened by wizard).")

    try:
        _run_restore_via_snscli(
            sns_password, installpath, safe_name,
            LAN_address, LAN_mask,
            WAN_address, WAN_mask,
            FW_GTW, LAN_net_address
        )
        _log(f"QuickConfig: restore completed successfully for '{safe_name}'.")
    except Exception as e:
        _log(f"QuickConfig: restore failed: {e}.")
        raise
