"""Start with Windows through the per-user Run key. No admin rights are needed."""
import os
import sys

from claude_pulse import fetch

KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "ClaudePulse"


def supported():
    return fetch.WINDOWS


def command():
    """The command line that starts this app without a console window."""
    if getattr(sys, "frozen", False):
        return '"%s"' % sys.executable
    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.isfile(pythonw):
        exe = pythonw
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return '"%s" "%s"' % (exe, os.path.join(root, "claude_pulse.pyw"))


def is_enabled():
    if not supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as key:
            winreg.QueryValueEx(key, NAME)
            return True
    except OSError:
        return False


def set_enabled(on):
    if not supported():
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as key:
        if on:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass
    fetch.save_setting("autostart_set", True)


def enable_on_first_run():
    """Turn autostart on once, the first time the app runs. The tray menu turns it off for good."""
    if not supported():
        return
    raw = fetch.load_json(fetch.CONFIG)
    if isinstance(raw, dict) and raw.get("autostart_set"):
        return
    try:
        set_enabled(True)
    except OSError:
        pass
