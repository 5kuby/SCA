#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
menu_helper.py
Dispatcher for UI menus.

Exposes:
    menu_caller(target: str)

Targets:
    "main"      -> calls UI.menu.main_menu()
    "sns"       -> calls UI.SNS_menu.sns_management()
    "vault"     -> calls UI.vault_menu.vault_menu()
    "workspace" -> calls UI.workspace_menu.workspace_menu()
    "quick config wizard" -> calls UI.wizard_menu.wizard_menu()
"""

def menu_caller(target: str):
    target = (target or "").strip().lower()

    if target == "main":
        try:
            from UI.menu import main_menu
            return main_menu()
        except Exception as e:
            print(f"[menu_helper] Unable to launch main menu: {e}")
            return None

    elif target == "sns":
        try:
            from UI.SNS_menu import sns_management
            return sns_management()
        except Exception as e:
            print(f"[menu_helper] Unable to launch SNS menu: {e}")
            return None

    elif target == "vault":
        try:
            from UI.vault_menu import vault_menu
            return vault_menu()
        except Exception as e:
            print(f"[menu_helper] Unable to launch Vault menu: {e}")
            return None

    elif target == "workspace":
        try:
            from UI.workspace_menu import workspace_menu
            return workspace_menu()
        except Exception as e:
            print(f"[menu_helper] Unable to launch Workspace menu: {e}")
            return None

    elif target in ("quick config wizard", "quick_config_wizard"):
        try:
            from UI.wizard_menu import wizard_menu
            return wizard_menu()
        except Exception as e:
            print(f"[menu_helper] Unable to launch Quick Config Wizard: {e}")
            return None

    else:
        print(f"[menu_helper] Unknown target: {target}")
        return None
