#!/usr/bin/env python3
"""Tray icon for desktops other than Plasma 6 (StatusNotifier via Qt).

Shows the same dashboard as the Plasma widget and uses the same collector.
"""
import json
import math
import os
import signal
import sys
import time

from PyQt6.QtCore import QLocale, QProcess, QRectF, Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QColor, QCursor, QGuiApplication, QIcon, QPainter, QPalette, QPen, QPixmap
from PyQt6.QtQuick import QQuickView
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

HERE = os.path.dirname(os.path.abspath(__file__))
FETCH = os.path.join(HERE, "fetch.py")
DASHBOARD = os.path.normpath(os.path.join(HERE, "..", "ui", "Dashboard.qml"))


# Session and week colours and the icon shape, matching ui/Themes.js.
THEMES = {
    "orbit": ("Orbit", "rings", "#3b82f6", "#d946ef"),
    "lines": ("Lines", "bars", "#3b82f6", "#a855f7"),
    "terminal": ("Terminal", "bars", "#2563eb", "#9333ea"),
    "battery": ("Battery", "cells", "#3b82f6", "#a855f7"),
    "paper": ("Paper", "rings", "#4f7cac", "#8e5ea2"),
}
MODES = {"system": "Follow the system", "light": "Light", "dark": "Dark"}
CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "claude-pulse", "config.json")


def level_color(pct, base):
    return QColor("#ef4444" if pct >= 85 else base)


def render_icon(session, week, risk, theme="orbit"):
    """The panel mark as a pixmap. session is None on plans with no session limit."""
    _, shape, session_color, week_color = THEMES.get(theme, THEMES["orbit"])
    size = 64
    track = QColor(128, 128, 128, 90)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    marks = [(session, session_color), (week, week_color)]
    if shape == "rings":
        for (pct, base), inset in zip(marks, (5, 20)):
            if pct is None:
                continue
            rect = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
            p.setPen(QPen(track, 9))
            p.drawEllipse(rect)
            if pct:
                pen = QPen(level_color(pct, base), 9)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawArc(rect, 90 * 16, int(-min(100, pct) / 100 * 360 * 16))
    else:
        p.setPen(Qt.PenStyle.NoPen)
        for (pct, base), top in zip(marks, (14, 36)):
            if pct is None:
                continue
            if shape == "bars":
                p.setBrush(track)
                p.drawRoundedRect(QRectF(4, top, 56, 14), 4, 4)
                p.setBrush(level_color(pct, base))
                p.drawRoundedRect(QRectF(4, top, 56 * min(100, pct) / 100, 14), 4, 4)
            else:
                left = math.ceil((100 - pct) / 100 * 6)
                for i in range(6):
                    p.setBrush(level_color(pct, base) if i < left else track)
                    p.drawRoundedRect(QRectF(4 + i * 9.6, top, 8, 14), 2, 2)
    if risk:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f97316"))
        p.drawEllipse(QRectF(size - 22, 0, 22, 22))
    p.end()
    return QIcon(pixmap)


def save_setting(key, value):
    """Change one key of the config file, keeping the others."""
    try:
        with open(CONFIG, encoding="utf-8") as f:
            config = json.load(f)
        if not isinstance(config, dict):
            config = {}
    except (OSError, ValueError):
        config = {}
    config[key] = value
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG)


class Tray:
    def __init__(self):
        self.usage = None
        self.view = None
        self.theme = "orbit"
        self.mode = "system"
        self.process = None
        self.tray = QSystemTrayIcon(render_icon(0, 0, False))
        self.tray.setToolTip("Claude Pulse")
        self.tray.activated.connect(self.on_activated)
        menu = QMenu()
        for label, slot in (("Show", self.show_dashboard), ("Refresh", lambda: self.refresh(True)), ("Quit", QApplication.quit)):
            action = QAction(label, menu)
            action.triggered.connect(slot)
            menu.addAction(action)
        for title, key, options in (("Theme", "theme", {k: v[0] for k, v in THEMES.items()}), ("Appearance", "color_mode", MODES)):
            sub = menu.addMenu(title)
            for value, label in options.items():
                action = QAction(label, sub)
                action.triggered.connect(lambda _, k=key, v=value: self.choose(k, v))
                sub.addAction(action)
        self.menu = menu
        self.tray.setContextMenu(menu)
        self.tray.show()
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: self.refresh(True))
        self.timer.start(300_000)
        self.refresh(True)

    def choose(self, key, value):
        save_setting(key, value)
        if key == "theme":
            self.theme = value
        else:
            self.mode = value
        self.update_icon()
        self.push(busy=bool(self.process))

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_dashboard()

    def refresh(self, force):
        if self.process:
            return
        self.process = QProcess()
        self.process.finished.connect(self.on_finished)
        self.process.start(sys.executable, ["-I", FETCH] + (["--force"] if force else []))
        self.push(busy=True)

    def on_finished(self):
        output = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        self.process = None
        try:
            parsed = json.loads(output)
        except ValueError:
            parsed = dict(self.usage or {}, ok=False, error="The data collector did not answer")
        if parsed.get("fetched_at") or not self.usage:
            self.usage = parsed
        settings = parsed.get("settings") or {}
        self.theme = settings.get("theme", self.theme)
        self.mode = settings.get("color_mode", self.mode)
        if settings.get("interval_minutes"):
            self.timer.setInterval(int(settings["interval_minutes"] * 60_000))
        self.update_icon()
        self.push(busy=False)

    def update_icon(self):
        session = (self.usage or {}).get("session") or {}
        week = (self.usage or {}).get("week") or {}
        risk = bool(session.get("runout") or week.get("runout"))
        self.tray.setIcon(render_icon(session.get("pct", None if week else 0), week.get("pct", 0), risk, self.theme))
        lines = ["Claude Pulse"]
        if (self.usage or {}).get("plan"):
            lines.append("Plan: " + self.usage["plan"])
        for name, limit in (("Session", session), ("Week", week)):
            if limit:
                lines.append("%s: %d%% used, %d%% left" % (name, round(limit["pct"]), 100 - round(limit["pct"])))
        self.tray.setToolTip("\n".join(lines))

    def push(self, busy):
        if not self.view:
            return
        root = self.view.rootObject()
        root.setProperty("busy", busy)
        root.setProperty("theme", self.theme)
        root.setProperty("colorMode", self.mode)
        if not busy and self.usage:
            root.setProperty("usage", self.usage)

    def build_view(self):
        language = ((self.usage or {}).get("settings") or {}).get("language")
        if language in ("ru", "en"):
            QLocale.setDefault(QLocale("ru_RU" if language == "ru" else "en_US"))
        window = QGuiApplication.palette().color(QPalette.ColorRole.Window)
        view = QQuickView()
        view.setFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        view.setColor(QColor(Qt.GlobalColor.transparent))
        view.setInitialProperties({
            "usage": self.usage,
            "theme": self.theme,
            "colorMode": self.mode,
            "systemDark": window.lightnessF() < 0.5,
        })
        view.setSource(QUrl.fromLocalFile(DASHBOARD))
        root = view.rootObject()
        root.refreshRequested.connect(lambda: self.refresh(True))
        root.implicitHeightChanged.connect(lambda: view.resize(view.width(), int(root.implicitHeight())))
        view.activeChanged.connect(lambda: view.hide() if not view.isActive() and view.isVisible() else None)
        self.view = view

    def show_dashboard(self):
        if not self.view:
            self.build_view()
        root = self.view.rootObject()
        root.setProperty("usage", self.usage)
        root.setProperty("now", time.time())
        self.view.resize(int(root.implicitWidth()), int(root.implicitHeight()))
        area = QGuiApplication.primaryScreen().availableGeometry()
        spot = QCursor.pos()
        self.view.setPosition(min(spot.x(), area.right() - self.view.width()), min(spot.y(), area.bottom() - self.view.height()))
        self.view.show()
        self.view.requestActivate()
        self.refresh(False)

    def toggle_dashboard(self):
        if self.view and self.view.isVisible():
            self.view.hide()
        else:
            self.show_dashboard()


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    app.setApplicationName("Claude Pulse")
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray found. On GNOME, enable the AppIndicator extension.", file=sys.stderr)
    tray = Tray()
    if "--show" in sys.argv:
        QTimer.singleShot(2500, tray.show_dashboard)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
