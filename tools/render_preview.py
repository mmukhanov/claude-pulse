#!/usr/bin/env python3
"""Render the dashboard and panel icon offscreen with sample data.

usage: render_preview.py <output-dir> [live.json]
Used for the README images and for checking the UI without a Plasma shell.
"""
import json
import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QSG_RHI_BACKEND", "software")
from PyQt6.QtCore import QEventLoop, QTimer, QUrl
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtQuick import QQuickView

UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "package", "contents", "ui")
out = sys.argv[1]
app = QGuiApplication([])
now = time.time()


def window(pct, left, duration):
    elapsed = duration - left
    w = {"pct": pct, "reset": now + left, "pace": elapsed / duration * 100,
         "projected": pct + pct / elapsed * left, "runout": 0}
    if w["projected"] >= 100 and pct < 100:
        w["runout"] = now + (100 - pct) / (pct / elapsed)
    return w


def history():
    rows = []
    for i in range(289):
        session = (i % 60) / 60 * 70 if 60 < i < 250 else 0
        rows.append([now - 86400 + i * 300, round(session, 1), 30 + i * 0.09])
    return rows


stats = {"day": {"requests": 494, "sessions": 9}, "week": {"requests": 1717, "sessions": 21}}
cases = {
    "calm": {"ok": True, "fetched_at": now - 200, "session": window(18, 3 * 3600, 18000), "week": window(36, 2 * 86400, 604800),
             "plan": "Max", "models": [{"name": "Fable", "pct": 10, "reset": now + 172800}], "stats": stats, "history": history()},
    "risk": {"ok": True, "fetched_at": now - 20, "session": window(72, 2.5 * 3600, 18000), "week": window(88, 3 * 86400, 604800),
             "plan": "Max", "models": [{"name": "Fable", "pct": 91, "reset": now + 259200}], "stats": stats, "history": history()},
    "ultra": {"ok": True, "fetched_at": now - 20, "session": None, "week": window(41, 3 * 86400, 604800),
              "plan": "Ultra", "models": [], "stats": stats, "history": history()},
    "stale": {"ok": False, "error": "claude not found", "fetched_at": now - 900, "session": window(100, 1800, 18000),
              "week": window(64, 86400, 604800), "models": [], "stats": stats, "history": history()},
    "empty": None,
    "signedout": {"ok": False, "error": "Not logged in to Claude Code. Run claude and log in"},
}
if len(sys.argv) > 2:
    with open(sys.argv[2], encoding="utf-8") as f:
        cases["live"] = json.load(f)
themes = {"dark": ("#1f2130", "#eceef4", "#9aa0b4"), "light": ("#f7f7fb", "#20222c", "#6b7080")}


def shot(qml, props, background, path, size=None):
    view = QQuickView()
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setColor(QColor(background))
    view.setInitialProperties(props)
    view.setSource(QUrl.fromLocalFile(os.path.join(UI, qml)))
    for error in view.errors():
        print("QML ERROR", error.toString())
    root = view.rootObject()
    if root is None:
        return
    view.resize(*(size or (int(root.implicitWidth()), int(root.implicitHeight()))))
    view.show()
    loop = QEventLoop()
    QTimer.singleShot(1500, loop.quit)
    loop.exec()
    view.grabWindow().save(path)
    view.close()


for name, usage in cases.items():
    for theme, (bg, text, muted) in themes.items():
        shot("Dashboard.qml", {"usage": usage, "now": now, "backgroundColor": bg, "textColor": text, "mutedColor": muted},
             bg, f"{out}/dashboard-{name}-{theme}.png")
        if usage:
            for numbers, width in ((True, 92), (False, 32)):
                suffix = "" if numbers else "-rings"
                shot("PanelIcon.qml", {"usage": usage, "textColor": text, "mutedColor": muted, "showNumbers": numbers},
                     bg, f"{out}/icon-{name}-{theme}{suffix}.png", (width, 28))
