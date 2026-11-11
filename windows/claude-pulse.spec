# PyInstaller build: pyinstaller claude-pulse.spec  ->  dist/ClaudePulse.exe
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ["claude_pulse.pyw"],
    datas=[("claude_pulse/ui", "claude_pulse/ui")] + collect_data_files("tzdata"),
    hiddenimports=["tzdata", "PyQt6.QtQml", "PyQt6.QtQuick"],
    excludes=["tkinter", "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtMultimedia",
              "PyQt6.QtBluetooth", "PyQt6.QtPdf", "PyQt6.Qt3DCore", "PyQt6.QtSql"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name="ClaudePulse",
    console=False,
    icon="docs/icon.ico",
    upx=False,
)
