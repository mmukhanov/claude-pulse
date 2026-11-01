#!/usr/bin/env python3
"""Tray icon for desktops other than Plasma 6 (StatusNotifier via Qt).

Shows the same dashboard as the Plasma widget and uses the same collector.
"""
import json
import os
import signal
import sys

from PyQt6.QtCore import QLocale, QProcess, QRectF, Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QColor, QCursor, QGuiApplication, QIcon, QPainter, QPalette, QPen, QPixmap
from PyQt6.QtQuick import QQuickView
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

HERE = os.path.dirname(os.path.abspath(__file__))
FETCH = os.path.join(HERE, "fetch.py")
DASHBOARD = os.path.normpath(os.path.join(HERE, "..", "ui", "Dashboard.qml"))


def level_color(pct, base):
    return QColor("#ef4444" if pct >= 85 else base)


def render_icon(session, week, risk):
    """Outer ring is the session, inner ring is the week, as in the Plasma widget."""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for pct, inset, base in ((session, 5, "#3b82f6"), (week, 20, "#d946ef")):
        rect = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
        p.setPen(QPen(QColor(128, 128, 128, 90), 9))
        p.drawEllipse(rect)
        if pct:
            pen = QPen(level_color(pct, base), 9)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(rect, 90 * 16, int(-min(100, pct) / 100 * 360 * 16))
    if risk:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f97316"))
        p.drawEllipse(QRectF(size - 22, 0, 22, 22))
    p.end()
    return QIcon(pixmap)


class Tray:
    def __init__(self):
        self.usage = None
        self.view = None
        self.process = None
        self.tray = QSystemTrayIcon(render_icon(0, 0, False))
        self.tray.setToolTip("Claude Pulse")
        self.tray.activated.connect(self.on_activated)
        menu = QMenu()
        for label, slot in (("Show", self.show_dashboard), ("Refresh", lambda: self.refresh(True)), ("Quit", QApplication.quit)):
            action = QAction(label, menu)
            action.triggered.connect(slot)
            menu.addAction(action)
        self.menu = menu
        self.tray.setContextMenu(menu)
        self.tray.show()
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: self.refresh(True))
        self.timer.start(300_000)
        self.refresh(True)

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
        if settings.get("interval_minutes"):
            self.timer.setInterval(int(settings["interval_minutes"] * 60_000))
        self.update_icon()
        self.push(busy=False)

    def update_icon(self):
        session = (self.usage or {}).get("session") or {}
        week = (self.usage or {}).get("week") or {}
        risk = bool(session.get("runout") or week.get("runout"))
        self.tray.setIcon(render_icon(session.get("pct", 0), week.get("pct", 0), risk))
        lines = ["Claude Pulse"]
        for name, limit in (("Session", session), ("Week", week)):
            if limit:
                lines.append("%s: %d%% used, %d%% left" % (name, round(limit["pct"]), 100 - round(limit["pct"])))
        self.tray.setToolTip("\n".join(lines))

    def push(self, busy):
        if not self.view:
            return
        root = self.view.rootObject()
        root.setProperty("busy", busy)
        if not busy and self.usage:
            root.setProperty("usage", self.usage)

    def build_view(self):
        language = ((self.usage or {}).get("settings") or {}).get("language")
        if language in ("ru", "en"):
            QLocale.setDefault(QLocale("ru_RU" if language == "ru" else "en_US"))
        palette = QGuiApplication.palette()
        view = QQuickView()
        view.setFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        background = palette.color(QPalette.ColorRole.Window)
        view.setColor(background)
        view.setInitialProperties({
            "usage": self.usage,
            "backgroundColor": background,
            "textColor": palette.color(QPalette.ColorRole.WindowText),
            "mutedColor": palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText),
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
        root.setProperty("now", __import__("time").time())
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
