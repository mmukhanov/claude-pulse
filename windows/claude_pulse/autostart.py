"""Start with Windows through the per-user Run key. No admin rights are needed."""
import os
import shutil
import sys

from claude_pulse import fetch

KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "ClaudePulse"


def supported():
    return fetch.WINDOWS


def command():
    """The command line that starts this app without a console window.

    From source it goes through the `pyw` launcher when there is one: the path of
    the python.exe running now can be a Microsoft Store alias or a venv that can't be
    started directly at logon.
    """
    if getattr(sys, "frozen", False):
        return '"%s"' % sys.executable
    exe = shutil.which("pyw")
    if not exe:
        exe = sys.executable
        pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.isfile(pythonw):
            exe = pythonw
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return '"%s" "%s"' % (exe, os.path.join(root, "claude_pulse.pyw"))


def stored():
    """The command now in the Run key, or None."""
    if not supported():
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as key:
            return winreg.QueryValueEx(key, NAME)[0]
    except OSError:
        return None


def is_enabled():
    return stored() is not None


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


def check_on_start():
    """Turn autostart on the first time the app runs, and keep its path current.

    If the folder or exe was moved, the Run key still points to the old place and
    nothing starts at logon, so it is rewritten to where the app runs from now.
    Once turned off in the tray menu it stays off.
    """
    if not supported():
        return
    raw = fetch.load_json(fetch.CONFIG)
    first_run = not (isinstance(raw, dict) and raw.get("autostart_set"))
    current = stored()
    try:
        if first_run or (current is not None and current != command()):
            set_enabled(True)
    except OSError:
        pass
