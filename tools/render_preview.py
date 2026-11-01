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
    for i in range(7 * 288):
        t = now - 7 * 86400 + i * 300
        hour = time.localtime(t).tm_hour
        session = ((hour - 9) % 5 + time.localtime(t).tm_min / 60) * 14 if 9 <= hour < 23 else 0
        rows.append([t, round(session, 1), round(10 + i / (7 * 288) * 50, 1)])
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
THEMES = ("orbit", "lines", "terminal", "battery", "paper")
PANEL = {"dark": ("#1f2130", "#eceef4", "#9aa0b4"), "light": ("#f7f7fb", "#20222c", "#6b7080")}


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
    QTimer.singleShot(1200, loop.quit)
    loop.exec()
    view.grabWindow().save(path)
    view.close()


for theme in THEMES:
    for mode, (bg, text, muted) in PANEL.items():
        for name, usage in cases.items():
            shot("Dashboard.qml", {"usage": usage, "now": now, "theme": theme, "colorMode": mode},
                 "#808080", f"{out}/{theme}-{name}-{mode}.png")
        for numbers, width in ((True, 110), (False, 50)):
            suffix = "" if numbers else "-mark"
            shot("PanelIcon.qml", {"usage": cases["risk"], "theme": theme, "colorMode": mode, "textColor": text,
                                   "mutedColor": muted, "showNumbers": numbers},
                 bg, f"{out}/{theme}-icon-{mode}{suffix}.png", (width, 28))
